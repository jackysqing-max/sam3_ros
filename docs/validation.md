# Validation record

Recorded **2026-10-06** (Europe/Rome) for the v0.1.0 extraction.

## Environment

| Component | Observed version |
| --- | --- |
| ROS | ROS 2 Humble |
| Python | 3.10.12, venv with system site packages |
| PyTorch | 2.10.0+cu128 |
| torchvision | 0.25.0+cu128 |
| Transformers | 5.2.0 |
| NumPy / Pillow | 1.26.4 / 12.1.1 |
| GPU | NVIDIA GeForce RTX 5080 Laptop GPU, 16 GiB |
| Model | `facebook/sam3`, cached revision `3c879f39826c281e95690f02c7821c4de09afae7` |

## Checks completed

- `python -m pytest -q`: **16 passed**. Tests cover confidence selection, empty
  detections, limits, RGB/BGR row padding, malformed image rejection, resizing,
  and very thin images.
- `colcon test` / `colcon test-result`: **16 tests, 0 errors, 0 failures, 0 skipped**.
- Python compilation, shell syntax, ROS parameter YAML and Compose YAML parsing.
- Independent `python -m colcon build --packages-select sam3_ros`: successful.
  No robot-workspace overlay was sourced. The installed node shebang points to
  the model environment's Python interpreter.
- `ros2 pkg executables sam3_ros`: both segmentation and image-file executables registered.
- Installed `ros2 launch sam3_ros sam3.launch.py --show-args`: successful.
- Real GPU smoke test via the **installed launch file**, with cached model weights,
  `local_files_only:=true`, and an isolated ROS domain: **passed**.
- Custom YAML with `score_th: 1.0`: both masks correctly became empty while best
  confidences remained positive (0.9663 / 0.9785). Launch overrides preserved the
  YAML threshold, validating the below-threshold output contract.
- Installed image-file publisher: emitted the expected RGB pixels, dimensions,
  encoding, and frame ID from a temporary synthetic PNG in a separate ROS domain.

The smoke test publishes synthetic **800 × 480 padded BGR** images with a red
square and blue circle. The wrapper's 640-pixel preprocessing limit exercises mask
restoration to original dimensions. Both masks are binary `mono8` and preserve the
published source frame ID and exact timestamp.

| Prompt | Foreground pixels | Best confidence |
| --- | ---: | ---: |
| `red square` | 40,003 | 0.9663 |
| `blue circle` after a volatile prompt-topic update | 41,604 | 0.9785 |

The test stops its own launch process and probe after completion. Reproduce using
an authorized cached snapshot and the sourced ROS/install environment:

```bash
python scripts/smoke_test.py --device cuda --local-files-only \
  --model-revision 3c879f39826c281e95690f02c7821c4de09afae7 --require-mask
```

## Coverage limits

- The native tests use an existing working model venv. The setup script's full
  installation from a blank host was not performed.
- Docker is unavailable on the validation host. Container build, Compose GPU
  allocation, NVIDIA Container Toolkit, and container-to-host DDS are untested.
- No real camera, robot motion, depth fusion, video tracking, or other ROS
  distribution is part of this extraction's runtime acceptance.
- Public CI runs unit tests and a Humble package build without gated model weights.
  It does not provide a GPU-model acceptance result.
- Measurements above are functional checks, not a segmentation accuracy or
  real-time performance benchmark; models and hardware can change the values.
