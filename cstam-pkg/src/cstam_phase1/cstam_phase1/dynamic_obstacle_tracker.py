"""Detect and track moving people from the navigation scan.

Inputs are the robot's own sensing only: /scan_navigation (front-mounted 3D
LiDAR), short-range rear and side range scans covering what the mast hides
from it, the saved static /map and AMCL's map->base TF. Ground truth from the
simulator is never used.

Outputs (all PointCloud2 in base_footprint, so the costmap ray origin is the
robot):
* /dynamic_obstacles/costmap_local: people now plus their predicted path
  over prediction_horizon seconds, and a far clearing ring;
* /dynamic_obstacles/costmap_global: people now plus the clearing ring;
* /dynamic_obstacles/people: people now only, for the collision monitor;
* /dynamic_obstacles/markers: RViz tracks, velocities and predictions.

The clearing ring lies beyond the costmap layers' obstacle_max_range, so it
never marks anything; its rays clear the whole people layer each update, so a
person who walked away leaves no stale obstacle behind.

It also republishes the 3D cloud without confirmed people as
/lidar/points_static for the voxel layer. People therefore live only in the
people layer, which is rebuilt every cycle: in the voxel layer they left
lethal trails in the LiDAR's near-field blind cone (it cannot see the floor
within ~0.5 m), where no ray ever clears them, stalling the robot. Untracked
people still reach the voxel layer, so a tracking miss stays safe.
"""

import math
import time

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Point
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import LaserScan, PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

from cstam_phase1.people_tracking import (
    MultiTracker,
    StaticMap,
    clearing_ring,
    cluster_scan_points,
    merge_detections,
    person_detections,
    plausible_detections,
    remove_near,
    predicted_footprints,
)


def _yaw(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class DynamicObstacleTracker(Node):

    def __init__(self):
        super().__init__('cstam_dynamic_obstacle_tracker')
        self.declare_parameter('scan_topic', '/scan_navigation')
        # Short-range sensors covering what the mast hides from the LiDAR.
        self.declare_parameter(
            'aux_scan_topics',
            ['/rear_range/scan', '/left_side_range/scan', '/right_side_range/scan'])
        self.declare_parameter('aux_scan_max_age', 0.35)
        self.declare_parameter('cloud_topic', '/lidar/points_filtered')
        self.declare_parameter('static_cloud_topic', '/lidar/points_static')
        self.declare_parameter('people_mask_radius', 0.45)
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('base_frame', 'base_footprint')
        # 5.5 m is >35 s of warning at the robot's 0.15 m/s, and keeps the
        # people layers' per-update clearing area (and re-inflation) small.
        self.declare_parameter('max_range', 5.5)
        self.declare_parameter('static_margin', 0.20)
        # No person's centre is this close to furniture or a wall (body
        # radius plus estimation error); such detections are furniture edges.
        self.declare_parameter('person_min_clearance', 0.30)
        # Within this distance of the map a track must first move this far.
        self.declare_parameter('furniture_distance', 0.50)
        self.declare_parameter('furniture_min_travel', 0.40)
        self.declare_parameter('cluster_gap', 0.25)
        self.declare_parameter('association_gate', 0.7)
        self.declare_parameter('track_timeout', 0.8)
        # The robot's own mast and shelves hide the area just beside and
        # behind it from the front-mounted LiDAR (base frame x < blind_x,
        # within blind_radius). People last seen there are kept for
        # occluded_timeout seconds rather than forgotten.
        self.declare_parameter('blind_x', 0.20)
        self.declare_parameter('blind_radius', 1.0)
        self.declare_parameter('occluded_timeout', 10.0)
        self.declare_parameter('confirm_hits', 3)
        # Padded discs for the costmaps; true-size discs for the monitor.
        self.declare_parameter('person_radius', 0.30)
        self.declare_parameter('monitor_person_radius', 0.22)
        self.declare_parameter('prediction_horizon', 2.0)
        self.declare_parameter('prediction_step', 0.4)
        self.declare_parameter('prediction_growth', 0.05)
        self.declare_parameter('moving_speed', 0.20)
        self.declare_parameter('robot_exclusion_radius', 0.60)
        self.declare_parameter('point_spacing', 0.05)
        self.declare_parameter('clearing_radius', 6.5)
        self.declare_parameter('cloud_height', 0.5)

        get = lambda name: self.get_parameter(name).value  # noqa: E731
        self.global_frame = str(get('global_frame'))
        self.base_frame = str(get('base_frame'))
        self.max_range = float(get('max_range'))
        self.static_margin = float(get('static_margin'))
        self.cluster_gap = float(get('cluster_gap'))
        self.person_radius = float(get('person_radius'))
        self.monitor_radius = float(get('monitor_person_radius'))
        self.horizon = float(get('prediction_horizon'))
        self.prediction_step = float(get('prediction_step'))
        self.growth = float(get('prediction_growth'))
        self.moving_speed = float(get('moving_speed'))
        self.robot_exclusion = float(get('robot_exclusion_radius'))
        self.spacing = float(get('point_spacing'))
        self.cloud_height = float(get('cloud_height'))
        self.ring = clearing_ring(float(get('clearing_radius')), 720)
        self.blind_x = float(get('blind_x'))
        self.blind_radius = float(get('blind_radius'))
        self.tracker = MultiTracker(
            gate=float(get('association_gate')),
            max_age=float(get('track_timeout')),
            confirm_hits=int(get('confirm_hits')),
            occluded_max_age=float(get('occluded_timeout')),
            min_travel_near_static=float(get('furniture_min_travel')))
        self.person_clearance = float(get('person_min_clearance'))
        self.furniture_distance = float(get('furniture_distance'))
        self.static_map = None
        self.too_close = None      # StaticMap with person_min_clearance
        self.near_furniture = None  # StaticMap with furniture_distance
        self.aux = {}  # topic -> (stamp_sec, map-frame points, sensor xy)
        self.aux_max_age = float(get('aux_scan_max_age'))
        self.mask_radius = float(get('people_mask_radius'))
        self.robot_pose = None  # last good (xy, yaw), for TF dropouts
        self.stats = {'scans': 0, 'tf_fallback': 0, 'tf_missing': 0, 'max_ms': 0.0}
        self.create_timer(30.0, self._log_stats)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        map_qos = QoSProfile(depth=1)
        map_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        map_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.create_subscription(OccupancyGrid, '/map', self._map_callback, map_qos)
        self.create_subscription(
            LaserScan, str(get('scan_topic')), self._scan_callback, 5)
        for topic in get('aux_scan_topics'):
            self.create_subscription(
                LaserScan, str(topic),
                lambda scan, t=str(topic): self._aux_callback(t, scan), 5)
        self.static_cloud_pub = self.create_publisher(
            PointCloud2, str(get('static_cloud_topic')), 5)
        self.create_subscription(
            PointCloud2, str(get('cloud_topic')), self._cloud_callback, 5)
        self.local_pub = self.create_publisher(
            PointCloud2, '/dynamic_obstacles/costmap_local', 5)
        self.global_pub = self.create_publisher(
            PointCloud2, '/dynamic_obstacles/costmap_global', 5)
        self.people_pub = self.create_publisher(
            PointCloud2, '/dynamic_obstacles/people', 5)
        self.marker_pub = self.create_publisher(
            MarkerArray, '/dynamic_obstacles/markers', 5)

    def _map_callback(self, message):
        grid = np.array(message.data, dtype=np.int8).reshape(
            message.info.height, message.info.width)
        self.static_map = StaticMap(
            grid, message.info.resolution,
            message.info.origin.position.x, message.info.origin.position.y,
            self.static_margin)
        origin = (message.info.origin.position.x, message.info.origin.position.y)
        self.too_close = StaticMap(grid, message.info.resolution, *origin, self.person_clearance)
        self.near_furniture = StaticMap(grid, message.info.resolution, *origin, self.furniture_distance)
        self.get_logger().info(
            f'Static map loaded ({message.info.width}x{message.info.height}); '
            f'ignoring returns within {self.static_margin:.2f} m of it.')

    def _log_stats(self):
        st = self.stats
        self.get_logger().info(
            f'{st["scans"]} scans in 30 s, slowest {st["max_ms"]:.0f} ms, '
            f'TF latest-fallbacks {st["tf_fallback"]}, TF missing {st["tf_missing"]}')
        self.stats = {'scans': 0, 'tf_fallback': 0, 'tf_missing': 0, 'max_ms': 0.0}

    def _lookup(self, target, source, stamp):
        # Never block the executor: a scan must always produce output.
        try:
            return self.tf_buffer.lookup_transform(target, source, stamp)
        except TransformException:
            pass
        try:
            transform = self.tf_buffer.lookup_transform(target, source, Time())
            self.stats['tf_fallback'] += 1
            return transform
        except TransformException:
            self.stats['tf_missing'] += 1
            return None

    def _scan_callback(self, scan):
        started = time.monotonic()
        try:
            self._process(scan)
        finally:
            self.stats['scans'] += 1
            self.stats['max_ms'] = max(
                self.stats['max_ms'], 1000.0 * (time.monotonic() - started))

    def _scan_points(self, scan, sensor_tf):
        """Valid returns of a scan in the map frame, plus the sensor xy."""
        ranges = np.asarray(scan.ranges, dtype=float)
        angles = scan.angle_min + np.arange(len(ranges)) * scan.angle_increment
        valid = (np.isfinite(ranges) & (ranges > scan.range_min)
                 & (ranges < min(scan.range_max, self.max_range)))
        st = sensor_tf.transform
        sensor_xy = np.array([st.translation.x, st.translation.y])
        world_angles = angles[valid] + _yaw(st.rotation)
        points = sensor_xy + np.column_stack([
            ranges[valid] * np.cos(world_angles), ranges[valid] * np.sin(world_angles)])
        return points, sensor_xy

    def _cloud_callback(self, cloud):
        """Forward the 3D cloud to the voxel layer without confirmed people."""
        xyz = point_cloud2.read_points_numpy(cloud, field_names=('x', 'y', 'z'))
        xyz = xyz[np.all(np.isfinite(xyz), axis=1)]
        tracks = self.tracker.confirmed()
        if tracks and len(xyz):
            cloud_tf = self._lookup(
                cloud.header.frame_id, self.global_frame, Time.from_msg(cloud.header.stamp))
            if cloud_tf is not None:
                t = cloud_tf.transform
                c, s = math.cos(_yaw(t.rotation)), math.sin(_yaw(t.rotation))
                centres = [(t.translation.x + c * x - s * y, t.translation.y + s * x + c * y)
                           for x, y in (tr.position for tr in tracks)]
                xyz = xyz[remove_near(xyz[:, :2], centres, self.mask_radius)]
        self.static_cloud_pub.publish(self._xyz_cloud(cloud.header, xyz))

    @staticmethod
    def _xyz_cloud(header, xyz):
        xyz = np.ascontiguousarray(xyz, dtype=np.float32)
        out = PointCloud2()
        out.header = header
        out.height, out.width = 1, len(xyz)
        out.fields = [PointField(name=axis, offset=4 * i, datatype=PointField.FLOAT32, count=1)
                      for i, axis in enumerate('xyz')]
        out.is_bigendian = False
        out.point_step, out.row_step = 12, 12 * len(xyz)
        out.is_dense = True
        out.data = xyz.tobytes()
        return out

    def _aux_callback(self, topic, scan):
        if self.static_map is None or self.robot_pose is None:
            return
        stamp = Time.from_msg(scan.header.stamp)
        sensor_tf = self._lookup(self.global_frame, scan.header.frame_id, stamp)
        if sensor_tf is None:
            return
        points, sensor_xy = self._scan_points(scan, sensor_tf)
        if len(points):
            points = points[~self.static_map.is_static(points)]
            # Drop any return on the robot's own body.
            local = self._to_base(points, *self.robot_pose)
            body = ((local[:, 0] > -0.36) & (local[:, 0] < 0.40)
                    & (np.abs(local[:, 1]) < 0.32))
            points = points[~body]
        self.aux[topic] = (stamp.nanoseconds * 1e-9, points, sensor_xy)

    def _process(self, scan):
        header = Header(stamp=scan.header.stamp, frame_id=self.base_frame)
        stamp = Time.from_msg(scan.header.stamp)
        sensor_tf = None if self.static_map is None else self._lookup(
            self.global_frame, scan.header.frame_id, stamp)
        robot_tf = self._lookup(self.global_frame, self.base_frame, stamp)
        if robot_tf is not None:
            rt = robot_tf.transform
            self.robot_pose = (np.array([rt.translation.x, rt.translation.y]),
                               _yaw(rt.rotation))
        if sensor_tf is None or self.robot_pose is None:
            # Keep every consumer fed: without localization the best we can
            # do is clear the people layers and report nobody, but staying
            # silent would make the costmaps stale and abort navigation.
            empty = np.zeros((0, 2))
            self.local_pub.publish(self._cloud(header, self.ring))
            self.global_pub.publish(self._cloud(header, self.ring))
            self.people_pub.publish(self._cloud(header, empty))
            return

        points, sensor_xy = self._scan_points(scan, sensor_tf)
        if len(points):
            points = points[~self.static_map.is_static(points)]

        clusters = cluster_scan_points(points, self.cluster_gap)
        detections = person_detections(clusters, sensor_xy)
        stamp_sec = stamp.nanoseconds * 1e-9
        fused = False
        for aux_stamp, aux_points, aux_xy in self.aux.values():
            if abs(stamp_sec - aux_stamp) <= self.aux_max_age:
                aux_clusters = cluster_scan_points(aux_points, self.cluster_gap)
                detections += person_detections(aux_clusters, aux_xy)
                fused = True
        if fused:
            detections = merge_detections(detections, 0.45)
        detections = plausible_detections(detections, self.too_close.is_static)
        robot_xy, robot_yaw = self.robot_pose

        def in_blind_zone(position):
            local = self._to_base(np.asarray([position]), robot_xy, robot_yaw)[0]
            return (local[0] < self.blind_x
                    and float(np.hypot(local[0], local[1])) < self.blind_radius)
        tracks = self.tracker.update(
            detections, stamp.nanoseconds * 1e-9, in_blind_zone,
            lambda position: bool(self.near_furniture.is_static(np.asarray([position]))[0]))

        current, future = predicted_footprints(
            tracks, self.horizon, self.prediction_step, self.person_radius,
            self.growth, self.moving_speed, self.spacing)
        if len(future):
            # A predicted disc on top of the robot would make every motion,
            # including stopping, look like a collision to the controller.
            keep = np.linalg.norm(future - robot_xy, axis=1) > self.robot_exclusion
            future = future[keep]

        actual, _ = predicted_footprints(
            tracks, 0.0, 1.0, self.monitor_radius, 0.0, math.inf, self.spacing)
        current_base = self._to_base(current, robot_xy, robot_yaw)
        future_base = self._to_base(future, robot_xy, robot_yaw)
        self.local_pub.publish(self._cloud(header, current_base, future_base, self.ring))
        self.global_pub.publish(self._cloud(header, current_base, self.ring))
        self.people_pub.publish(self._cloud(
            header, self._to_base(actual, robot_xy, robot_yaw)))
        self.marker_pub.publish(self._markers(scan.header.stamp, tracks))

    @staticmethod
    def _to_base(points, robot_xy, robot_yaw):
        if len(points) == 0:
            return points
        c, s = math.cos(robot_yaw), math.sin(robot_yaw)
        d = points - robot_xy
        return np.column_stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]])

    def _cloud(self, header, *parts):
        """Pack 2D parts at cloud_height into an xyz cloud (no per-point loop)."""
        nonempty = [p for p in parts if len(p)]
        xy = np.vstack(nonempty) if nonempty else np.zeros((0, 2))
        xyz = np.empty((len(xy), 3), dtype=np.float32)
        xyz[:, :2] = xy
        xyz[:, 2] = self.cloud_height
        return self._xyz_cloud(header, xyz)

    def _markers(self, stamp, tracks):
        markers = MarkerArray()
        clear = Marker()
        clear.header.frame_id = self.global_frame
        clear.action = Marker.DELETEALL
        markers.markers.append(clear)
        lifetime = Duration(sec=0, nanosec=500_000_000)
        for track in tracks:
            x, y = track.position
            vx, vy = track.velocity
            moving = track.speed >= self.moving_speed
            body = Marker()
            body.header.frame_id = self.global_frame
            body.header.stamp = stamp
            body.ns, body.id = 'person', track.id
            body.type = Marker.CYLINDER
            body.pose.position.x, body.pose.position.y = float(x), float(y)
            body.pose.position.z = 0.85
            body.pose.orientation.w = 1.0
            body.scale.x = body.scale.y = 2.0 * self.person_radius
            body.scale.z = 1.7
            body.color.r, body.color.g, body.color.b = (
                (1.0, 0.45, 0.0) if moving else (1.0, 0.85, 0.1))
            body.color.a = 0.75
            body.lifetime = lifetime
            markers.markers.append(body)

            label = Marker()
            label.header = body.header
            label.ns, label.id = 'label', track.id
            label.type = Marker.TEXT_VIEW_FACING
            label.pose.position.x, label.pose.position.y = float(x), float(y)
            label.pose.position.z = 1.95
            label.pose.orientation.w = 1.0
            label.scale.z = 0.22
            label.color.r = label.color.g = label.color.b = label.color.a = 1.0
            label.text = f'#{track.id} {track.speed:.2f} m/s'
            label.lifetime = lifetime
            markers.markers.append(label)

            if not moving:
                continue
            path = Marker()
            path.header = body.header
            path.ns, path.id = 'prediction', track.id
            path.type = Marker.LINE_STRIP
            path.pose.orientation.w = 1.0
            path.scale.x = 0.05
            path.color.r, path.color.g, path.color.b, path.color.a = 1.0, 0.2, 0.2, 0.9
            path.lifetime = lifetime
            steps = int(self.horizon / 0.2) + 1
            for i in range(steps):
                t = i * 0.2
                path.points.append(Point(x=float(x + vx * t), y=float(y + vy * t), z=0.05))
            markers.markers.append(path)
        return markers


def main(args=None):
    rclpy.init(args=args)
    node = DynamicObstacleTracker()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        if rclpy.ok():   # not just the launch's shutdown racing the executor
            raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
