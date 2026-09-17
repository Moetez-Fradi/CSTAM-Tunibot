"""Launch the Sweet Home 3D restaurant scene with the existing Andino stack."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    package_share = get_package_share_directory('andino_gz')
    return LaunchDescription([
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
                # The centre of the imported building is at the Gazebo origin.
                # Start in the clear area south-west of the dining tables.
                'robots': 'andino={x: -8.0, y: -12.0, z: 0.10, yaw: 0.0};',
                'nav2': 'False',
                'rviz': 'False',
                'autostart': 'True',
            }.items(),
        )
    ])
