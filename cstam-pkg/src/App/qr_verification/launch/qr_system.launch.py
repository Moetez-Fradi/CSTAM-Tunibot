from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # Get package path
    # pkg_share = get_package_share_directory('qr_verification')
    
    # Declare Arguments
    use_webcam_arg = DeclareLaunchArgument(
        'use_webcam',
        default_value='False',
        description='Enable laptop webcam for simulation mode'
    )
    
    # Nodes
    qr_scanner = Node(
        package='qr_verification',
        executable='qr_scanner',
        name='qr_scanner',
        output='screen',
        parameters=[{
            'use_webcam': LaunchConfiguration('use_webcam'),
            'mission_root_path': os.path.expanduser('~/ws/src/App/order_logger/missions'), # Can also use substitution if needed
            'audio_assets_path': os.path.expanduser('~/ws/src/App/audio_assets')
        }]
    )

    qr_generator = Node(
        package='qr_verification',
        executable='qr_generator',
        name='qr_generator',
        output='screen',
        parameters=[{
            'mission_root': os.path.expanduser('~/ws/src/App/order_logger/missions'),
            'order_history_path': os.path.expanduser('~/ws/src/App/order_logger/dashboard/order_history.txt')
        }]
    )

    return LaunchDescription([
        use_webcam_arg,
        qr_scanner,
        qr_generator
    ])
