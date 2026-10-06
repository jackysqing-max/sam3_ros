#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check ROS and model imports before downloading or starting SAM3."""

import importlib.metadata
import sys


def main():
    """Report the interpreter, dependency versions, and CUDA availability."""
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    for package in ("torch", "torchvision", "transformers", "numpy", "Pillow"):
        print(f"{package}: {importlib.metadata.version(package)}")
    import rclpy
    import torch
    from transformers import Sam3Model, Sam3Processor

    assert rclpy and Sam3Model and Sam3Processor
    print(f"CUDA available: {torch.cuda.is_available()} (wheel CUDA: {torch.version.cuda})")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print("ROS and SAM3 imports: OK")


if __name__ == "__main__":
    main()
