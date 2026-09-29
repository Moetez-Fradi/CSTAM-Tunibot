"""Drive a slow, odometry-based mapping patrol using the real CSTAM robot."""

import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


def angle_error(target, current):
    return math.atan2(math.sin(target - current), math.cos(target - current))


class MappingRoute(Node):
    """A conservative rectangular patrol with a front-obstacle safety stop."""

    def __init__(self):
        super().__init__('cstam_mapping_route')
        self.declare_parameter('linear_speed', 0.12)
        self.declare_parameter('angular_speed', 0.25)
        self.declare_parameter('turn_angle', math.pi / 2.0)
        self.declare_parameter('leg_length', 5.0)
        self.declare_parameter('legs', 4)
        self.declare_parameter('leg_lengths', '')
        self.declare_parameter('turn_directions', '')
        self.declare_parameter('safety_distance', 0.75)
        self.declare_parameter('safety_trigger_scans', 5)
        self.declare_parameter('auto_avoid', False)
        self.linear_speed = float(self.get_parameter('linear_speed').value)
        self.angular_speed = float(self.get_parameter('angular_speed').value)
        self.turn_angle = float(self.get_parameter('turn_angle').value)
        self.leg_length = float(self.get_parameter('leg_length').value)
        self.legs = int(self.get_parameter('legs').value)
        length_text = str(self.get_parameter('leg_lengths').value).strip()
        turn_text = str(self.get_parameter('turn_directions').value).strip()
        self.leg_lengths = (
            [float(value) for value in length_text.split(',') if value.strip()]
            if length_text else [self.leg_length] * self.legs)
        self.turn_directions = (
            [float(value) for value in turn_text.split(',') if value.strip()]
            if turn_text else [1.0] * len(self.leg_lengths))
        # Explicit route lists define the route length.  The old default of
        # four legs must not silently truncate a deliberate coverage patrol.
        self.legs = min(len(self.leg_lengths), len(self.turn_directions))
        self.safety_distance = float(self.get_parameter('safety_distance').value)
        self.safety_trigger_scans = int(
            self.get_parameter('safety_trigger_scans').value)
        self.auto_avoid = bool(self.get_parameter('auto_avoid').value)
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Odometry, '/odom', self._odom_callback, 10)
        # Use the 3D-LiDAR-derived scan so the mapping patrol sees geometry at
        # every height occupied by CSTAM, including chair backs and counters.
        self.create_subscription(
            LaserScan, '/scan_navigation', self._scan_callback, 10)
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.initialized = False
        self.start_x = 0.0
        self.start_y = 0.0
        self.target_yaw = 0.0
        self.front_clearance = float('inf')
        self.left_clearance = float('inf')
        self.right_clearance = float('inf')
        self.close_scan_count = 0
        self.avoid_count = 0
        self.phase = 'rotate'
        self.leg = 0
        self.rotate_start = None
        self.drive_start = None
        self.timer = self.create_timer(0.1, self._step)
        self.get_logger().info(
            'Mapping route started. It uses real /cmd_vel, /odom and '
            '/scan_navigation; '
            f'auto_avoid={self.auto_avoid}; '
            'Ctrl+C stops the robot.')

    def _odom_callback(self, message):
        pose = message.pose.pose
        self.x = pose.position.x
        self.y = pose.position.y
        self.yaw = math.atan2(
            2.0 * (pose.orientation.w * pose.orientation.z),
            1.0 - 2.0 * pose.orientation.z * pose.orientation.z)
        if not self.initialized:
            self.initialized = True
            self.start_x = self.x
            self.start_y = self.y
            self.target_yaw = self.yaw

    def _scan_callback(self, message):
        values = []
        left_values = []
        right_values = []
        for index, value in enumerate(message.ranges):
            angle = message.angle_min + index * message.angle_increment
            if not math.isfinite(value):
                continue
            if abs(angle) <= math.radians(25.0):
                values.append(value)
            elif math.radians(35.0) <= angle <= math.radians(120.0):
                left_values.append(value)
            elif -math.radians(120.0) <= angle <= -math.radians(35.0):
                right_values.append(value)
        self.front_clearance = min(values, default=float('inf'))
        self.left_clearance = min(left_values, default=float('inf'))
        self.right_clearance = min(right_values, default=float('inf'))
        if self.front_clearance < self.safety_distance:
            self.close_scan_count += 1
        else:
            self.close_scan_count = 0

    def _command(self, linear=0.0, angular=0.0):
        message = Twist()
        message.linear.x = linear
        message.angular.z = angular
        self.publisher.publish(message)

    def _step(self):
        if not self.initialized:
            self._command()
            return
        if self.leg >= self.legs:
            self.stop()
            self.get_logger().info('Mapping route complete; robot stopped.')
            self.timer.cancel()
            rclpy.shutdown()
            return

        if self.phase == 'rotate':
            if self.rotate_start is None:
                self.rotate_start = self.yaw
                self.target_yaw = self.yaw + (
                    math.copysign(self.turn_angle, self.turn_directions[self.leg]))
            error = angle_error(self.target_yaw, self.yaw)
            if abs(error) < 0.04:
                self._command()
                self.phase = 'drive'
                self.drive_start = (self.x, self.y)
                self.rotate_start = None
                self.get_logger().info(f'Leg {self.leg + 1}/{self.legs}: driving.')
            else:
                self._command(angular=math.copysign(self.angular_speed, error))
            return

        if self.phase == 'avoid_rotate':
            error = angle_error(self.target_yaw, self.yaw)
            if abs(error) < 0.04:
                self._command()
                self.phase = 'drive'
                self.drive_start = (self.x, self.y)
                self.rotate_start = None
                self.get_logger().info(
                    f'Obstacle avoidance turn {self.avoid_count} complete; driving.')
            else:
                self._command(angular=math.copysign(self.angular_speed, error))
            return

        if self.close_scan_count >= self.safety_trigger_scans:
            if self.auto_avoid and self.avoid_count < 12:
                direction = 1.0 if self.left_clearance >= self.right_clearance else -1.0
                self.target_yaw = self.yaw + direction * self.turn_angle
                self.phase = 'avoid_rotate'
                self.rotate_start = self.yaw
                self.drive_start = None
                self.close_scan_count = 0
                self.avoid_count += 1
                self.get_logger().warning(
                    f'Obstacle at {self.front_clearance:.2f} m; '
                    f'avoidance turn {self.avoid_count} direction={direction:+.0f}.')
                self._command()
                return
            self.stop()
            self.get_logger().error(
                f'Safety stop at {self.front_clearance:.2f} m. '
                'The route was stopped before a collision; inspect the map and rerun.')
            self.timer.cancel()
            return
        distance = math.hypot(self.x - self.drive_start[0], self.y - self.drive_start[1])
        if distance >= self.leg_lengths[self.leg]:
            self._command()
            self.phase = 'rotate'
            self.leg += 1
            self.drive_start = None
            self.get_logger().info(f'Leg {self.leg}/{self.legs}: turn.')
        else:
            self._command(linear=self.linear_speed)

    def stop(self):
        if not rclpy.ok():
            return
        for _ in range(5):
            try:
                self._command()
            except rclpy.RCLError:
                break


def main(args=None):
    rclpy.init(args=args)
    node = MappingRoute()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
