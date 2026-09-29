"""Lifecycle-managed CSTAM mapping launch."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch_ros.actions import LifecycleNode
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory('cstam_phase1'), 'config', 'slam_toolbox.yaml')
    params_file = LaunchConfiguration('slam_params_file')
    node = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        namespace='',
        output='screen',
        parameters=[params_file],
    )
    configure = TimerAction(
        period=3.0,
        actions=[ExecuteProcess(
            cmd=['ros2', 'lifecycle', 'set', '/slam_toolbox', 'configure'],
            output='screen')])
    activate = TimerAction(
        period=5.0,
        actions=[ExecuteProcess(
            cmd=['ros2', 'lifecycle', 'set', '/slam_toolbox', 'activate'],
            output='screen')])
    return LaunchDescription([
        DeclareLaunchArgument(
            'slam_params_file', default_value=default_params,
            description='SLAM Toolbox parameter file.'),
        node,
        configure,
        activate,
    ])
