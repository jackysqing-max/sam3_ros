# SPDX-License-Identifier: Apache-2.0
"""Image conversion helpers independent of ROS and model dependencies."""

import numpy as np
from PIL import Image as PILImage


def imgmsg_to_rgb(msg) -> np.ndarray:
    """Decode rgb8/bgr8 images, including row padding, into packed RGB."""
    encoding = msg.encoding.lower()
    if encoding not in {"rgb8", "bgr8"}:
        raise ValueError(f"Unsupported image encoding {msg.encoding!r}; use rgb8 or bgr8")
    height, width, step = int(msg.height), int(msg.width), int(msg.step)
    if height <= 0 or width <= 0 or step < width * 3:
        raise ValueError("Invalid image dimensions or row stride")
    data = np.frombuffer(msg.data, dtype=np.uint8)
    if data.size != height * step:
        raise ValueError("Image data length does not match height * step")
    rgb = data.reshape(height, step)[:, :width * 3].reshape(height, width, 3)
    if encoding == "bgr8":
        rgb = rgb[:, :, ::-1]
    return rgb.copy()


def resize_keep_aspect(rgb: np.ndarray, max_side: int):
    """Limit the longest input side and return the original (height, width)."""
    if max_side < 1:
        raise ValueError("max_side must be positive")
    height, width = rgb.shape[:2]
    if max(height, width) <= max_side:
        return rgb, (height, width)
    scale = max_side / float(max(height, width))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return np.array(PILImage.fromarray(rgb).resize(size)), (height, width)
