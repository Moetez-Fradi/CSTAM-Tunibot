#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Range, LaserScan
import time
import sys
class UltrasonicVerifier(Node):
    def __init__(self):
        super().__init__('ultrasonic_verifier')
        self.publisher = self.create_publisher(Range, '/ultrasonic_sensor/range', 10)
        self.subscription = self.create_subscription(LaserScan, '/ultrasonic_sensor/scan', self.scan_callback, 10)
        self.scan_received = False
        self.get_logger().info("Verifier Started. Waiting for existing driver or mocking data...")
    def scan_callback(self, msg):
        self.get_logger().info(f"SUCCESS: Received LaserScan! Frame: {msg.header.frame_id}, Ranges: {len(msg.ranges)}")
        self.scan_received = True
        sys.exit(0)
    def publish_mock_data(self):
        msg = Range()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "ultrasonic_link"
        msg.radiation_type = Range.ULTRASOUND
        msg.field_of_view = 0.5
        msg.min_range = 0.02
        msg.max_range = 2.0
        msg.range = 0.5 
        self.get_logger().info("Publishing Mock Range: 0.5m")
        self.publisher.publish(msg)
def main(args=None):
    rclpy.init(args=args)
    node = UltrasonicVerifier()
    for _ in range(5):
        rclpy.spin_once(node, timeout_sec=0.5)
        if node.scan_received:
            return
    node.get_logger().info("No scan received from hardware. Injecting mock data...")
    for _ in range(5):
        node.publish_mock_data()
        rclpy.spin_once(node, timeout_sec=0.5)
        if node.scan_received:
            return
    node.get_logger().error("FAILURE: No LaserScan received after timeout.")
    sys.exit(1)
if __name__ == '__main__':
    main()
