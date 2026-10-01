"""Bounded runtime health check for the complete Phase 1 startup chain."""

import math
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan, PointCloud2
from tf2_ros import Buffer, TransformListener


class StartupHealthCheck(Node):
    """Observe all startup dependencies using one DDS participant."""

    def __init__(self):
        super().__init__('cstam_phase1_startup_health_check')
        self.declare_parameter('timeout_sec', 25.0)
        self.timeout_sec = float(self.get_parameter('timeout_sec').value)
        self.messages = {}
        self.clock_first = None
        self.clock_latest = None

        transient_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        reliable_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.create_subscription(Clock, '/clock', self._clock_callback, 10)
        self.create_subscription(
            OccupancyGrid, '/map', self._store('map'), transient_qos)
        self.create_subscription(
            PointCloud2, '/lidar/points', self._store('points'), reliable_qos)
        self.create_subscription(
            PointCloud2, '/lidar/points_filtered',
            self._store('points_filtered'), reliable_qos)
        self.create_subscription(
            PointCloud2, '/lidar/points_clearing',
            self._store('points_clearing'), reliable_qos)
        self.create_subscription(
            LaserScan, '/scan_navigation', self._store('scan'), reliable_qos)
        self.create_subscription(
            Odometry, '/odom', self._store('odom'), reliable_qos)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose',
            self._store('amcl_pose'), transient_qos)
        self.create_subscription(
            OccupancyGrid, '/global_costmap/costmap',
            self._store('global_costmap'), reliable_qos)
        self.create_subscription(
            OccupancyGrid, '/local_costmap/costmap',
            self._store('local_costmap'), reliable_qos)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.compute_path = ActionClient(
            self, ComputePathToPose, '/compute_path_to_pose')
        self.navigate = ActionClient(
            self, NavigateToPose, '/navigate_to_pose')
        self.lifecycle_clients = {
            name: self.create_client(GetState, f'/{name}/get_state')
            for name in (
                'amcl', 'map_server', 'planner_server',
                'controller_server', 'bt_navigator')
        }

    def _store(self, name):
        def callback(message):
            self.messages[name] = message
        return callback

    def _clock_callback(self, message):
        value = message.clock.sec + message.clock.nanosec * 1e-9
        if self.clock_first is None:
            self.clock_first = value
        self.clock_latest = value

    def _spin_until_inputs(self):
        deadline = time.monotonic() + self.timeout_sec
        lifecycle = {}
        required = {
            'map', 'points', 'points_filtered', 'points_clearing', 'scan', 'odom', 'amcl_pose',
            'global_costmap', 'local_costmap',
        }
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            transforms_ready = all(
                self.tf_buffer.can_transform(target, source, Time())
                for target, source in (
                    ('odom', 'base_footprint'),
                    ('base_link', 'lidar_3d_link'),
                    ('map', 'odom'),
                    ('map', 'base_footprint'),
                )
            )
            actions_ready = (
                self.compute_path.server_is_ready()
                and self.navigate.server_is_ready()
            )
            clock_ready = (
                self.clock_first is not None
                and self.clock_latest is not None
                and self.clock_latest > self.clock_first
            )
            if (
                required.issubset(self.messages)
                and transforms_ready
                and actions_ready
                and clock_ready
            ):
                # Action servers can be advertised while the lifecycle node
                # is still activating. Wait within the same bounded startup
                # window instead of reporting a transient false failure.
                lifecycle = self._lifecycle_states()
                if all(lifecycle.get(name) == 'active'
                       for name in self.lifecycle_clients):
                    return lifecycle
        return lifecycle

    def _lifecycle_states(self):
        states = {}
        pending = {}
        for name, client in self.lifecycle_clients.items():
            if client.wait_for_service(timeout_sec=0.2):
                pending[name] = client.call_async(GetState.Request())
        deadline = time.monotonic() + 2.0
        while pending and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            for name, future in list(pending.items()):
                if future.done():
                    try:
                        states[name] = future.result().current_state.label
                    except Exception:
                        states[name] = 'unavailable'
                    del pending[name]
        return states

    def evaluate(self):
        lifecycle = self._spin_until_inputs()
        if not lifecycle:
            lifecycle = self._lifecycle_states()
        results = []

        def add(description, passed, detail=''):
            results.append((description, bool(passed), detail))

        clock_advanced = (
            self.clock_first is not None
            and self.clock_latest is not None
            and self.clock_latest > self.clock_first
        )
        add('/clock advancing', clock_advanced)

        map_msg = self.messages.get('map')
        add(
            '/map valid',
            map_msg is not None
            and map_msg.header.frame_id == 'map'
            and map_msg.info.width == 345
            and map_msg.info.height == 486
            and math.isclose(map_msg.info.resolution, 0.05, abs_tol=1e-6),
            'expected map frame, 345x486 cells at 0.05 m')

        points = self.messages.get('points')
        add(
            '/lidar/points valid',
            points is not None
            and points.header.frame_id == 'lidar_3d_link'
            and points.height == 16,
            'expected lidar_3d_link with 16 vertical channels')
        add(
            '/lidar/points_filtered publishing',
            self.messages.get('points_filtered') is not None)
        add(
            '/lidar/points_clearing publishing',
            self.messages.get('points_clearing') is not None)

        scan = self.messages.get('scan')
        finite_ranges = (
            scan is not None and any(math.isfinite(value) for value in scan.ranges)
        )
        add(
            '/scan_navigation valid',
            scan is not None
            and scan.header.frame_id == 'lidar_3d_link'
            and finite_ranges,
            'expected lidar_3d_link and finite scene ranges')

        odom = self.messages.get('odom')
        add(
            '/odom valid',
            odom is not None
            and odom.header.frame_id == 'odom'
            and odom.child_frame_id == 'base_drive')
        add(
            '/amcl_pose available',
            self.messages.get('amcl_pose') is not None
            and self.messages['amcl_pose'].header.frame_id == 'map')
        add(
            'global costmap available/current',
            self.messages.get('global_costmap') is not None)
        add(
            'local costmap available/current',
            self.messages.get('local_costmap') is not None)

        for target, source, label in (
            ('odom', 'base_footprint', 'odom -> base_footprint TF'),
            ('base_link', 'lidar_3d_link', 'base_link -> lidar_3d_link TF'),
            ('map', 'odom', 'map -> odom TF'),
            ('map', 'base_footprint', 'map -> base_footprint TF'),
        ):
            add(
                label,
                self.tf_buffer.can_transform(target, source, Time()))

        for name in (
            'map_server', 'amcl', 'planner_server',
            'controller_server', 'bt_navigator'):
            add(f'{name} active', lifecycle.get(name) == 'active')

        add(
            'ComputePathToPose action available',
            self.compute_path.server_is_ready())
        add(
            'NavigateToPose action available',
            self.navigate.server_is_ready())

        node_names = self.get_node_names_and_namespaces()
        duplicates = sorted({item for item in node_names if node_names.count(item) > 1})
        add(
            'no duplicate ROS node names',
            not duplicates,
            ', '.join(f'{namespace}{name}' for name, namespace in duplicates))

        passed = sum(1 for _, ok, _ in results if ok)
        failed = len(results) - passed
        print('CSTAM Phase 1 startup health check')
        for description, ok, detail in results:
            suffix = f' ({detail})' if detail and not ok else ''
            print(f'{"PASS" if ok else "FAIL"}: {description}{suffix}')
        print(f'PASS={passed} FAIL={failed}')
        return failed == 0


def main(args=None):
    rclpy.init(args=args)
    node = StartupHealthCheck()
    try:
        success = node.evaluate()
    finally:
        node.destroy_node()
        rclpy.shutdown()
    raise SystemExit(0 if success else 1)


if __name__ == '__main__':
    main()
