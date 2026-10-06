#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Usage: setup.sh [cpu|cuda] [workspace]
set -eo pipefail
mode="${1:-cpu}"
workspace="${2:-$HOME/sam3_ws}"
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ros_distro="${ROS_DISTRO:-humble}"
venv_dir="${SAM3_VENV:-$workspace/.venv}"
case "$mode" in
  cpu) torch_index=https://download.pytorch.org/whl/cpu ;;
  cuda) torch_index=https://download.pytorch.org/whl/cu128 ;;
  *) echo "Usage: $0 [cpu|cuda] [workspace]" >&2; exit 2 ;;
esac
if [[ ! -f "/opt/ros/$ros_distro/setup.bash" ]]; then
  echo "Install ROS 2 $ros_distro first; see docs/deployment.md." >&2
  exit 1
fi
source "/opt/ros/$ros_distro/setup.bash"
mkdir -p "$workspace/src"
package_path="$workspace/src/sam3_ros"
if [[ -e "$package_path" || -L "$package_path" ]]; then
  if [[ "$(realpath "$package_path")" != "$repo_dir" ]]; then
    echo "$package_path already points to another checkout; choose a different workspace." >&2
    exit 1
  fi
else
  ln -s "$repo_dir" "$package_path"
fi
"${SAM3_PYTHON:-/usr/bin/python3}" -m venv --system-site-packages "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install torch==2.10.0 torchvision==0.25.0 --index-url "$torch_index"
"$venv_dir/bin/python" -m pip install -r "$repo_dir/requirements.txt"
"$venv_dir/bin/python" -c 'import rclpy; from transformers import Sam3Model, Sam3Processor'
cd "$workspace"
# Use the venv interpreter for colcon so installed node shebangs use it too.
"$venv_dir/bin/python" -m colcon build --symlink-install --packages-select sam3_ros
echo "Built sam3_ros. In each new terminal:"
printf 'source /opt/ros/%s/setup.bash\n' "$ros_distro"
printf 'source %q/bin/activate\n' "$venv_dir"
printf 'source %q/install/local_setup.bash\n' "$workspace"
