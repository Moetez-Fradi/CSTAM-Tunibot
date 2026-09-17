import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition
from nav2_common.launch import ReplaceString
def get_auto_camera_device():
    """Probe /dev/video* devices to find a working camera."""
    import cv2
    import os
    print("[AutoDetect] Searching for working webcam...")
    for i in range(10): 
        path = f'/dev/video{i}'
        if os.path.exists(path):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    if ret:
                        print(f"[AutoDetect] Found working camera at {path}")
                        return path
            except:
                pass
    print("[AutoDetect] No working camera found, defaulting to /dev/video1")
    return '/dev/video1'
def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    bridge_config_file_path = os.path.join(pkg_andino_gz, 'config', 'bridge_config.yaml')
    entity_arg = DeclareLaunchArgument(
        'entity', default_value='andino', description='Name of the entity to bridge with Gazebo.')
    use_webcam_arg = DeclareLaunchArgument(
        'use_webcam', default_value='true', description='Use laptop webcam for compressed stream (QR/YOLO)')
    use_webcam = LaunchConfiguration('use_webcam')
    detected_device = get_auto_camera_device()
    bridge_config = ReplaceString(
        source_file=bridge_config_file_path,
        replacements={'<entity>': LaunchConfiguration('entity')},
    )
    bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        parameters=[{
            'config_file': bridge_config
        }],
    )
    webcam_node = Node(
        condition=IfCondition(use_webcam),
        package='v4l2_camera',
        executable='v4l2_camera_node',
        output='screen',
        parameters=[{
            'video_device': detected_device,
            'image_size': [640, 480],
            'pixel_format': 'mjpeg'
        }],
        respawn=True,
        respawn_delay=2.0,
        remappings=[
            ('image_raw', '/webcam/image_raw')
        ]
    )
    sim_compression_node = Node(
        condition=IfCondition(PythonExpression(['not ', use_webcam])),
        package='image_transport',
        executable='republish',
        arguments=['raw', 'compressed'],
        remappings=[
            ('in', 'camera/image_raw'),
            ('out/compressed', 'camera/image_raw/compressed')
        ],
        output='screen'
    )
    webcam_compression_node = Node(
        condition=IfCondition(use_webcam),
        package='image_transport',
        executable='republish',
        arguments=['raw', 'compressed'],
        remappings=[
            ('in', '/webcam/image_raw'),
            ('out/compressed', 'camera/image_raw/compressed')
        ],
        output='screen'
    )
    return LaunchDescription([
        entity_arg,
        use_webcam_arg,
        bridge_node,
        webcam_node,
        sim_compression_node,
        webcam_compression_node,
    ])
