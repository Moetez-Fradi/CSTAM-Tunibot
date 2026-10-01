"""Launch the CSTAM robot in the repository's local office environment."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    package_share = get_package_share_directory('andino_gz')
    return LaunchDescription([
        DeclareLaunchArgument(
            'headless', default_value='False', choices=['True', 'False'],
            description='Run Gazebo server-only for terminal-only sessions.',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(package_share, 'launch', 'andino_gz.launch.py')
            ),
            launch_arguments={
                'world_name': 'office.sdf',
                'map': 'office',
                'robots': 'cstam={x: 0.0, y: 0.0, z: 0.02, yaw: 0.0};',
                'robot_type': 'cstam',
                'nav2': 'False',
                'rviz': 'False',
                'autostart': 'True',
                'headless': LaunchConfiguration('headless'),
            }.items(),
        )
    ])
