FROM ros:humble-ros-base-jammy
SHELL ["/bin/bash", "-c"]
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-venv python3-pip python3-colcon-common-extensions \
    ros-humble-launch-ros ros-humble-ament-index-python \
    ros-humble-sensor-msgs ros-humble-std-msgs \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/sam3-venv
COPY requirements.txt /tmp/sam3-requirements.txt
RUN /opt/sam3-venv/bin/python -m pip install --upgrade pip \
    && /opt/sam3-venv/bin/python -m pip install \
       torch==2.10.0 torchvision==0.25.0 --index-url "$TORCH_INDEX_URL" \
    && /opt/sam3-venv/bin/python -m pip install -r /tmp/sam3-requirements.txt
COPY . /ws/src/sam3_ros
WORKDIR /ws
RUN source /opt/ros/humble/setup.bash \
    && /opt/sam3-venv/bin/python -m colcon build --packages-select sam3_ros
COPY docker/entrypoint.sh /usr/local/bin/sam3-entrypoint
RUN chmod +x /usr/local/bin/sam3-entrypoint
ENV HF_HOME=/models/huggingface
ENTRYPOINT ["/usr/local/bin/sam3-entrypoint"]
CMD ["ros2", "launch", "sam3_ros", "sam3.launch.py", "device:=auto"]
