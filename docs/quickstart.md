# sam3_ros: A standalone ROS 2 SAM3 vision module

[Full guide](../README.md) · [Deployment](deployment.md) ·
[Topics and parameters](interfaces.md) · [Validation record](validation.md)

The general-purpose `sam3_ros` segmentation node was extracted from
`vla_simu_workspace` and packaged as an independent open-source `ament_python`
package. It takes ROS color images and text prompts, then publishes binary masks,
confidence scores, and the active prompt. Use it in another ROS 2 project without
starting a robot controller, PyBullet, an LLM, or the experiment benchmark.

## Included components

- `sam3_mask_node`: Text-guided SAM3 inference that preserves the source image
  dimensions, timestamp, and frame ID.
- `sam3_image_file_node`: Republish a local image for camera-free demonstrations.
- `launch/sam3.launch.py` and `config/sam3.yaml`: Launch and parameter configuration.
- `scripts/setup.sh`: Create a ROS-compatible virtual environment, install
  CPU/CUDA dependencies, and build the package.
- Model download, environment checks, a real-model ROS smoke test, and GitHub Actions.
- Dockerfile, Compose configuration, Apache-2.0 licensing, and upstream attribution.

## Recommended environment

The validated baseline is Ubuntu 22.04, ROS 2 Humble, Python 3.10, PyTorch 2.10.0,
torchvision 0.25.0, and Transformers 5.2.0. CUDA deployment uses cu128 wheels and
requires a compatible NVIDIA driver. This package loads SAM3 through Transformers;
it does not require Meta's separate Python 3.12 SAM3 environment.

For a first deployment, install ROS 2 Humble, then run:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-colcon-common-extensions \
  ros-humble-launch-ros ros-humble-ament-index-python \
  ros-humble-sensor-msgs ros-humble-std-msgs

mkdir -p "$HOME/sam3_ws/src"
git clone https://github.com/jackysqing-max/sam3_ros.git "$HOME/sam3_ws/src/sam3_ros"
cd "$HOME/sam3_ws/src/sam3_ros"
./scripts/setup.sh cuda "$HOME/sam3_ws"

source /opt/ros/humble/setup.bash
source "$HOME/sam3_ws/.venv/bin/activate"
source "$HOME/sam3_ws/install/local_setup.bash"
python scripts/check_environment.py
```

Use `cpu` instead of `cuda` when no GPU is available. Source the three environment
files shown above in every new terminal.

Request access and accept the terms at
[facebook/sam3](https://huggingface.co/facebook/sam3). Once authorized, authenticate,
download the model, and start the node:

```bash
hf auth login
python scripts/download_model.py
ros2 launch sam3_ros sam3.launch.py \
  device:=cuda image_topic:=/camera/color/image_raw prompt:="red cup"
```

Change the target from another terminal:

```bash
ros2 topic pub --once /sam3/prompt std_msgs/msg/String "{data: 'blue cup'}"
```

Input images support `rgb8` and `bgr8`, including row padding. `/sam3/mask` is a
`mono8` image with values 0 or 255, combining the retained instance masks into one
foreground mask. `/sam3/score` is the highest model confidence, including when it
falls below the mask threshold. `/sam3/active_prompt` lets late subscribers read
the current prompt.

## Offline deployment and verification

```bash
python scripts/download_model.py --output "$HOME/models/sam3"
ros2 launch sam3_ros sam3.launch.py \
  model_id:="$HOME/models/sam3" local_files_only:=true device:=cuda

# Check the real model, image conversion, topics, and prompt switching in ROS domain 97:
python scripts/smoke_test.py --device cuda --local-files-only --require-mask
```

For custom parameters, copy `config/sam3.yaml`, edit it, and load it with
`params_file:=/absolute/path/sam3.yaml`. In an existing ROS workspace, clone this
repository into `src/sam3_ros` and run
`python -m colcon build --symlink-install --packages-select sam3_ros` using a
Python 3.10 virtual environment that contains the model dependencies. For multiple
instances, configure separate input, output, and prompt topics; a namespace alone
does not change the default absolute topic names.

The repository uses the original ROS package's Apache-2.0 license. SAM3 models
follow Meta's own license. Model weights, tokens, recordings, and experiment
materials are obtained separately. Docker deployment recipes are included;
completed checks and coverage limits are documented in the validation record.
