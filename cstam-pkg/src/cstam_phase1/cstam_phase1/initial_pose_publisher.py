"""Publish the configured AMCL initial pose until localization acknowledges it."""

import math

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)


class InitialPosePublisher(Node):
    def __init__(self):
        super().__init__('cstam_initial_pose_publisher')
        self.declare_parameter('x', 0.0)
        self.declare_parameter('y', 0.0)
        self.declare_parameter('yaw', 0.0)
        self.declare_parameter('publish_period', 0.5)
        self.declare_parameter('max_publish_count', 30)

        self.x = float(self.get_parameter('x').value)
        self.y = float(self.get_parameter('y').value)
        self.yaw = float(self.get_parameter('yaw').value)
        self.count = 0
        self.received_amcl_pose = False
        self.map_ready = False
        self.odom_ready = False
        self.waiting_logged = False
        self.publisher = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl_pose_callback, 10)
        map_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            OccupancyGrid, '/map', self._map_callback, map_qos)
        self.create_subscription(
            Odometry, '/odom', self._odom_callback, qos_profile_sensor_data)
        self.timer = self.create_timer(
            float(self.get_parameter('publish_period').value), self._publish)
        self.get_logger().info(
            f'Waiting for map, odometry and AMCL before publishing '
            f'initial pose ({self.x:.2f}, {self.y:.2f}, {self.yaw:.2f}).')

    def _map_callback(self, message):
        self.map_ready = message.header.frame_id == 'map'

    def _odom_callback(self, _message):
        self.odom_ready = True

    def _amcl_pose_callback(self, _message):
        # AMCL can emit an initial/default pose before it has consumed the
        # requested /initialpose message.  Only treat a pose near the
        # configured target as acknowledgement.
        message = _message
        position = message.pose.pose.position
        distance = math.hypot(position.x - self.x, position.y - self.y)
        orientation = message.pose.pose.orientation
        pose_yaw = math.atan2(
            2.0 * (orientation.w * orientation.z),
            1.0 - 2.0 * (orientation.z * orientation.z),
        )
        yaw_error = math.atan2(
            math.sin(pose_yaw - self.yaw), math.cos(pose_yaw - self.yaw))
        if not self.received_amcl_pose and distance < 0.35 and abs(yaw_error) < 0.45:
            self.received_amcl_pose = True
            self.get_logger().info(
                'AMCL acknowledged the configured initial pose; stopping publisher.')
            self.timer.cancel()

    def _publish(self):
        if self.received_amcl_pose:
            return
        ready = (
            self.map_ready
            and self.odom_ready
            and self.publisher.get_subscription_count() > 0
        )
        if not ready:
            if not self.waiting_logged:
                self.get_logger().info(
                    'Initial pose is waiting for the complete localization '
                    'input chain.')
                self.waiting_logged = True
            return
        message = PoseWithCovarianceStamped()
        # Give the request a recent, non-future sensor-time stamp. AMCL may
        # still log a one-sample odom extrapolation while compensating the
        # pose to its callback time; it safely falls back and accepts the pose.
        stamp = self.get_clock().now()
        if stamp.nanoseconds > 100_000_000:
            stamp = stamp - Duration(seconds=0.1)
        message.header.stamp = stamp.to_msg()
        message.header.frame_id = 'map'
        message.pose.pose.position.x = self.x
        message.pose.pose.position.y = self.y
        message.pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        message.pose.pose.orientation.w = math.cos(self.yaw / 2.0)
        message.pose.covariance[0] = 0.10
        message.pose.covariance[7] = 0.10
        message.pose.covariance[35] = 0.05
        self.publisher.publish(message)
        if self.count == 0:
            self.get_logger().info(
                'Localization inputs are ready; publishing the initial pose.')
        self.count += 1
        if self.count >= int(self.get_parameter('max_publish_count').value):
            self.get_logger().error(
                'AMCL did not acknowledge the initial pose before the retry limit.')
            self.timer.cancel()


def main(args=None):
    rclpy.init(args=args)
    node = InitialPosePublisher()
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
