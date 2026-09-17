#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Range, LaserScan
import math

class RangeToLaserScanNode(Node):
    def __init__(self):
        super().__init__('range_to_laserscan')
        self.declare_parameter('scan_topic', '/ultrasonic_sensor/scan')
        
        self.subscription = self.create_subscription(
            Range,
            '/ultrasonic_broadcaster/range',
            self.range_callback,
            10)
        self.publisher = self.create_publisher(LaserScan, self.get_parameter('scan_topic').value, 10)
        self.get_logger().info('Range to LaserScan converter started.')

    def range_callback(self, msg):
        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = msg.header.frame_id
        
        # FOV of standard Ultrasonic is usually ~15-30 degrees.
        # msg.field_of_view should contain it.
        # We will create a scan with 5 points to cover the cone.
        
        fov = msg.field_of_view
        if fov == 0:
            fov = 0.52 # Default 30 deg if not set
            
        num_readings = 5
        scan.angle_min = -fov / 2.0
        scan.angle_max = fov / 2.0
        scan.angle_increment = fov / (num_readings - 1)
        scan.time_increment = 0.0
        scan.range_min = msg.min_range
        scan.range_max = msg.max_range
        
        # Populate ranges
        current_range = msg.range
        # Filter invalid ranges
        if current_range < msg.min_range:
            current_range = float('inf') # Too close
        elif current_range > msg.max_range:
            current_range = float('inf') # Too far
            
        scan.ranges = [current_range] * num_readings
        self.publisher.publish(scan)

def main(args=None):
    rclpy.init(args=args)
    node = RangeToLaserScanNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
