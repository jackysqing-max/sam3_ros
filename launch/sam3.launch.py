# SPDX-License-Identifier: Apache-2.0
"""Launch the standalone segmentation node with optional parameter overrides."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    """Expose common deployment settings; leave tuning in the YAML file."""
    declarations = [DeclareLaunchArgument(
        "params_file", default_value=get_package_share_directory("sam3_ros") + "/config/sam3.yaml",
        description="ROS parameter YAML (all startup parameters are supported)",
    )]
    overrides = {}
    for name, value_type in (
        ("image_topic", str), ("mask_topic", str), ("score_topic", str),
        ("prompt_topic", str), ("active_prompt_topic", str), ("prompt", str),
        ("device", str), ("model_id", str), ("model_revision", str),
        ("local_files_only", bool), ("infer_hz", float),
    ):
        # Empty arguments preserve the value from params_file.
        declarations.append(DeclareLaunchArgument(name, default_value=""))
        overrides[name] = value_type
    declarations.append(DeclareLaunchArgument("namespace", default_value=""))

    def launch_node(context):
        parameters = {}
        for name, value_type in overrides.items():
            value = LaunchConfiguration(name).perform(context)
            if value:
                parameters[name] = ParameterValue(LaunchConfiguration(name), value_type=value_type)
        return [Node(
            package="sam3_ros", executable="sam3_mask_node", name="sam3_mask_node",
            namespace=LaunchConfiguration("namespace"), output="screen",
            parameters=[LaunchConfiguration("params_file"), parameters],
        )]

    return LaunchDescription(declarations + [OpaqueFunction(function=launch_node)])
