"""Elevator between the dining room (floor 1) and the upper room (floor 2).

The restaurant's shaft holds a cabin whose platform rides a prismatic joint
in Gazebo (world: elevator_cabin) and physically carries the robot. A ride
is called by the task manager once the robot stands in the cabin
(/elevator/to_floor_1, /elevator/to_floor_2, std_srvs/Trigger):

1. check that the cabin is at the robot's floor and the robot is inside it
   and standing still (ground truth: the cabin's presence sensor);
2. "close the doors", then drive the lift joint (/elevator/lift/cmd_vel)
   with a smooth speed profile, reading its position (/elevator/joint_state);
3. confirm the robot arrived with the platform. The ride is vertical, so
   wheel odometry and AMCL's x/y stay valid;
4. load that floor's map in the map server, re-seed AMCL at the robot's
   current estimate and clear both costmaps of the floor left behind.

/elevator/state (JSON, latched) reports the floor, the cabin height and
whether a ride is running.
"""

import json
import math
import os
import threading
import time

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.srv import ClearEntireCostmap, LoadMap
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformException, TransformListener
import yaml


def load_elevator(path):
    """The `elevator` section of locations.yaml, floors keyed by int."""
    with open(path, encoding='utf-8') as stream:
        data = (yaml.safe_load(stream) or {}).get('elevator')
    if not data:
        return None
    return {'x': float(data['x']), 'cabin_y': float(data['cabin_y']),
            'floors': {int(k): {'map': str(v['map']), 'height': float(v['height']),
                                'lobby_y': float(v['lobby_y']), 'enter_yaw': float(v['enter_yaw'])}
                       for k, v in data['floors'].items()}}


def ride_legs(elevator, start_floor, target_floor):
    """Waypoint legs from start_floor's lobby to target_floor's lobby."""
    if elevator is None or start_floor == target_floor:
        return []
    a, b = elevator['floors'][start_floor], elevator['floors'][target_floor]
    yaw, x = a['enter_yaw'], elevator['x']
    return [{'name': f'elevator_lobby_f{start_floor}', 'x': x, 'y': a['lobby_y'], 'yaw': yaw},
            {'name': f'elevator_cabin_f{start_floor}', 'x': x, 'y': elevator['cabin_y'], 'yaw': yaw},
            {'name': f'elevator_ride_f{target_floor}', 'ride': target_floor},
            {'name': f'elevator_exit_f{target_floor}', 'x': x, 'y': b['lobby_y'], 'yaw': yaw}]


def in_cabin(elevator, x, y, tolerance=0.45):
    return abs(x - elevator['x']) <= tolerance and abs(y - elevator['cabin_y']) <= tolerance


def lift_command(position, target, velocity, dt, max_speed=0.35, accel=0.25,
                 tolerance=0.003, creep=0.02):
    """Next lift velocity: ramp up by accel, brake so as to stop at target.

    Braking follows the stopping-distance curve but never sheds more than
    2 * accel per second, so a robot on the platform feels no jolt.
    """
    remaining = target - position
    if abs(remaining) <= tolerance:
        return 0.0
    speed = min(max_speed, math.sqrt(2.0 * accel * abs(remaining)), abs(velocity) + accel * dt)
    speed = max(speed, abs(velocity) - 2.0 * accel * dt)
    return math.copysign(max(speed, creep), remaining)


def floor_of_height(elevator, z):
    """Floor whose height is closest to a ground-truth z."""
    return min(elevator['floors'], key=lambda f: abs(elevator['floors'][f]['height'] - z))


def _yaw(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class Elevator(Node):

    def __init__(self):
        super().__init__('cstam_elevator')
        share = get_package_share_directory('cstam_phase1')
        maps = os.path.join(share, 'maps', 'restaurant')
        self.declare_parameter('locations_file', os.path.join(maps, 'locations.yaml'))
        self.declare_parameter('alignment_file', os.path.join(maps, 'world_alignment.yaml'))
        self.declare_parameter('robot_model', 'cstam')
        self.declare_parameter('door_sec', 1.5)
        self.declare_parameter('max_speed', 0.35)     # m/s
        self.declare_parameter('acceleration', 0.25)  # m/s^2
        self.declare_parameter('ride_timeout_sec', 30.0)
        get = lambda name: self.get_parameter(name).value  # noqa: E731
        self.maps_dir = os.path.dirname(str(get('locations_file')))
        self.elevator = load_elevator(str(get('locations_file')))
        with open(str(get('alignment_file')), encoding='utf-8') as stream:
            a = yaml.safe_load(stream)['world_from_map']
        self.world_from_map = (float(a['x']), float(a['y']), float(a['yaw']))
        self.robot_model = str(get('robot_model'))
        self.door_sec = float(get('door_sec'))
        self.max_speed = float(get('max_speed'))
        self.accel = float(get('acceleration'))
        self.ride_timeout = float(get('ride_timeout_sec'))

        group = ReentrantCallbackGroup()
        self.floor = 1
        self.busy = False
        self.message = 'ready at floor 1'
        self.truth = None   # (x, y, z, yaw) in the map frame, z absolute
        self.truth_at = 0.0
        self.lift = None    # cabin height (lift joint position)
        self.lock = threading.Lock()
        self.lift_pub = self.create_publisher(Float64, '/elevator/lift/cmd_vel', 10)
        self.create_subscription(JointState, '/elevator/joint_state', self._joint_callback, 10,
                                 callback_group=group)
        self.map_client = self.create_client(
            LoadMap, '/map_server/load_map', callback_group=group)
        self.clear_clients = [self.create_client(ClearEntireCostmap, name, callback_group=group)
                              for name in ('/global_costmap/clear_entirely_global_costmap',
                                           '/local_costmap/clear_entirely_local_costmap')]
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(PoseStamped, f'/model/{self.robot_model}/pose',
                                 self._truth_callback, 10, callback_group=group)
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)
        latched = QoSProfile(depth=1)
        latched.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        latched.reliability = QoSReliabilityPolicy.RELIABLE
        self.state_pub = self.create_publisher(String, '/elevator/state', latched)
        for floor in self.elevator['floors']:
            self.create_service(
                Trigger, f'/elevator/to_floor_{floor}',
                lambda request, response, f=floor: self._ride_callback(f, response),
                callback_group=group)
        self._publish_state()
        self.get_logger().info(
            f'elevator ready: floors {sorted(self.elevator["floors"])}, cabin at '
            f'({self.elevator["x"]:.2f}, {self.elevator["cabin_y"]:.2f})')

    # Inputs ----------------------------------------------------------------
    def _joint_callback(self, message):
        if 'lift' in message.name:
            self.lift = float(message.position[list(message.name).index('lift')])

    def _truth_callback(self, message):
        p = message.pose.position
        wx, wy, wyaw = self.world_from_map
        c, s = math.cos(wyaw), math.sin(wyaw)
        dx, dy = p.x - wx, p.y - wy
        self.truth = (c * dx + s * dy, -s * dx + c * dy, p.z, _yaw(message.pose.orientation) - wyaw)
        self.truth_at = time.monotonic()
        if not self.busy:
            floor = floor_of_height(self.elevator, p.z)
            if floor != self.floor:   # e.g. a simulator reset
                self.floor = floor
                self._publish_state()

    def _publish_state(self):
        self.state_pub.publish(String(data=json.dumps({
            'floor': self.floor, 'busy': self.busy, 'message': self.message,
            'cabin_height': None if self.lift is None else round(self.lift, 3),
            'floors': sorted(self.elevator['floors'])})))

    # Ride ---------------------------------------------------------------------
    def _ride_callback(self, target, response):
        with self.lock:
            if self.busy:
                response.success, response.message = False, 'elevator busy'
                return response
            self.busy = True
        try:
            response.success, response.message = self._ride(target)
        except Exception as error:  # never leave the elevator stuck busy
            response.success, response.message = False, f'ride failed: {error}'
        self.busy = False
        self.message = response.message
        self._publish_state()
        self.get_logger().info(f'ride to floor {target}: {response.message}')
        return response

    def _wait(self, future, timeout):
        end = time.monotonic() + timeout
        while not future.done() and time.monotonic() < end:
            time.sleep(0.02)
        return future.result() if future.done() else None

    def _robot_still(self, wait=6.0, window=0.6, tolerance=0.01):
        """True once the robot stays put for `window` s (within `wait` s)."""
        end = time.monotonic() + wait
        while self.truth is not None and time.monotonic() < end:
            before = self.truth
            time.sleep(window)
            if math.hypot(self.truth[0] - before[0], self.truth[1] - before[1]) < tolerance:
                return True
        return False

    def _drive_lift(self, target):
        """Run the lift to `target` height; True once there."""
        velocity, dt = 0.0, 0.05
        end = time.monotonic() + self.ride_timeout
        while time.monotonic() < end:
            if self.lift is None:
                return False
            velocity = lift_command(self.lift, target, velocity, dt, self.max_speed, self.accel)
            self.lift_pub.publish(Float64(data=velocity))
            if velocity == 0.0:
                return True
            time.sleep(dt)
        self.lift_pub.publish(Float64(data=0.0))
        return False

    def _ride(self, target):
        floors = self.elevator['floors']
        if target not in floors:
            return False, f'no floor {target}'
        if target == self.floor:
            return True, f'already at floor {target}'
        if self.truth is None or self.lift is None or time.monotonic() - self.truth_at > 2.0:
            return False, 'simulation not ready'
        start = self.floor
        h0, h1 = floors[start]['height'], floors[target]['height']
        if abs(self.lift - h0) > 0.05:
            # The cabin is elsewhere (e.g. after a reset): call it to this floor first.
            self.message = f'calling the cabin to floor {start}'
            self._publish_state()
            if not self._drive_lift(h0):
                return False, 'the cabin did not come'
        x, y, _z, _yaw = self.truth
        if not in_cabin(self.elevator, x, y):
            return False, f'robot is not in the cabin ({x:.2f}, {y:.2f})'
        if not self._robot_still():
            return False, 'robot is still moving'
        self.message = f'going to floor {target}'
        self._publish_state()
        time.sleep(self.door_sec)   # doors close
        if not self._drive_lift(h1):
            return False, f'the lift stopped at {self.lift:.2f} m'
        time.sleep(0.5)
        if abs(self.truth[2] - h1) > 0.15:
            return False, f'robot did not ride with the cabin (z {self.truth[2]:.2f})'
        self.floor = target
        map_ok = self._load_map(floors[target]['map'])
        self._reseed_amcl()
        self._clear_costmaps()
        time.sleep(self.door_sec)   # doors open
        if not map_ok:
            return False, f'at floor {target} but its map did not load'
        return True, f'arrived at floor {target}'

    def _load_map(self, name):
        if not self.map_client.wait_for_service(timeout_sec=3.0):
            return False
        request = LoadMap.Request()
        request.map_url = os.path.join(self.maps_dir, name)
        result = self._wait(self.map_client.call_async(request), 10.0)
        return bool(result is not None and result.result == LoadMap.Response.RESULT_SUCCESS)

    def _reseed_amcl(self):
        """AMCL keeps its x/y; tell it so on the new map, with a tight spread."""
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time())
        except TransformException:
            return
        message = PoseWithCovarianceStamped()
        message.header.frame_id = 'map'
        message.header.stamp = self.get_clock().now().to_msg()
        message.pose.pose.position.x = t.transform.translation.x
        message.pose.pose.position.y = t.transform.translation.y
        message.pose.pose.orientation = t.transform.rotation
        message.pose.covariance[0] = message.pose.covariance[7] = 0.05 ** 2
        message.pose.covariance[35] = 0.03 ** 2
        time.sleep(0.5)   # let AMCL take the new map first
        self.initial_pose_pub.publish(message)

    def _clear_costmaps(self):
        time.sleep(0.5)
        for client in self.clear_clients:
            if client.wait_for_service(timeout_sec=1.0):
                self._wait(client.call_async(ClearEntireCostmap.Request()), 3.0)


def main(args=None):
    rclpy.init(args=args)
    node = Elevator()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
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
