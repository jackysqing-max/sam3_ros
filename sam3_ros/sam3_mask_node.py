# SPDX-License-Identifier: Apache-2.0
"""Prompt-driven SAM3 segmentation for ROS 2 image streams.

Extracted from vla_simu_workspace; modified for standalone deployment in 2026.
"""

import math
import queue
import threading
import time
from contextlib import nullcontext

import numpy as np
import rclpy
import torch
from PIL import Image as PILImage
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32, String
from transformers import Sam3Model, Sam3Processor

from .image_utils import imgmsg_to_rgb, resize_keep_aspect
from .instance_selection import select_instance_indices


def mask_to_imgmsg(mask_u8: np.ndarray, header) -> Image:
    """Encode a binary 0/255 mask and preserve the source image header."""
    msg = Image()
    msg.header = header
    msg.height, msg.width = mask_u8.shape
    msg.encoding = "mono8"
    msg.is_bigendian = 0
    msg.step = msg.width
    msg.data = mask_u8.tobytes()
    return msg


class Sam3MaskNode(Node):
    """Consume the latest image and publish a union mask and best score."""

    def __init__(self):
        super().__init__("sam3_mask_node")
        defaults = {
            "image_topic": "/image_raw",
            "mask_topic": "/sam3/mask",
            "score_topic": "/sam3/score",
            "prompt_topic": "/sam3/prompt",
            "active_prompt_topic": "/sam3/active_prompt",
            "prompt": "glasses",
            "model_id": "facebook/sam3",
            "model_revision": "",
            "local_files_only": False,
            "device": "cpu",
            "use_amp": True,
            "score_th": 0.3,
            "relative_score_th": 0.2,
            "max_instances": 16,
            "mask_th": 0.5,
            "max_side": 640,
            "infer_hz": 0.5,
            "prompt_republish_sec": 1.0,
        }
        for name, default in defaults.items():
            self.declare_parameter(name, default, ParameterDescriptor(read_only=True))
            setattr(self, name, self.get_parameter(name).value)
        self._validate_parameters()
        self.prompt = self.prompt.strip()
        self._prompt_lock = threading.RLock()
        self._prompt_generation = 0
        self._stop = threading.Event()
        self._last_status_log_time = 0.0
        self.q = queue.Queue(maxsize=1)

        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        device = torch.device(self.device)
        if device.type not in {"cpu", "cuda"}:
            raise ValueError("device must be cpu, auto, cuda, or cuda:N")
        if device.type == "cuda" and not torch.cuda.is_available():
            self.get_logger().warning("CUDA unavailable; falling back to CPU")
            self.device = "cpu"
            device = torch.device("cpu")
        self._cuda = device.type == "cuda"

        self.get_logger().info(f"Loading {self.model_id} on {self.device} ...")
        load_options = {"local_files_only": self.local_files_only}
        if self.model_revision:
            load_options["revision"] = self.model_revision
        self.model = Sam3Model.from_pretrained(self.model_id, **load_options).to(self.device)
        self.processor = Sam3Processor.from_pretrained(self.model_id, **load_options)
        self.model.eval()
        if self._cuda:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        image_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        # A volatile subscription accepts both ordinary CLI publishers and
        # transient-local publishers. An active prompt is separately latched.
        prompt_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        active_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.sub = self.create_subscription(Image, self.image_topic, self.on_image, image_qos)
        self.sub_prompt = self.create_subscription(
            String, self.prompt_topic, self.on_prompt, prompt_qos,
        )
        self.pub_mask = self.create_publisher(Image, self.mask_topic, 1)
        self.pub_score = self.create_publisher(Float32, self.score_topic, 1)
        self.pub_active_prompt = self.create_publisher(String, self.active_prompt_topic, active_qos)
        if self.prompt_republish_sec > 0.0:
            self.prompt_timer = self.create_timer(self.prompt_republish_sec, self.publish_prompt)
        self.publish_prompt()
        self.worker = threading.Thread(target=self.infer_loop, daemon=True)
        self.worker.start()
        self.get_logger().info(
            f"Subscribed: {self.image_topic} + {self.prompt_topic} | "
            f"Publishing: {self.mask_topic} + {self.score_topic} | infer_hz={self.infer_hz}"
        )

    def _validate_parameters(self):
        for name in ("score_th", "relative_score_th", "mask_th"):
            if not math.isfinite(getattr(self, name)) or not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not math.isfinite(self.infer_hz) or self.infer_hz <= 0:
            raise ValueError("infer_hz must be positive")
        if self.max_side < 1 or self.max_instances < 1:
            raise ValueError("max_side and max_instances must be positive")
        if not self.prompt.strip() or not self.model_id.strip():
            raise ValueError("prompt and model_id must not be empty")
        if not math.isfinite(self.prompt_republish_sec) or self.prompt_republish_sec < 0:
            raise ValueError("prompt_republish_sec must be nonnegative")

    def on_prompt(self, msg: String):
        """Switch the prompt and invalidate any inference already in flight."""
        new_prompt = msg.data.strip()
        with self._prompt_lock:
            if not new_prompt or new_prompt == self.prompt:
                return
            self.prompt = new_prompt
            self._prompt_generation += 1
            self.get_logger().info(f"Updated prompt: {self.prompt}")
            self.publish_prompt()

    def publish_prompt(self):
        """Broadcast the current prompt, including to late subscribers."""
        with self._prompt_lock:
            self.pub_active_prompt.publish(String(data=self.prompt))

    def on_image(self, msg: Image):
        """Replace the queued frame; reject malformed or unsupported images."""
        try:
            rgb = imgmsg_to_rgb(msg)
        except ValueError as exc:
            self.get_logger().warning(str(exc), throttle_duration_sec=5.0)
            return
        try:
            self.q.get_nowait()
        except queue.Empty:
            pass
        self.q.put_nowait((rgb, msg.header))

    def _log_status(self, message: str):
        now = time.monotonic()
        if now - self._last_status_log_time >= 2.0:
            self._last_status_log_time = now
            self.get_logger().info(message)

    def infer_loop(self):
        """Run inference at a bounded rate without building a frame backlog."""
        period = 1.0 / self.infer_hz
        last_run = -period
        while not self._stop.is_set() and rclpy.ok(context=self.context):
            if self._stop.wait(max(0.0, period - (time.monotonic() - last_run))):
                break
            try:
                rgb, header = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            last_run = time.monotonic()
            try:
                with self._prompt_lock:
                    inference_prompt = self.prompt
                    generation = self._prompt_generation
                rgb_small, (orig_h, orig_w) = resize_keep_aspect(rgb, self.max_side)
                inputs = self.processor(
                    images=PILImage.fromarray(rgb_small), text=inference_prompt,
                    return_tensors="pt",
                ).to(self.device)
                amp = (
                    torch.autocast("cuda", dtype=torch.float16)
                    if self._cuda and self.use_amp else nullcontext()
                )
                with torch.inference_mode(), amp:
                    outputs = self.model(**inputs)
                result = self.processor.post_process_instance_segmentation(
                    outputs, threshold=0.0, mask_threshold=self.mask_th,
                    target_sizes=inputs.get("original_sizes").tolist(),
                )[0]
                masks = result["masks"].detach().cpu().numpy()
                scores = result["scores"].detach().cpu().numpy()
                selected = select_instance_indices(
                    scores, absolute_threshold=self.score_th,
                    relative_threshold=self.relative_score_th, max_instances=self.max_instances,
                )
                if selected.size:
                    mask = np.any(masks[selected] > 0, axis=0).astype(np.uint8) * 255
                else:
                    mask = np.zeros(rgb_small.shape[:2], dtype=np.uint8)
                if mask.shape != (orig_h, orig_w):
                    mask = np.array(PILImage.fromarray(mask).resize(
                        (orig_w, orig_h), resample=PILImage.Resampling.NEAREST,
                    ))
                best_score = float(np.max(scores)) if scores.size else 0.0
                # Hold the prompt lock through publication, so an accepted new
                # prompt can never be followed by an old prompt's result. A
                # generation counter also detects changes A -> B -> A.
                with self._prompt_lock:
                    if self._stop.is_set() or generation != self._prompt_generation:
                        continue
                    self.pub_score.publish(Float32(data=best_score))
                    self.pub_mask.publish(mask_to_imgmsg(mask, header))
                self._log_status(
                    f"prompt={inference_prompt!r} union_masks={selected.size} "
                    f"best_score={best_score:.3f} area={np.count_nonzero(mask)}"
                )
            except Exception as exc:
                if not self._stop.is_set():
                    self.get_logger().error(f"Inference failed: {exc!r}")
                    self._stop.wait(0.2)

    def destroy_node(self):
        """Stop the inference worker before tearing down ROS publishers."""
        self._stop.set()
        if hasattr(self, "worker"):
            self.worker.join(timeout=5.0)
        return super().destroy_node()


def main(args=None):
    """Run the node with graceful cleanup on shutdown and loading errors."""
    rclpy.init(args=args)
    node = None
    try:
        node = Sam3MaskNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
