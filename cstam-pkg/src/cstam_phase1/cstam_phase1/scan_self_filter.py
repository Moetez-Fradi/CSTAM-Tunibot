"""Remove only the CSTAM self-return from the raw Gazebo LaserScan."""

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class ScanSelfFilter(Node):
    """Keep real scene returns while suppressing CSTAM's rear shelf echo."""

    def __init__(self):
        super().__init__('cstam_scan_self_filter')
        self.declare_parameter('self_range_max', 0.55)
        # The shelf/rear panel is visible on both sides of the rear half-plane
        # in the 360-degree scan.  Filtering only [-pi, -pi/2] leaves the
        # mirrored +pi/2..pi self returns in the SLAM input.
        self.declare_parameter('self_angle_min', math.pi / 2.0)
        self.declare_parameter('self_angle_max', math.pi)
        self.max_range = float(self.get_parameter('self_range_max').value)
        self.angle_min = float(self.get_parameter('self_angle_min').value)
        self.angle_max = float(self.get_parameter('self_angle_max').value)
        self.publisher = self.create_publisher(LaserScan, '/scan_filtered', 10)
        self.create_subscription(LaserScan, '/scan', self._callback, 10)

    def _callback(self, message):
        filtered = LaserScan()
        filtered.header = message.header
        filtered.angle_min = message.angle_min
        filtered.angle_max = message.angle_max
        filtered.angle_increment = message.angle_increment
        filtered.time_increment = message.time_increment
        filtered.scan_time = message.scan_time
        filtered.range_min = message.range_min
        filtered.range_max = message.range_max
        filtered.ranges = list(message.ranges)
        filtered.intensities = list(message.intensities)
        for index, value in enumerate(filtered.ranges):
            angle = message.angle_min + index * message.angle_increment
            if (self.angle_min <= abs(angle) <= self.angle_max and
                    math.isfinite(value) and value < self.max_range):
                filtered.ranges[index] = float('inf')
        self.publisher.publish(filtered)


def main(args=None):
    rclpy.init(args=args)
    node = ScanSelfFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
