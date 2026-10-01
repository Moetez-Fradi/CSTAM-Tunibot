"""Bridge CSTAM Gazebo topics when Gazebo is launched by the environment."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("cstam_robot")
    bridge_config = os.path.join(package_share, "config", "environment_bridge.yaml")

    return LaunchDescription([
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            parameters=[{"config_file": bridge_config}],
            output="screen",
        ),
    ])
