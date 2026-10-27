"""ROS side of the CSTAM web UI.

Feeds the StateHub from the robot (task status, battery, map pose, global
plan, tracked people, safety metrics, node health, lifetime usage for
maintenance) and turns web commands
into the task manager's own interface: /delivery/request, /delivery/cancel,
/delivery/confirm and the /delivery/return_to_dock service. It never sends
navigation goals itself.
"""

import json
import math
import os
import socket
import threading

from ament_index_python.packages import get_package_share_directory
from nav_msgs.msg import Odometry, Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import MarkerArray

from cstam_ui.catalog import Catalog
from cstam_ui.hub import StateHub
from cstam_ui.map_image import load_map
from cstam_ui.server import UiServer
from cstam_ui.usage import load_schedule, UsageTracker


MAX_PLAN_POINTS = 150
USAGE_SAVE_SEC = 30.0
PREDICTION_STEP_SEC = 0.2   # spacing of the tracker's prediction line points
# Nodes shown in the admin health panel (name as in phase1.launch.py / Nav2).
WATCHED_NODES = [
    'cstam_delivery_task_manager', 'cstam_battery_simulator', 'amcl', 'map_server',
    'planner_server', 'controller_server', 'bt_navigator', 'collision_monitor',
    'cstam_dynamic_obstacle_tracker', 'cstam_pedestrian_simulator',
]


def lan_address():
    """This machine's address on the local network (what phones can reach).

    Connecting a UDP socket sends nothing; it only selects the outgoing
    interface. Falls back to localhost when there is no network.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 80))  # TEST-NET-1, never routed
            return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def _yaw(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def battery_view(message):
    percentage = 100.0 * float(message.percentage)
    return {
        'percentage': round(percentage, 1) if math.isfinite(percentage) else None,
        'charging': message.power_supply_status in (
            BatteryState.POWER_SUPPLY_STATUS_CHARGING, BatteryState.POWER_SUPPLY_STATUS_FULL),
        'full': message.power_supply_status == BatteryState.POWER_SUPPLY_STATUS_FULL,
        'voltage': round(float(message.voltage), 2),
        'current': round(float(message.current), 2),
        'health': ('dead' if message.power_supply_health == BatteryState.POWER_SUPPLY_HEALTH_DEAD
                   else 'good'),
    }


def plan_view(message):
    points = [(p.pose.position.x, p.pose.position.y) for p in message.poses]
    if len(points) > MAX_PLAN_POINTS:
        step = len(points) / MAX_PLAN_POINTS
        points = [points[int(i * step)] for i in range(MAX_PLAN_POINTS)] + [points[-1]]
    return [[round(x, 2), round(y, 2)] for x, y in points]


def people_view(message):
    """Tracked people from the tracker's RViz markers (map frame)."""
    people, velocity = {}, {}
    for marker in message.markers:
        if marker.ns == 'person':
            people[marker.id] = {
                'id': marker.id,
                'x': round(marker.pose.position.x, 2), 'y': round(marker.pose.position.y, 2),
                'vx': 0.0, 'vy': 0.0, 'moving': False,
            }
        elif marker.ns == 'prediction' and len(marker.points) >= 2:
            a, b = marker.points[0], marker.points[1]
            velocity[marker.id] = ((b.x - a.x) / PREDICTION_STEP_SEC,
                                   (b.y - a.y) / PREDICTION_STEP_SEC)
    for track_id, (vx, vy) in velocity.items():
        if track_id in people:
            people[track_id].update(vx=round(vx, 2), vy=round(vy, 2), moving=True)
    return sorted(people.values(), key=lambda p: p['id'])


class UiNode(Node):
    def __init__(self, hub):
        super().__init__('cstam_ui_server')
        self.hub = hub
        self.declare_parameter('base_frame', 'base_footprint')
        self.declare_parameter('map_frame', 'map')
        self.base_frame = str(self.get_parameter('base_frame').value)
        self.map_frame = str(self.get_parameter('map_frame').value)

        latched = QoSProfile(depth=1)
        latched.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        latched.reliability = QoSReliabilityPolicy.RELIABLE
        self.create_subscription(String, '/delivery/status', self._status, latched)
        self.usage = None
        self.usage_lock = threading.Lock()
        self.create_subscription(BatteryState, '/battery/state', self._battery, latched)
        self.create_subscription(Path, '/plan', lambda m: hub.update('plan', plan_view(m)), 5)
        self.create_subscription(
            MarkerArray, '/dynamic_obstacles/markers',
            lambda m: hub.update('people', people_view(m)), 5)
        self.create_subscription(String, '/pedestrians/metrics', self._safety, 5)

        self.request_pub = self.create_publisher(String, '/delivery/request', 10)
        self.cancel_pub = self.create_publisher(String, '/delivery/cancel', 10)
        self.confirm_pub = self.create_publisher(String, '/delivery/confirm', 10)
        self.dock_client = self.create_client(Trigger, '/delivery/return_to_dock')

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_timer(0.2, self._pose)
        self.create_timer(1.0, self._health)

    def attach_usage(self, usage):
        """Track lifetime usage (odometry, battery) for the maintenance view."""
        self.usage = usage
        self.create_subscription(Odometry, '/odom', self._odometry, 20)
        self.create_timer(2.0, self._publish_usage)
        self.create_timer(USAGE_SAVE_SEC, self.save_usage)
        self._publish_usage()

    def save_usage(self):
        if self.usage is None:
            return
        with self.usage_lock:
            try:
                self.usage.save()
            except OSError as error:
                self.get_logger().warn(f'cannot save usage to {self.usage.path}: {error}')

    def _publish_usage(self):
        with self.usage_lock:
            report = self.usage.report()
        if report != self.hub.get('maintenance'):
            self.hub.update('maintenance', report)

    def _odometry(self, message):
        twist = message.twist.twist
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        with self.usage_lock:
            self.usage.odometry(stamp, twist.linear.x, twist.angular.z)

    # ----- ROS -> hub ------------------------------------------------------

    def _battery(self, message):
        view = battery_view(message)
        self.hub.update('battery', view)
        if self.usage is not None:
            with self.usage_lock:
                self.usage.battery(view['percentage'], view['charging'])

    def _status(self, message):
        try:
            self.hub.update('status', json.loads(message.data))
        except json.JSONDecodeError:
            self.get_logger().warn('ignoring a non-JSON /delivery/status message')

    def _safety(self, message):
        try:
            self.hub.update('safety', json.loads(message.data))
        except json.JSONDecodeError:
            pass

    def _pose(self):
        try:
            t = self.tf_buffer.lookup_transform(self.map_frame, self.base_frame, Time())
        except TransformException:
            return
        tr = t.transform
        self.hub.update('pose', {
            'x': round(tr.translation.x, 3), 'y': round(tr.translation.y, 3),
            'yaw': round(_yaw(tr.rotation), 3)})

    def _health(self):
        names = set(self.get_node_names())
        online = self.count_publishers('/delivery/status') > 0
        if online != self.hub.get('task_manager_online'):
            self.hub.update('task_manager_online', online)
        nodes = {name: name in names for name in WATCHED_NODES}
        if nodes != self.hub.get('nodes'):
            self.hub.update('nodes', nodes)

    # ----- web -> ROS (called from HTTP threads) ---------------------------

    def send_order(self, order):
        self.request_pub.publish(String(data=json.dumps(order)))

    def send_cancel(self, key):
        self.cancel_pub.publish(String(data=key))

    def send_confirm(self, key):
        self.confirm_pub.publish(String(data=key))

    def record_service(self, item_id):
        if self.usage is None:
            raise KeyError(item_id)
        with self.usage_lock:
            self.usage.record_service(item_id)
            self.usage.save()
            report = self.usage.report()
        self.hub.update('maintenance', report)
        return report

    def return_to_dock(self, timeout):
        if not self.dock_client.service_is_ready():
            return False, 'the task manager is not running'
        done = threading.Event()
        future = self.dock_client.call_async(Trigger.Request())
        future.add_done_callback(lambda _: done.set())
        if not done.wait(timeout):
            return False, 'the task manager did not answer'
        response = future.result()
        return bool(response.success), str(response.message)


def main(args=None):
    rclpy.init(args=args)
    hub = StateHub()
    node = UiNode(hub)
    get = lambda name, default: node.declare_parameter(name, default).value  # noqa: E731
    phase1_share = get_package_share_directory('cstam_phase1')
    ui_share = get_package_share_directory('cstam_ui')
    locations_file = get('locations_file', os.path.join(
        phase1_share, 'maps', 'restaurant', 'locations.yaml'))
    map_file = get('map_file', os.path.join(phase1_share, 'maps', 'restaurant', 'restaurant.yaml'))
    menu_file = get('menu_file', os.path.join(ui_share, 'config', 'menu.yaml'))
    web_dir = get('web_dir', os.path.join(ui_share, 'web'))
    order_log = get('order_log_file', '') or os.path.join(
        os.environ.get('ROS_HOME', os.path.expanduser('~/.ros')), 'cstam_orders.jsonl')
    host, port = get('host', '0.0.0.0'), int(get('port', 8080))
    usage_file = get('usage_file', '') or os.path.join(
        os.environ.get('ROS_HOME', os.path.expanduser('~/.ros')), 'cstam_robot_usage.json')
    node.attach_usage(UsageTracker(usage_file, load_schedule(
        get('maintenance_file', os.path.join(ui_share, 'config', 'maintenance.yaml')))))

    catalog = Catalog(locations_file, menu_file)
    try:
        map_png, map_meta = load_map(map_file)
    except (OSError, ValueError, KeyError) as error:
        node.get_logger().warn(f'map unavailable for the UI: {error}')
        map_png, map_meta = None, None
    # Printed QR cards point here; override when the address is not the one
    # phones should use (e.g. several networks, or a hostname).
    public_url = get('public_url', '') or f'http://{lan_address()}:{port}'
    server = UiServer(hub, catalog, node, web_dir, map_png, map_meta,
                      admin_pin=str(get('admin_pin', '0000')), order_log_file=order_log,
                      host=host, port=port, public_url=public_url)
    server.start()
    node.get_logger().info(
        f'CSTAM UI on {public_url}/ (admin: /admin'
        f'{", PIN required" if server.admin_pin else ""}; table QR codes: /qr)')
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        node.save_usage()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
