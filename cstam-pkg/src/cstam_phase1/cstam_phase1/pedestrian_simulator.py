"""Scenario-driven pedestrians for the Gazebo restaurant, plus safety metrics.

Pedestrians are light visual-only Gazebo models (no skinned meshes, no extra
sensors) spawned once, then moved with the bridged set_pose service. The GPU
LiDAR renders them like any other geometry, so the robot perceives them only
through its own sensors.

The node also measures safety from ground truth: the clearance between the
real robot footprint (/model/cstam/pose) and each pedestrian, and publishes
JSON on /pedestrians/metrics. Reset with:
    ros2 service call /pedestrians/reset_metrics std_srvs/srv/Trigger '{}'
"""

import json
import math
import os

import numpy as np
import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose, SpawnEntity
from std_msgs.msg import String
from std_srvs.srv import Trigger
from visualization_msgs.msg import Marker, MarkerArray
import yaml

from cstam_phase1.pedestrian_model import (
    Pedestrian,
    PedestrianConfig,
    PedestrianParams,
    footprint_clearance,
)
from cstam_phase1.people_tracking import StaticMap


def pedestrian_sdf(name, color):
    r, g, b = color
    skin = '0.76 0.57 0.42 1'
    dark = '0.12 0.13 0.16 1'
    shirt = f'{r} {g} {b} 1'

    def visual(vname, pose, geometry, rgba):
        return (f'<visual name="{vname}"><pose>{pose}</pose><geometry>{geometry}'
                f'</geometry><material><ambient>{rgba}</ambient><diffuse>{rgba}'
                f'</diffuse></material></visual>')
    parts = [
        visual('left_leg', '0 0.09 0.43 0 0 0', '<box><size>0.14 0.13 0.86</size></box>', dark),
        visual('right_leg', '0 -0.09 0.43 0 0 0', '<box><size>0.14 0.13 0.86</size></box>', dark),
        visual('torso', '0 0 1.15 0 0 0',
               '<cylinder><radius>0.19</radius><length>0.60</length></cylinder>', shirt),
        visual('left_arm', '0 0.24 1.12 0 0 0', '<box><size>0.10 0.09 0.58</size></box>', shirt),
        visual('right_arm', '0 -0.24 1.12 0 0 0', '<box><size>0.10 0.09 0.58</size></box>', shirt),
        visual('head', '0.02 0 1.62 0 0 0', '<sphere><radius>0.13</radius></sphere>', skin),
    ]
    # Visual-only: a static collision would stay at the spawn pose forever,
    # because set_pose does not move static collision geometry.
    return (f'<sdf version="1.9"><model name="{name}"><static>true</static>'
            f'<link name="body">{"".join(parts)}</link></model></sdf>')


class PedestrianSimulator(Node):

    def __init__(self):
        super().__init__('cstam_pedestrian_simulator')
        share = get_package_share_directory('cstam_phase1')
        self.declare_parameter(
            'scenario_file', os.path.join(share, 'config', 'pedestrians.yaml'))
        self.declare_parameter(
            'alignment_file',
            os.path.join(share, 'maps', 'restaurant', 'world_alignment.yaml'))
        self.declare_parameter('world_name', 'restaurant')
        self.declare_parameter('update_rate_hz', 15.0)
        self.declare_parameter('robot_pose_topic', '/model/cstam/pose')
        self.declare_parameter('close_pass_clearance', 0.20)

        with open(str(self.get_parameter('scenario_file').value), encoding='utf-8') as f:
            scenario = yaml.safe_load(f) or {}
        with open(str(self.get_parameter('alignment_file').value), encoding='utf-8') as f:
            alignment = yaml.safe_load(f)['world_from_map']
        self.world_from_map = (
            float(alignment['x']), float(alignment['y']), float(alignment['yaw']))
        params = PedestrianParams(**(scenario.get('params') or {}))
        self.pedestrians = [
            Pedestrian(PedestrianConfig.from_dict(item), params)
            for item in scenario.get('pedestrians', [])]
        self.close_pass = float(self.get_parameter('close_pass_clearance').value)
        world = str(self.get_parameter('world_name').value)

        self.spawn_client = self.create_client(SpawnEntity, f'/world/{world}/create')
        self.pose_client = self.create_client(SetEntityPose, f'/world/{world}/set_pose')
        self.pending = {p.config.name: 0 for p in self.pedestrians}
        self.spawned = False
        self.spawn_futures = []
        self.static_map = None
        self.robot_pose = None
        self.robot_velocity = (0.0, 0.0)
        self.robot_yaw_rate = 0.0
        self.moved = {}  # metres each pedestrian moved in the last tick
        self.last_robot = None
        self.last_step = None
        self._reset_metrics()

        map_qos = QoSProfile(depth=1)
        map_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        map_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.create_subscription(OccupancyGrid, '/map', self._map_callback, map_qos)
        self.create_subscription(
            PoseStamped, str(self.get_parameter('robot_pose_topic').value),
            self._robot_callback, 10)
        self.metrics_pub = self.create_publisher(String, '/pedestrians/metrics', 10)
        self.marker_pub = self.create_publisher(MarkerArray, '/pedestrians/markers', 5)
        self.state_pub = self.create_publisher(String, '/pedestrians/state', 5)
        self.create_service(Trigger, '/pedestrians/reset_metrics', self._reset_callback)
        rate = float(self.get_parameter('update_rate_hz').value)
        self.create_timer(1.0 / rate, self._tick)
        self.create_timer(1.0, self._publish_metrics)
        self.create_timer(0.2, self._publish_markers)
        self.get_logger().info(
            f'{len(self.pedestrians)} pedestrians: '
            + ', '.join(f'{p.config.name} ({p.config.behavior})' for p in self.pedestrians))

    # Frames -------------------------------------------------------------
    def _map_to_world(self, x, y, yaw=0.0):
        wx, wy, wyaw = self.world_from_map
        c, s = math.cos(wyaw), math.sin(wyaw)
        return wx + c * x - s * y, wy + s * x + c * y, yaw + wyaw

    def _world_to_map(self, x, y, yaw=0.0):
        wx, wy, wyaw = self.world_from_map
        c, s = math.cos(wyaw), math.sin(wyaw)
        dx, dy = x - wx, y - wy
        return c * dx + s * dy, -s * dx + c * dy, yaw - wyaw

    # Inputs -------------------------------------------------------------
    def _map_callback(self, message):
        grid = np.array(message.data, dtype=np.int8).reshape(
            message.info.height, message.info.width)
        self.static_map = StaticMap(
            grid, message.info.resolution, message.info.origin.position.x,
            message.info.origin.position.y, margin=0.30)

    def _is_free(self, x, y):
        if self.static_map is None:
            return True
        return not bool(self.static_map.is_static(np.array([[x, y]]))[0])

    def _robot_callback(self, message):
        q = message.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        pose = self._world_to_map(message.pose.position.x, message.pose.position.y, yaw)
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.last_robot is not None:
            dt = now - self.last_robot[0]
            if dt > 0.02:
                self.robot_velocity = ((pose[0] - self.last_robot[1][0]) / dt,
                                       (pose[1] - self.last_robot[1][1]) / dt)
                self.robot_yaw_rate = math.remainder(
                    pose[2] - self.last_robot[1][2], math.tau) / dt
                self.last_robot = (now, pose)
        else:
            self.last_robot = (now, pose)
        self.robot_pose = pose

    # Spawning and motion --------------------------------------------------
    def _spawn_all(self):
        if not self.spawn_client.service_is_ready():
            return False
        for pedestrian in self.pedestrians:
            x, y = pedestrian.position
            wx, wy, wyaw = self._map_to_world(x, y, pedestrian.heading)
            request = SpawnEntity.Request()
            request.entity_factory.name = pedestrian.config.name
            request.entity_factory.allow_renaming = False
            request.entity_factory.sdf = pedestrian_sdf(
                pedestrian.config.name, pedestrian.config.color)
            request.entity_factory.pose.position.x = wx
            request.entity_factory.pose.position.y = wy
            request.entity_factory.pose.orientation.z = math.sin(wyaw / 2.0)
            request.entity_factory.pose.orientation.w = math.cos(wyaw / 2.0)
            self.spawn_futures.append(self.spawn_client.call_async(request))
        self.get_logger().info('Spawned pedestrians in Gazebo.')
        return True

    def _send_pose(self, pedestrian):
        name = pedestrian.config.name
        if self.pending[name] >= 2 or not self.pose_client.service_is_ready():
            return
        x, y = pedestrian.position
        wx, wy, wyaw = self._map_to_world(x, y, pedestrian.heading)
        request = SetEntityPose.Request()
        request.entity.name = name
        request.entity.type = Entity.MODEL
        request.pose.position.x = wx
        request.pose.position.y = wy
        request.pose.orientation.z = math.sin(wyaw / 2.0)
        request.pose.orientation.w = math.cos(wyaw / 2.0)
        self.pending[name] += 1
        future = self.pose_client.call_async(request)
        future.add_done_callback(lambda _f, n=name: self._pose_done(n))

    def _pose_done(self, name):
        self.pending[name] = max(0, self.pending[name] - 1)

    def _tick(self):
        if not self.spawned:
            self.spawned = self._spawn_all()
            return
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.last_step is None or now < self.last_step:
            self.last_step = now
            return
        dt = min(0.2, now - self.last_step)
        self.last_step = now
        if dt <= 0.0:
            return
        for pedestrian in self.pedestrians:
            before = pedestrian.position
            others = [p.position for p in self.pedestrians if p is not pedestrian]
            pedestrian.step(dt, self.robot_pose, others, self._is_free)
            after = pedestrian.position
            self.moved[pedestrian.config.name] = math.dist(before, after)
            if (before != after) or pedestrian.speed > 0.0:
                self._send_pose(pedestrian)
        self._update_metrics(now)

    # Metrics ------------------------------------------------------------
    def _reset_metrics(self):
        self.metrics_start = None
        self.min_clearance = math.inf
        # The robot is only responsible for distance it closes itself.
        self.min_clearance_moving = math.inf
        self.robot_speed_at_min = None
        self.per_pedestrian = {p.config.name: math.inf for p in self.pedestrians}
        self.contacts = 0
        self.robot_fault_contacts = 0
        self.close_passes = 0
        self.in_contact = set()
        self.in_close_pass = set()

    def _reset_callback(self, _request, response):
        self._reset_metrics()
        response.success = True
        response.message = 'pedestrian metrics reset'
        return response

    def _update_metrics(self, now):
        if self.robot_pose is None:
            return
        if self.metrics_start is None:
            self.metrics_start = now
        robot_speed = math.hypot(*self.robot_velocity)
        # Turning counts as moving: the corners sweep up to 0.456 m out.
        robot_moving = robot_speed > 0.02 or abs(self.robot_yaw_rate) > 0.05
        for pedestrian in self.pedestrians:
            name = pedestrian.config.name
            position = pedestrian.position
            clearance = footprint_clearance(self.robot_pose, position)
            if clearance < self.min_clearance:
                self.min_clearance = clearance
                self.robot_speed_at_min = robot_speed
            if robot_moving:
                self.min_clearance_moving = min(self.min_clearance_moving, clearance)
            self.per_pedestrian[name] = min(self.per_pedestrian[name], clearance)
            if clearance <= 0.0:
                if name not in self.in_contact:
                    self.in_contact.add(name)
                    self.contacts += 1
                    # People never step into the robot (the model forbids
                    # it), so if this person stood still while contact began,
                    # the robot closed the gap by driving or by turning.
                    robot_fault = robot_moving and self.moved.get(name, 0.0) < 0.005
                    self.robot_fault_contacts += int(robot_fault)
                    self.get_logger().warn(
                        f'CONTACT with {name} (robot {robot_speed:.2f} m/s, '
                        f'{self.robot_yaw_rate:+.2f} rad/s, '
                        f'{"robot" if robot_fault else "pedestrian"} closed the gap)')
            elif clearance > 0.05:
                self.in_contact.discard(name)
            if clearance < self.close_pass:
                if name not in self.in_close_pass:
                    self.in_close_pass.add(name)
                    self.close_passes += 1
            elif clearance > self.close_pass + 0.1:
                self.in_close_pass.discard(name)

    def _publish_metrics(self):
        if self.metrics_start is None:
            return
        current = None
        if self.robot_pose is not None and self.pedestrians:
            current = min(footprint_clearance(self.robot_pose, p.position)
                          for p in self.pedestrians)

        def rounded(value):
            return None if value is None or math.isinf(value) else round(value, 3)
        payload = {
            'elapsed_sec': round(self.get_clock().now().nanoseconds * 1e-9
                                 - self.metrics_start, 1),
            'min_clearance_m': rounded(self.min_clearance),
            'robot_speed_at_min_clearance_mps': rounded(self.robot_speed_at_min),
            'min_clearance_while_robot_moving_m': rounded(self.min_clearance_moving),
            'current_min_clearance_m': rounded(current),
            'contacts': self.contacts,
            'robot_fault_contacts': self.robot_fault_contacts,
            'close_passes_under_m': self.close_pass,
            'close_passes': self.close_passes,
            'per_pedestrian_min_clearance_m': {
                k: rounded(v) for k, v in self.per_pedestrian.items()},
        }
        self.metrics_pub.publish(String(data=json.dumps(payload)))

    def _publish_markers(self):
        # Named ground truth for evaluation (map frame).
        self.state_pub.publish(String(data=json.dumps({
            p.config.name: [round(p.position[0], 3), round(p.position[1], 3)]
            for p in self.pedestrians})))
        markers = MarkerArray()
        for index, pedestrian in enumerate(self.pedestrians):
            x, y = pedestrian.position
            marker = Marker()
            marker.header.frame_id = 'map'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns, marker.id = 'ground_truth', index
            marker.type = Marker.CYLINDER
            marker.pose.position.x, marker.pose.position.y = x, y
            marker.pose.position.z = 0.01
            marker.pose.orientation.w = 1.0
            marker.scale.x = marker.scale.y = 0.44
            marker.scale.z = 0.02
            marker.color.g, marker.color.b, marker.color.a = 0.9, 0.3, 0.8
            markers.markers.append(marker)
        self.marker_pub.publish(markers)


def main(args=None):
    rclpy.init(args=args)
    node = PedestrianSimulator()
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
