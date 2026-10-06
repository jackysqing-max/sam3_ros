# sam3_ros：可独立部署的 ROS 2 SAM3 视觉模块

[English](README.md) · [完整部署说明](docs/deployment.md) ·
[接口与参数](docs/interfaces.md) · [验证记录](docs/validation.md)

从现有 `vla_simu_workspace` 中提取通用 `sam3_ros` 分割节点，整理为独立的
`ament_python` 开源包。输入 ROS 彩色图像和文本提示词，输出二值掩膜、置信度和当前提示词，
可以接入其他 ROS 2 项目；无需启动机械臂、PyBullet、LLM 或实验 benchmark。

## 已包含

- `sam3_mask_node`：文本提示词驱动 SAM3 推理，保留原图尺寸、时间戳和坐标系。
- `sam3_image_file_node`：循环发布本地图像，便于无相机演示。
- `launch/sam3.launch.py` 和 `config/sam3.yaml`：启动和参数配置。
- `scripts/setup.sh`：创建兼容 ROS 的虚拟环境、安装 CPU/CUDA 依赖并编译。
- 模型下载、环境检查、真实模型 ROS 冒烟测试和 GitHub Actions。
- Dockerfile、Compose、Apache-2.0 许可证及上游归属说明。

## 推荐环境

已验证基线：Ubuntu 22.04、ROS 2 Humble、Python 3.10、PyTorch 2.10.0、
torchvision 0.25.0、Transformers 5.2.0。CUDA 部署使用 cu128 wheel，需要兼容的 NVIDIA 驱动。
该包通过 Transformers 加载模型，无需安装 Meta 官方 Python 3.12 的 SAM3 环境。

首次部署先安装 ROS 2 Humble，然后执行：

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

没有 GPU 时将 `cuda` 改为 `cpu`。每个新终端都需要加载以上三个环境文件。

SAM3 权重需要使用者自行前往 [facebook/sam3](https://huggingface.co/facebook/sam3)
申请访问并接受条款。获批后登录、下载并启动：

```bash
hf auth login
python scripts/download_model.py
ros2 launch sam3_ros sam3.launch.py \
  device:=cuda image_topic:=/camera/color/image_raw prompt:="red cup"
```

其他终端切换识别目标：

```bash
ros2 topic pub --once /sam3/prompt std_msgs/msg/String "{data: 'blue cup'}"
```

图像输入支持 `rgb8` 和 `bgr8`，包括行填充。输出 `/sam3/mask` 为 `mono8`，像素值
0 或 255，是筛选后多个实例掩膜的并集；`/sam3/score` 为模型最高置信度，低于筛选阈值时
仍会发布真实分数；`/sam3/active_prompt` 可供新订阅者读取当前提示词。

## 离线部署与验收

```bash
python scripts/download_model.py --output "$HOME/models/sam3"
ros2 launch sam3_ros sam3.launch.py \
  model_id:="$HOME/models/sam3" local_files_only:=true device:=cuda

# 在独立 ROS 域 97 中启动并检查真实模型、图像转换、话题和提示词切换：
python scripts/smoke_test.py --device cuda --local-files-only --require-mask
```

自定义参数可复制 `config/sam3.yaml` 后通过 `params_file:=/absolute/path/sam3.yaml`
加载。既有 ROS 工作区可直接把本仓库克隆到 `src/sam3_ros`，用包含模型依赖的 Python 3.10
虚拟环境运行 `python -m colcon build --symlink-install --packages-select sam3_ros`。
多个节点并行部署时需要配置各自的输入、输出和提示词话题；仅设置 namespace 不会改变默认绝对话题。

本仓库沿用原 ROS 包的 Apache-2.0 许可。SAM3 模型遵循 Meta 自身许可；模型权重、token、
录制数据和实验材料不随仓库发布。仓库包含 Docker 部署方案；实际已执行的验证及限制见验证记录。
