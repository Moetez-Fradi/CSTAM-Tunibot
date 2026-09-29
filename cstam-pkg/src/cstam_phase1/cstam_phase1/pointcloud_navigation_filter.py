"""Project one simulated 3D LiDAR into Phase 1 navigation products.

The GPU LiDAR publishes a real ``PointCloud2`` with several vertical rings.
This node removes only points inside the known CSTAM self-volume, keeps the
vertical space occupied by the robot, and publishes:

* ``/lidar/points_filtered`` for Nav2's local voxel layer;
* ``/scan_navigation`` for the existing 2D SLAM Toolbox and AMCL pipeline.

The projection is deliberately nearest-return per horizontal angle.  That is
the same conservative representation used by a 2D laser scanner: any point
in the robot's collision height blocks the ray.
"""

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan, PointCloud2
from sensor_msgs_py import point_cloud2


class PointCloudNavigationFilter(Node):
    """Filter CSTAM returns and project relevant 3D points into a LaserScan."""

    def __init__(self):
        super().__init__('cstam_pointcloud_navigation_filter')
        self.declare_parameter('input_topic', '/lidar/points')
        self.declare_parameter('cloud_topic', '/lidar/points_filtered')
        self.declare_parameter('scan_topic', '/scan_navigation')
        self.declare_parameter('horizontal_samples', 360)
        self.declare_parameter('range_min', 0.10)
        self.declare_parameter('range_max', 15.0)
        # lidar_3d_link is at x=.24, z=.92 relative to base_footprint.  These
        # bounds correspond to world z=.04..1.18: above floor noise and up to
        # the top of the CSTAM mast/display collision geometry.
        self.declare_parameter('min_height', -0.88)
        self.declare_parameter('max_height', 0.26)
        self.declare_parameter('sensor_x_in_base', 0.24)
        self.declare_parameter('sensor_z_in_base', 0.92)
        self.declare_parameter('self_x_min', -0.29)
        self.declare_parameter('self_x_max', 0.31)
        self.declare_parameter('self_y_min', -0.26)
        self.declare_parameter('self_y_max', 0.26)
        self.declare_parameter('self_z_min', 0.0)
        self.declare_parameter('self_z_max', 1.18)

        self.samples = int(self.get_parameter('horizontal_samples').value)
        self.range_min = float(self.get_parameter('range_min').value)
        self.range_max = float(self.get_parameter('range_max').value)
        self.min_height = float(self.get_parameter('min_height').value)
        self.max_height = float(self.get_parameter('max_height').value)
        self.sensor_x = float(self.get_parameter('sensor_x_in_base').value)
        self.sensor_z = float(self.get_parameter('sensor_z_in_base').value)
        self.self_x_min = float(self.get_parameter('self_x_min').value)
        self.self_x_max = float(self.get_parameter('self_x_max').value)
        self.self_y_min = float(self.get_parameter('self_y_min').value)
        self.self_y_max = float(self.get_parameter('self_y_max').value)
        self.self_z_min = float(self.get_parameter('self_z_min').value)
        self.self_z_max = float(self.get_parameter('self_z_max').value)

        input_topic = str(self.get_parameter('input_topic').value)
        cloud_topic = str(self.get_parameter('cloud_topic').value)
        scan_topic = str(self.get_parameter('scan_topic').value)
        self.cloud_publisher = self.create_publisher(PointCloud2, cloud_topic, 5)
        self.scan_publisher = self.create_publisher(LaserScan, scan_topic, 10)
        self.create_subscription(PointCloud2, input_topic, self._callback, 5)
        self.get_logger().info(
            f'Projecting {input_topic} to {scan_topic}; forwarding relevant '
            f'points on {cloud_topic} with height [{self.min_height:.2f}, '
            f'{self.max_height:.2f}] m in lidar_3d_link.')

    def _is_self_point(self, x, y, z):
        base_x = x + self.sensor_x
        base_z = z + self.sensor_z
        return (
            self.self_x_min <= base_x <= self.self_x_max and
            self.self_y_min <= y <= self.self_y_max and
            self.self_z_min <= base_z <= self.self_z_max)

    def _callback(self, message):
        points = []
        bins = [float('inf')] * self.samples
        angle_increment = 2.0 * math.pi / self.samples

        for point in point_cloud2.read_points(
                message, field_names=('x', 'y', 'z'), skip_nans=False):
            x, y, z = (float(point[0]), float(point[1]), float(point[2]))
            if not all(math.isfinite(value) for value in (x, y, z)):
                continue
            distance = math.hypot(x, y)
            if distance < self.range_min or distance > self.range_max:
                continue
            if z < self.min_height or z > self.max_height:
                continue
            if self._is_self_point(x, y, z):
                continue
            points.append((x, y, z))
            angle = math.atan2(y, x)
            index = int((angle + math.pi) / angle_increment)
            if index >= self.samples:
                index = self.samples - 1
            if distance < bins[index]:
                bins[index] = distance

        filtered = point_cloud2.create_cloud_xyz32(message.header, points)
        self.cloud_publisher.publish(filtered)

        scan = LaserScan()
        scan.header = message.header
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = angle_increment
        scan.time_increment = 0.0
        scan.scan_time = 1.0 / 8.0
        scan.range_min = self.range_min
        scan.range_max = self.range_max
        scan.ranges = bins
        self.scan_publisher.publish(scan)


def main(args=None):
    rclpy.init(args=args)
    node = PointCloudNavigationFilter()
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
