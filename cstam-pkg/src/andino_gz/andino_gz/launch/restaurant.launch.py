"""Launch the Sweet Home 3D restaurant scene with the CSTAM robot."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    package_share = get_package_share_directory('andino_gz')
    robot_x = LaunchConfiguration('robot_x')
    robot_y = LaunchConfiguration('robot_y')
    robot_z = LaunchConfiguration('robot_z')
    robot_yaw = LaunchConfiguration('robot_yaw')
    headless = LaunchConfiguration('headless')
    autostart = LaunchConfiguration('autostart')
    rviz = LaunchConfiguration('rviz')
    use_webcam = LaunchConfiguration('use_webcam')
    start_app = LaunchConfiguration('start_app')

    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_x', default_value='-8.0',
            description='Initial CSTAM x position in the restaurant world.'),
        DeclareLaunchArgument(
            'robot_y', default_value='-12.0',
            description='Initial CSTAM y position in the restaurant world.'),
        DeclareLaunchArgument(
            'robot_z', default_value='0.02',
            description='Initial CSTAM z position in the restaurant world.'),
        DeclareLaunchArgument(
            'robot_yaw', default_value='0.0',
            description='Initial CSTAM yaw in radians.'),
        DeclareLaunchArgument(
            'headless', default_value='False', choices=['True', 'False'],
            description='Run Gazebo server-only.'),
        DeclareLaunchArgument(
            'autostart', default_value='True', choices=['True', 'False'],
            description='Start Gazebo immediately.'),
        DeclareLaunchArgument(
            'rviz', default_value='False', choices=['True', 'False'],
            description='Start the environment RViz view.'),
        DeclareLaunchArgument(
            'use_webcam', default_value='False',
            description='Start the optional host webcam bridge.'),
        DeclareLaunchArgument(
            'start_app', default_value='False',
            description='Start the optional application layer.'),
        # This must be set before the nested Gazebo launch begins.  Gazebo uses
        # it to resolve model://restaurant from worlds/restaurant.sdf.
        SetEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=os.path.join(package_share, 'models') + ':' +
                  os.environ.get('GZ_SIM_RESOURCE_PATH', ''),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(package_share, 'launch', 'andino_gz.launch.py')
            ),
            launch_arguments={
                'world_name': 'restaurant.sdf',
                'gui_config': 'restaurant.config',
                # The defaults start in the clear area south-west of the
                # dining tables. Override robot_x/y/z/yaw at launch time.
                'robots': TextJoin(substitutions=[
                    'cstam={x: ', robot_x,
                    ', y: ', robot_y,
                    ', z: ', robot_z,
                    ', yaw: ', robot_yaw,
                    '};',
                ]),
                'robot_type': 'cstam',
                'nav2': 'False',
                'rviz': rviz,
                'autostart': autostart,
                'headless': headless,
                'use_webcam': use_webcam,
                'start_app': start_app,
            }.items(),
        )
    ])
