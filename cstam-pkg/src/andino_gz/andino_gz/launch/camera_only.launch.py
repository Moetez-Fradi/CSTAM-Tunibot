import os
import time
import cv2
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import TimerAction
def find_working_camera():
    """Returns the first working /dev/video* camera."""
    for i in range(10):
        device = f"/dev/video{i}"
        if os.path.exists(device):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    if ret:
                        print(f"[AutoDetect] Found working camera at {device}")
                        return device
            except Exception as e:
                print(f"[AutoDetect] Failed on {device}: {e}")
    return None
def make_camera_node():
    device = find_working_camera()
    if device is None:
        print("[AutoDetect] No camera found, defaulting to /dev/video0")
        device = "/dev/video0"
    print(f"🚀 Launching Camera on: {device}")
    return Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        output='screen',
        parameters=[{
            'video_device': device,
            'pixel_format': 'YUYV',          
            'output_encoding': 'yuv422_yuy2',
            'image_size': [640, 480],
            'frame_rate': 30.0,
            'io_method': 'mmap',
            'camera_info_url': ''
        }],
        respawn=True,                       
        respawn_delay=2.0
    )
def generate_launch_description():
    """
    Launch camera node with a TimerAction to auto-retry detection if it crashes.
    """
    return LaunchDescription([
        TimerAction(
            period=2.0,
            actions=[make_camera_node()]
        )
    ])
