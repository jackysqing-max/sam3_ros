#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise the installed ROS launch file with real SAM3 and synthetic images."""

import argparse
import math
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import rclpy
from PIL import Image as PILImage
from PIL import ImageDraw
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Float32, String


class Probe(Node):
    """Publish padded BGR input and validate actual ROS output messages."""

    def __init__(self):
        super().__init__("sam3_smoke_probe")
        self.publisher = self.create_publisher(Image, "/sam3_smoke/image", qos_profile_sensor_data)
        self.prompt_pub = self.create_publisher(String, "/sam3_smoke/prompt", 10)
        self.masks = []
        self.scores = []
        self.active_prompt = ""
        self.sub_mask = self.create_subscription(Image, "/sam3_smoke/mask", self.masks.append, 10)
        self.sub_score = self.create_subscription(
            Float32, "/sam3_smoke/score", lambda msg: self.scores.append(msg.data), 10,
        )
        self.sub_active = self.create_subscription(
            String, "/sam3_smoke/active_prompt", self.on_active,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        # Input dimensions deliberately exceed max_side to test mask restoration.
        image = PILImage.new("RGB", (800, 480), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 80, 280, 280), fill="red")
        draw.ellipse((450, 100, 680, 330), fill="blue")
        rgb = np.array(image)
        padded = np.zeros((480, 800 * 3 + 8), dtype=np.uint8)
        padded[:, :2400] = rgb[:, :, ::-1].reshape(480, 2400)
        self.image = Image(height=480, width=800, encoding="bgr8", step=2408)
        self.image.header.frame_id = "sam3_smoke_camera"
        self.image.data = padded.tobytes()
        self.sent_stamps = set()
        self.timer = self.create_timer(0.25, self.publish_image)

    def on_active(self, msg):
        self.active_prompt = msg.data

    def publish_image(self):
        self.image.header.stamp = self.get_clock().now().to_msg()
        stamp = self.image.header.stamp
        self.sent_stamps.add((stamp.sec, stamp.nanosec))
        self.publisher.publish(self.image)

    def wait_for(self, predicate, deadline, process):
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"SAM3 launch exited with code {process.returncode}")
            rclpy.spin_once(self, timeout_sec=0.1)
            if predicate():
                return
        raise TimeoutError("Timed out waiting for SAM3 output")

    def validate_output(self):
        mask = self.masks[-1]
        assert (mask.height, mask.width, mask.step, mask.encoding) == (480, 800, 800, "mono8")
        assert mask.header.frame_id == "sam3_smoke_camera"
        assert (mask.header.stamp.sec, mask.header.stamp.nanosec) in self.sent_stamps
        data = np.frombuffer(mask.data, dtype=np.uint8)
        assert data.size == 480 * 800 and set(np.unique(data)).issubset({0, 255})
        assert all(math.isfinite(score) and 0 <= score <= 1 for score in self.scores)
        return int(np.count_nonzero(data)), float(self.scores[-1])


def main():
    """Launch in an isolated domain, check prompt switching, and clean up."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model-id", default="facebook/sam3")
    parser.add_argument("--model-revision", default="")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--domain-id", type=int, default=97)
    parser.add_argument("--params-file", help="Optional custom ROS parameter YAML")
    parser.add_argument("--require-mask", action="store_true", help="Require nonempty masks for both shapes")
    parser.add_argument("--expect-empty", action="store_true", help="Require empty masks with positive scores")
    args = parser.parse_args()
    if args.require_mask and args.expect_empty:
        parser.error("--require-mask and --expect-empty are mutually exclusive")
    os.environ["ROS_DOMAIN_ID"] = str(args.domain_id)
    os.environ["ROS_LOCALHOST_ONLY"] = "1"
    command = [
        "ros2", "launch", "sam3_ros", "sam3.launch.py", f"device:={args.device}",
        f"model_id:={args.model_id}", f"local_files_only:={str(args.local_files_only).lower()}",
        "prompt:=red square", "infer_hz:=2.0", "image_topic:=/sam3_smoke/image",
        "mask_topic:=/sam3_smoke/mask", "score_topic:=/sam3_smoke/score",
        "prompt_topic:=/sam3_smoke/prompt", "active_prompt_topic:=/sam3_smoke/active_prompt",
    ]
    if args.model_revision:
        command.append(f"model_revision:={args.model_revision}")
    if args.params_file:
        command.append(f"params_file:={Path(args.params_file).resolve()}")
    with tempfile.TemporaryDirectory(prefix="sam3-smoke-") as temp_dir:
        log_path = Path(temp_dir) / "launch.log"
        environment = dict(os.environ, ROS_LOG_DIR=temp_dir)
        with log_path.open("w") as logfile:
            process = subprocess.Popen(
                command, stdout=logfile, stderr=subprocess.STDOUT,
                env=environment, start_new_session=True,
            )
            probe = None
            rclpy.init()
            try:
                probe = Probe()
                deadline = time.monotonic() + args.timeout
                probe.wait_for(
                    lambda: probe.masks and probe.scores and probe.active_prompt == "red square",
                    deadline, process,
                )
                area, score = probe.validate_output()
                if args.require_mask:
                    assert area > 0, "No red square mask"
                if args.expect_empty:
                    assert area == 0 and score > 0, "Expected empty mask and unfiltered positive score"
                print(f"red square: area={area}, score={score:.4f}", flush=True)
                probe.prompt_pub.publish(String(data="blue circle"))
                probe.wait_for(lambda: probe.active_prompt == "blue circle", deadline, process)
                # Wait for a new output stamped after prompt acknowledgement,
                # allowing in-flight messages on independent DDS topics to drain.
                cutoff = probe.get_clock().now().nanoseconds
                previous_masks, previous_scores = len(probe.masks), len(probe.scores)

                def new_output():
                    if len(probe.masks) <= previous_masks or len(probe.scores) <= previous_scores:
                        return False
                    stamp = probe.masks[-1].header.stamp
                    return stamp.sec * 1000000000 + stamp.nanosec >= cutoff

                probe.wait_for(new_output, deadline, process)
                area, score = probe.validate_output()
                if args.require_mask:
                    assert area > 0, "No blue circle mask"
                if args.expect_empty:
                    assert area == 0 and score > 0, "Expected empty mask and unfiltered positive score"
                print(f"blue circle: area={area}, score={score:.4f}", flush=True)
                print("PASS: installed launch, padded BGR, mono8 dimensions/header, scores, prompt switch")
            except Exception:
                print(log_path.read_text(), flush=True)
                raise
            finally:
                if probe is not None:
                    probe.destroy_node()
                if rclpy.ok():
                    rclpy.shutdown()
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)


if __name__ == "__main__":
    main()
