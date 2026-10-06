#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -eo pipefail
source /opt/ros/humble/setup.bash
source /opt/sam3-venv/bin/activate
source /ws/install/local_setup.bash
exec "$@"
