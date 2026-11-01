"""Recognise the VIP guest with the robot's RGB-D camera.

The VIP wears an ID badge: ArUco marker vip_marker_id (DICT_4X4_50,
config/vip_badge.png) on the chest, back and both sleeves. Identity comes
from the marker's id alone, as with a badge reader: anyone else, whatever
they wear, is not the VIP. Twice a second the detector

1. finds ArUco markers in the colour image and keeps the VIP's id,
2. takes the median depth inside the marker and back-projects its centre
   through the camera intrinsics (camera_optical_frame), adding half a body
   width so the point is the person's centre, not their badge,
3. transforms it to the map frame and finds the table they are at
   (nearest tabletop centre within table_radius).

/vip/status (JSON, latched) carries the last sighting: position, table,
wall-clock time, pixel count and range. The task manager serves that
table's orders first; the dashboard shows the sighting.
"""

import json
import math
import os
import time

from ament_index_python.packages import get_package_share_directory
import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener
import yaml


ARUCO = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def find_badges(gray, marker_id, min_side_px=12):
    """Pixel corners (4x2 arrays) of every visible marker with marker_id."""
    corners, ids, _rejected = cv2.aruco.detectMarkers(
        gray, ARUCO, parameters=cv2.aruco.DetectorParameters_create())
    if ids is None:
        return []
    found = []
    for quad, mid in zip(corners, ids.flatten()):
        quad = quad.reshape(4, 2)
        side = float(np.mean(np.linalg.norm(quad - np.roll(quad, 1, axis=0), axis=1)))
        if int(mid) == marker_id and side >= min_side_px:
            found.append(quad)
    return found


def locate(quad, depth, fx, fy, cx, cy, body_radius=0.19):
    """(x, y, z) of the badge wearer's centre in the optical frame, or None.

    Median depth over the marker's box with a finite reading; the centre is
    pushed body_radius further along the viewing ray.
    """
    (u0, v0), (u1, v1) = quad.min(axis=0), quad.max(axis=0)
    h, w = depth.shape
    patch = depth[max(0, int(v0)):min(h, int(v1) + 1), max(0, int(u0)):min(w, int(u1) + 1)]
    d = patch[np.isfinite(patch) & (patch > 0.1)]
    if len(d) < 4:
        return None
    z = float(np.median(d))
    u, v = quad.mean(axis=0)
    ray = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
    point = ray * z
    return tuple(point + ray / np.linalg.norm(ray) * body_radius)


def nearest_table(tables, x, y, radius):
    """Name of the table whose centre is nearest (x, y), within radius."""
    best, best_d = None, radius
    for name, (tx, ty) in tables.items():
        d = math.hypot(tx - x, ty - y)
        if d <= best_d:
            best, best_d = name, d
    return best


def load_tables(path, floor=1):
    with open(path, encoding='utf-8') as stream:
        data = yaml.safe_load(stream) or {}
    return {name: (float(v['table'][0]), float(v['table'][1]))
            for name, v in data.items()
            if isinstance(v, dict) and 'table' in v and int(v.get('floor', 1)) == floor}


class VipDetector(Node):

    def __init__(self):
        super().__init__('cstam_vip_detector')
        share = get_package_share_directory('cstam_phase1')
        self.declare_parameter('locations_file', os.path.join(
            share, 'maps', 'restaurant', 'locations.yaml'))
        self.declare_parameter('image_topic', '/camera/rgbd/image')
        self.declare_parameter('depth_topic', '/camera/rgbd/depth_image')
        self.declare_parameter('info_topic', '/camera/rgbd/camera_info')
        self.declare_parameter('rate_hz', 2.0)
        self.declare_parameter('vip_marker_id', 7)
        self.declare_parameter('min_marker_px', 12)
        self.declare_parameter('max_range', 8.0)
        self.declare_parameter('table_radius', 1.6)
        get = lambda name: self.get_parameter(name).value  # noqa: E731
        # Only floor-1 guests are simulated; upstairs the camera sees no VIP.
        self.tables = load_tables(str(get('locations_file')))
        self.marker_id = int(get('vip_marker_id'))
        self.min_marker_px = int(get('min_marker_px'))
        self.max_range = float(get('max_range'))
        self.table_radius = float(get('table_radius'))
        self.period = 1.0 / max(0.1, float(get('rate_hz')))
        self.image = self.depth = self.info = None
        self.last_processed = 0.0
        self.sighting = None
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(Image, str(get('image_topic')), self._image, qos_profile_sensor_data)
        self.create_subscription(Image, str(get('depth_topic')), self._depth, qos_profile_sensor_data)
        self.create_subscription(CameraInfo, str(get('info_topic')), self._info, qos_profile_sensor_data)
        latched = QoSProfile(depth=1)
        latched.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        latched.reliability = QoSReliabilityPolicy.RELIABLE
        self.status_pub = self.create_publisher(String, '/vip/status', latched)
        self.status_pub.publish(String(data=json.dumps({'visible': False, 'last_seen': None})))
        self.get_logger().info(f'VIP detector watching {get("image_topic")}; '
                               f'tables {sorted(self.tables)}')

    def _info(self, message):
        self.info = message

    def _depth(self, message):
        self.depth = message

    def _image(self, message):
        self.image = message
        now = time.monotonic()
        if now - self.last_processed >= self.period:
            self.last_processed = now
            self._process()

    def _process(self):
        if self.depth is None or self.info is None:
            return
        image, depth_msg = self.image, self.depth
        if image.encoding not in ('rgb8', 'bgr8') or depth_msg.encoding != '32FC1':
            return
        rgb = np.frombuffer(image.data, np.uint8).reshape(image.height, image.step)[:, :image.width * 3]
        rgb = rgb.reshape(image.height, image.width, 3)
        if image.encoding == 'bgr8':
            rgb = rgb[..., ::-1]
        depth = np.frombuffer(depth_msg.data, np.float32).reshape(depth_msg.height, depth_msg.width)
        if depth.shape != rgb.shape[:2]:
            return
        k = self.info.k
        badges = find_badges(cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY),
                             self.marker_id, self.min_marker_px)
        points = [p for p in (locate(q, depth, k[0], k[4], k[2], k[5]) for q in badges) if p]
        point = min(points, key=lambda p: p[2]) if points else None
        visible = point is not None and point[2] <= self.max_range
        if visible:
            mapped = self._to_map(point, image.header.frame_id)
            if mapped is None:
                return
            x, y = mapped
            self.sighting = {
                'visible': True, 'last_seen': time.time(), 'x': round(x, 2), 'y': round(y, 2),
                'table': nearest_table(self.tables, x, y, self.table_radius),
                'range_m': round(float(point[2]), 2), 'badges': len(badges)}
            self.status_pub.publish(String(data=json.dumps(self.sighting)))
        elif self.sighting and self.sighting['visible']:
            self.sighting = {**self.sighting, 'visible': False}
            self.status_pub.publish(String(data=json.dumps(self.sighting)))

    def _to_map(self, point, frame):
        # Latest transform: at 2 Hz and walking speed the image is at most a
        # few centimetres older, well inside table_radius.
        try:
            t = self.tf_buffer.lookup_transform('map', frame or 'camera_optical_frame', Time())
        except TransformException:
            return None
        q, p = t.transform.rotation, t.transform.translation
        # Rotate the optical-frame point by q, then translate.
        x, y, z = point
        qx, qy, qz, qw = q.x, q.y, q.z, q.w
        rx = (1 - 2 * (qy * qy + qz * qz)) * x + 2 * (qx * qy - qz * qw) * y + 2 * (qx * qz + qy * qw) * z
        ry = 2 * (qx * qy + qz * qw) * x + (1 - 2 * (qx * qx + qz * qz)) * y + 2 * (qy * qz - qx * qw) * z
        return p.x + rx, p.y + ry


def main(args=None):
    rclpy.init(args=args)
    node = VipDetector()
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
