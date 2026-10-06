# Deployment

## Native installation

Follow [README](../README.md) for Ubuntu 22.04 + Humble installation. Setup does not
install ROS itself, request gated model access, or modify an existing robot workspace.
Its arguments are `scripts/setup.sh [cpu|cuda] [workspace]`; default mode is `cpu`,
default workspace is `$HOME/sam3_ws`. It refuses to replace another checkout already
at `<workspace>/src/sam3_ros`. `SAM3_VENV` overrides the venv path and `SAM3_PYTHON`
overrides `/usr/bin/python3`; keep the interpreter ABI compatible with ROS.

The direct model dependencies are pinned in `requirements.txt`. Torch and torchvision
are installed separately to select CPU versus CUDA wheels. Transitive dependency
versions are resolved by pip; this is a tested baseline, not a full dependency lock.
No system CUDA toolkit installation is needed to use the binary PyTorch wheels.

## Models and offline operation

Accept the access terms and obtain authorization at
[facebook/sam3](https://huggingface.co/facebook/sam3), then use `hf auth login` or
an externally supplied `HF_TOKEN`. The wrapper relies on Hugging Face's normal
authentication and cache lookup. Credentials do not belong in ROS YAML or Git.

```bash
python scripts/download_model.py --output "$HOME/models/sam3"
ros2 launch sam3_ros sam3.launch.py \
  model_id:="$HOME/models/sam3" local_files_only:=true device:=cuda
```

`model_id` accepts either a Hugging Face model ID or a local Transformers model
directory containing model, processor, and tokenizer files. A lone Meta `.pt`
checkpoint cannot be loaded as this directory. To reproduce a particular Hugging Face
snapshot, supply the same immutable revision to both download and launch:

```bash
python scripts/download_model.py --revision YOUR_MODEL_COMMIT
ros2 launch sam3_ros sam3.launch.py \
  model_revision:=YOUR_MODEL_COMMIT local_files_only:=true device:=cuda
```

`HF_HOME` controls the cache location. Runtime `local_files_only:=true` disables
model downloads. Copy local directories separately from the open-source repository.

## Docker on Linux

Requires Docker Engine; CUDA containers additionally need a compatible NVIDIA
driver and NVIDIA Container Toolkit. Host networking and IPC let the container
communicate with local ROS image publishers, including Fast DDS shared memory.
Set the same `ROS_DOMAIN_ID` and RMW implementation for the camera and SAM3 process.
This recipe targets native Linux.

Build CUDA or CPU image:

```bash
docker build -t sam3-ros:0.1.0 .
# CPU alternative:
docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu \
  -t sam3-ros:cpu .
```

Use your own predownloaded model directory (read-only mount); no authentication is
required inside the container for this offline case:

```bash
docker run --rm --init --gpus all --network host --ipc host \
  -e ROS_DOMAIN_ID=0 -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -v "$HOME/models/sam3:/models/sam3:ro" \
  sam3-ros:0.1.0 ros2 launch sam3_ros sam3.launch.py \
  device:=cuda model_id:=/models/sam3 local_files_only:=true \
  image_topic:=/camera/color/image_raw prompt:="red cup"
```

CPU: use `sam3-ros:cpu`, omit `--gpus all`, and pass `device:=cpu`.
For custom parameter YAML add a read-only mount and `params_file:=/config/sam3.yaml`.
The image's default command uses `device:=auto`; `docker run` alone uses the gated
online model ID, so it still needs an authorized cache or credentials.

## Docker Compose

The GPU Compose recipe needs Compose **2.30+** (for
[`gpus: all`](https://docs.docker.com/reference/compose-file/services/#gpus)) and
NVIDIA Container Toolkit. It stores the model cache in a named volume, separate
from the repository.

```bash
docker compose build
docker compose run --rm sam3 hf auth login
docker compose run --rm sam3 python /ws/src/sam3_ros/scripts/download_model.py
SAM3_IMAGE_TOPIC=/camera/color/image_raw SAM3_PROMPT="red cup" docker compose up
# Stop and preserve model cache:
docker compose down
```

Interactive login is stored only in the mounted Hugging Face cache volume. To use
offline local weights instead, use the `docker run` recipe above. The Docker recipes
are supplied for deployment; the current validation host does not have Docker, so
container build/runtime have not been exercised there. See [validation](validation.md).

## Integration notes and troubleshooting

| Symptom | Check / action |
| --- | --- |
| `ModuleNotFoundError: rclpy` | Source `/opt/ros/humble/setup.bash`; use its Python 3.10 ABI and a `--system-site-packages` venv. |
| `cannot import Sam3Model` | Run `scripts/check_environment.py`; use the pinned Transformers version. |
| Torch missing under `ros2 run` | Rebuild using the model venv's `python -m colcon`; installed shebangs select the interpreter. |
| HTTP 401/403 or gated repository error | Request model access, accept terms, and authenticate with the authorized account. |
| Offline file lookup fails | Download processor and tokenizer files as well as weights; select the right revision or full local directory. |
| No image callbacks | Match domain/RMW; verify the exact topic; publish raw `rgb8`/`bgr8` `sensor_msgs/Image`. Compressed image transport needs a separate republisher. |
| No masks but scores arrive | Reduce `score_th` if appropriate, inspect the prompt and image. An all-zero mask is a valid below-threshold result. |
| Prompt does not change | Publish `std_msgs/String` on the configured prompt topic. Startup parameters are read-only. |
| CUDA out of memory | Close competing GPU inference jobs, use `use_amp: true`, reduce output image size or use CPU. `max_side` reduces wrapper input/output sizes; the stock processor still resizes internally to the model resolution. |

The node processes at most `infer_hz` start events per second and keeps only the
newest queued frame. Actual throughput is limited by model inference time. It is
image segmentation on a stream, not a SAM video tracker. The `Float32` score has no
timestamp, so do not use arrival ordering as a synchronization contract across topics.
Use the mask header for aligned depth or RGB processing.
