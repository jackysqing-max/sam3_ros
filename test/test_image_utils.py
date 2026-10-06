# SPDX-License-Identifier: Apache-2.0
"""Exercise real camera encoding and stride edge cases without model weights."""

from types import SimpleNamespace

import numpy as np
import pytest

from sam3_ros.image_utils import imgmsg_to_rgb, resize_keep_aspect


@pytest.mark.parametrize("encoding", ["rgb8", "bgr8"])
def test_image_with_row_padding(encoding):
    rgb = np.array([[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]], dtype=np.uint8)
    pixels = rgb if encoding == "rgb8" else rgb[:, :, ::-1]
    padded = np.full((2, 8), 255, dtype=np.uint8)
    padded[:, :6] = pixels.reshape(2, 6)
    msg = SimpleNamespace(height=2, width=2, step=8, encoding=encoding, data=padded.tobytes())
    np.testing.assert_array_equal(imgmsg_to_rgb(msg), rgb)


@pytest.mark.parametrize("encoding", ["mono8", "16UC1", "rgba8"])
def test_unsupported_encoding_is_rejected(encoding):
    with pytest.raises(ValueError, match="Unsupported image encoding"):
        imgmsg_to_rgb(SimpleNamespace(encoding=encoding))


@pytest.mark.parametrize("height,width,step,data", [
    (0, 1, 3, b""), (1, 2, 3, b"123"), (2, 1, 3, b"123"),
])
def test_malformed_image_is_rejected(height, width, step, data):
    with pytest.raises(ValueError):
        imgmsg_to_rgb(SimpleNamespace(
            encoding="rgb8", height=height, width=width, step=step, data=data,
        ))


def test_resize_preserves_aspect_and_original_dimensions():
    image = np.zeros((480, 800, 3), dtype=np.uint8)
    resized, original = resize_keep_aspect(image, 640)
    assert resized.shape == (384, 640, 3)
    assert original == (480, 800)


def test_resize_handles_thin_images():
    resized, _ = resize_keep_aspect(np.zeros((1, 10000, 3), dtype=np.uint8), 640)
    assert resized.shape == (1, 640, 3)


def test_small_image_is_not_upscaled():
    image = np.zeros((100, 120, 3), dtype=np.uint8)
    resized, original = resize_keep_aspect(image, 640)
    assert resized is image
    assert original == (100, 120)
