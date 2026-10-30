"""Simulated elevator between the dining room (floor 1) and the upper room (floor 2).

The restaurant's real shaft holds a visual-only cabin. A ride is called by
the task manager once the robot stands in the cabin
(/elevator/to_floor_1, /elevator/to_floor_2, std_srvs/Trigger):

1. check, from ground truth, that the robot is inside the cabin;
2. "close the doors", then move the cabin to the other floor (set_pose);
3. move the robot onto the other floor at the same x, y and heading. The
   move is purely vertical, so wheel odometry and AMCL's x/y stay valid;
4. load that floor's map in the map server, re-seed AMCL at the robot's
   current estimate and clear both costmaps of the floor left behind.

/elevator/state (JSON, latched) reports the floor, the cabin and whether a
ride is running. Ground truth is used only for the cabin's presence sensor
and to move bodies, as a real elevator's sensors and motor would.
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
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose
from std_msgs.msg import String
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
        self.declare_parameter('world_name', 'restaurant')
        self.declare_parameter('robot_model', 'cstam')
        self.declare_parameter('cabin_model', 'elevator_cabin')
        self.declare_parameter('robot_spawn_z', 0.02)   # spawn height above a floor
        self.declare_parameter('door_sec', 1.5)
        self.declare_parameter('travel_sec', 5.0)
        get = lambda name: self.get_parameter(name).value  # noqa: E731
        self.maps_dir = os.path.dirname(str(get('locations_file')))
        self.elevator = load_elevator(str(get('locations_file')))
        with open(str(get('alignment_file')), encoding='utf-8') as stream:
            a = yaml.safe_load(stream)['world_from_map']
        self.world_from_map = (float(a['x']), float(a['y']), float(a['yaw']))
        self.robot_model = str(get('robot_model'))
        self.cabin_model = str(get('cabin_model'))
        self.spawn_z = float(get('robot_spawn_z'))
        self.door_sec = float(get('door_sec'))
        self.travel_sec = float(get('travel_sec'))
        world = str(get('world_name'))

        group = ReentrantCallbackGroup()
        self.floor = 1
        self.busy = False
        self.message = 'ready at floor 1'
        self.truth = None   # (x, y, z, yaw) in the map frame, z absolute
        self.lock = threading.Lock()
        self.pose_client = self.create_client(
            SetEntityPose, f'/world/{world}/set_pose', callback_group=group)
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

    # Frames ----------------------------------------------------------------
    def _map_to_world(self, x, y, yaw=0.0):
        wx, wy, wyaw = self.world_from_map
        c, s = math.cos(wyaw), math.sin(wyaw)
        return wx + c * x - s * y, wy + s * x + c * y, yaw + wyaw

    def _truth_callback(self, message):
        p = message.pose.position
        wx, wy, wyaw = self.world_from_map
        c, s = math.cos(wyaw), math.sin(wyaw)
        dx, dy = p.x - wx, p.y - wy
        self.truth = (c * dx + s * dy, -s * dx + c * dy, p.z, _yaw(message.pose.orientation) - wyaw)
        if not self.busy:
            floor = floor_of_height(self.elevator, p.z)
            if floor != self.floor:   # e.g. a simulator reset
                self.floor = floor
                self._publish_state()

    def _publish_state(self):
        self.state_pub.publish(String(data=json.dumps({
            'floor': self.floor, 'busy': self.busy, 'message': self.message,
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

    def _set_pose(self, name, x, y, z, yaw, wait=True):
        wx, wy, wyaw = self._map_to_world(x, y, yaw)
        request = SetEntityPose.Request()
        request.entity.name = name
        request.entity.type = Entity.MODEL
        request.pose.position.x, request.pose.position.y, request.pose.position.z = wx, wy, z
        request.pose.orientation.z = math.sin(wyaw / 2.0)
        request.pose.orientation.w = math.cos(wyaw / 2.0)
        future = self.pose_client.call_async(request)
        if not wait:
            return True
        result = self._wait(future, 3.0)
        return bool(result and result.success)

    def _ride(self, target):
        floors = self.elevator['floors']
        if target not in floors:
            return False, f'no floor {target}'
        if target == self.floor:
            return True, f'already at floor {target}'
        if self.truth is None or not self.pose_client.wait_for_service(timeout_sec=2.0):
            return False, 'simulation not ready'
        x, y, _z, yaw = self.truth
        if not in_cabin(self.elevator, x, y):
            return False, f'robot is not in the cabin ({x:.2f}, {y:.2f})'
        start = self.floor
        self.message = f'going to floor {target}'
        self._publish_state()
        time.sleep(self.door_sec)   # doors close
        cx, cy = self.elevator['x'], self.elevator['cabin_y']
        h0, h1 = floors[start]['height'], floors[target]['height']
        steps = max(1, int(self.travel_sec * 10))
        for k in range(1, steps + 1):
            self._set_pose(self.cabin_model, cx, cy, h0 + (h1 - h0) * k / steps, 0.0, wait=False)
            time.sleep(self.travel_sec / steps)
        x, y, _z, yaw = self.truth   # the latest, in case it settled
        if not self._set_pose(self.robot_model, x, y, h1 + self.spawn_z, yaw):
            return False, 'could not move the robot'
        time.sleep(0.5)
        if abs(self.truth[2] - h1) > 0.3:
            return False, f'robot did not arrive (z {self.truth[2]:.2f})'
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
