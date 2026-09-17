#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import subprocess
import json
import time
import os
import signal
import cv2

class CameraManager(Node):
    def __init__(self):
        super().__init__('camera_manager')
        
        self.declare_parameter('video_device', 'auto')
        self.device_path = self.get_parameter('video_device').value

        if self.device_path == 'auto':
            self.device_path = self.detect_camera()
            
        self.get_logger().info(f"📷 Camera Manager Initialized. Target Device: {self.device_path}")
        self.get_logger().info("Waiting for arrival to start camera...")

        # Subscriptions c
        self.status_sub = self.create_subscription(
            String, '/app/goal_status', self.on_status, 10
        )
        
        self.like_sub = self.create_subscription(
            Bool, '/like_detected', self.on_like_detected, 10
        )
        
        self.goal_name_sub = self.create_subscription(
            String, '/app/goal_name', self.on_goal_name, 10
        )

        # Process Handle
        self.camera_process = None
        self.is_camera_running = False

    def detect_camera(self):
        """Probe /dev/video* devices to find a working camera."""
        self.get_logger().info("Probing video devices...")
        for i in range(10):
            path = f'/dev/video{i}'
            if os.path.exists(path):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    cap.release()
                    if ret:
                        self.get_logger().info(f"✅ Found working camera at {path}")
                        return path
        self.get_logger().warn("❌ No working camera found. Defaulting to /dev/video0")
        return '/dev/video0'

    def start_camera(self):
        if self.is_camera_running:
            return

        self.get_logger().info(f"🚀 Starting Webcam on {self.device_path}...")
        
        cmd = [
            'ros2', 'run', 'v4l2_camera', 'v4l2_camera_node',
            '--ros-args',
            '-r', 'image_raw:=/webcam/image_raw',
            '-p', f'video_device:={self.device_path}',
            '-p', 'image_size:=[640,480]'
        ]
        
        try:
            # excessive logic to ensure cleanup? usually Popen is enough if we track it
            self.camera_process = subprocess.Popen(cmd)
            self.is_camera_running = True
            self.get_logger().info("✅ Webcam Node Started!")
        except Exception as e:
            self.get_logger().error(f"Failed to start camera: {e}")

    def stop_camera(self):
        if not self.is_camera_running or self.camera_process is None:
            return

        self.get_logger().info("🛑 Stopping Webcam...")
        
        try:
            self.camera_process.terminate()
            try:
                self.camera_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.camera_process.kill()
                
            self.is_camera_running = False
            self.camera_process = None
            self.get_logger().info("✅ Webcam Node Stopped.")
        except Exception as e:
            self.get_logger().error(f"Error stopping camera: {e}")

    def on_status(self, msg):
        try:
            data = json.loads(msg.data)
            arrived = data.get('arrived', False)
        except:
            arrived = 'arrived' in msg.data or 'succeeded' in msg.data
            
        if arrived:
            # We arrived! Turn on camera
            self.start_camera()

    def on_like_detected(self, msg):
        if msg.data:
            self.get_logger().info("👍 Like Detected! Mission Complete. Turning off camera in 5s...")
            # Wait a bit to show the "Success" UI for a moment if needed, or kill immediately?
            # User said "Close and open YOLO" -> YOLO runs, detects like, then we are done.
            # If we kill camera immediately, YOLO might complain or just stop receiving.
            # Let's verify: YOLO creates its own sub. It needs the camera.
            # WAIT! If I kill the camera node, YOLO stops working.
            # BUT YOLO is the one detecting the Like.
            # So once Like is detected, we are DONE.
            # So yes, we can kill it.
            
            # Use a timer to delay kill slightly so we don't cut the feed abruptly on the very frame of detection
            # self.create_timer(2.0, self.stop_camera_callback)
            # Actually simplest is just stop.
            self.stop_camera()

    def on_goal_name(self, msg):
        # If goal changes (robopt moving to new place), kill camera
        self.get_logger().info(f"📍 New Goal: {msg.data} - Ensuring camera is OFF.")
        self.stop_camera()

def main(args=None):
    rclpy.init(args=args)
    node = CameraManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_camera()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
