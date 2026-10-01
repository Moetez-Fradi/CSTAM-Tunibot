"""Small, explicit first-floor delivery state machine for CSTAM.

The node deliberately delegates motion to Nav2's real NavigateToPose action.
It only resolves semantic locations, queues requests, and advances task state
when Nav2 reports a real result.
"""

from collections import deque
import json
import math
import os

import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger
import yaml


class DeliveryTaskManager(Node):
    STATES = {
        'IDLE', 'NAVIGATING_TO_PICKUP', 'NAVIGATING_TO_CUSTOMER',
        'DELIVERY_COMPLETE', 'RETURNING_TO_DOCK', 'ERROR',
    }

    def __init__(self):
        super().__init__('cstam_delivery_task_manager')
        default_locations = os.path.join(
            get_package_share_directory('cstam_phase1'),
            'maps', 'restaurant', 'locations.yaml')
        self.declare_parameter('locations_file', default_locations)
        self.declare_parameter('pickup_location', 'kitchen')
        self.declare_parameter('dock_location', 'dock')
        self.declare_parameter('frame_id', 'map')

        self.locations_file = str(self.get_parameter('locations_file').value)
        self.pickup_location = str(self.get_parameter('pickup_location').value)
        self.dock_location = str(self.get_parameter('dock_location').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.locations = self._load_locations(self.locations_file)
        self.queue = deque()
        self.current_location = None
        self.current_stage = None
        self.current_goal_handle = None
        self.goal_request_pending = False
        self.manual_dock_requested = False
        self.state = 'IDLE'
        self.last_message = 'ready'
        self.last_result = None

        status_qos = QoSProfile(depth=1)
        status_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        status_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.status_publisher = self.create_publisher(
            String, '/delivery/status', status_qos)
        self.request_subscription = self.create_subscription(
            String, '/delivery/request', self._request_callback, 10)
        self.return_service = self.create_service(
            Trigger, '/delivery/return_to_dock', self._return_to_dock_callback)
        self.status_service = self.create_service(
            Trigger, '/delivery/status', self._status_callback)
        self.navigator = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.create_timer(0.5, self._start_queued_task)
        self._publish_status('ready')
        self.get_logger().info(
            f'Loaded first-floor locations: {sorted(self.locations)}')

    @staticmethod
    def _load_locations(path):
        try:
            with open(path, encoding='utf-8') as stream:
                data = yaml.safe_load(stream) or {}
        except (OSError, yaml.YAMLError) as error:
            raise RuntimeError(f'Cannot load locations file {path}: {error}') from error
        locations = {}
        for name, value in data.items():
            if name == 'supported_floors' or not isinstance(value, dict):
                continue
            try:
                floor = int(value['floor'])
                locations[str(name)] = {
                    'floor': floor,
                    'x': float(value['x']),
                    'y': float(value['y']),
                    'yaw': float(value['yaw']),
                }
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError(f'Invalid location {name}: {error}') from error
        return locations

    def _request_callback(self, message):
        location = message.data.strip().lower()
        if not location:
            self._reject('empty delivery location')
            return
        if location not in self.locations:
            self._reject(
                f'unknown location "{location}"; valid locations: '
                f'{", ".join(sorted(self.locations))}')
            return
        if self.locations[location]['floor'] != 1:
            self._reject(f'location "{location}" is not on supported floor 1')
            return
        if location in self.queue or location == self.current_location:
            self._reject(f'duplicate request for "{location}"')
            return
        self.queue.append(location)
        self.last_message = f'queued {location}'
        self._publish_status(self.last_message)
        self.get_logger().info(
            f'Queued delivery to {location}; queue={list(self.queue)}')
        self._start_queued_task()

    def _return_to_dock_callback(self, _request, response):
        if self.dock_location not in self.locations:
            response.success = False
            response.message = 'dock is missing from locations.yaml'
            return response
        if self.state == 'RETURNING_TO_DOCK' and self.current_stage == 'dock':
            response.success = True
            response.message = 'already returning to dock'
            return response
        self.manual_dock_requested = True
        if self.goal_request_pending:
            self.state = 'RETURNING_TO_DOCK'
            self._publish_status('return-to-dock requested; waiting for goal acknowledgement')
        elif self.current_goal_handle is not None:
            self.get_logger().warn('Cancelling current navigation to return to dock.')
            self.current_goal_handle.cancel_goal_async()
            self.state = 'RETURNING_TO_DOCK'
            self._publish_status('return-to-dock requested; cancelling current goal')
        elif self.state != 'RETURNING_TO_DOCK':
            self.current_location = None
            self.current_stage = 'dock'
            self.state = 'RETURNING_TO_DOCK'
            self._send_navigation_goal(self.dock_location, 'dock')
        response.success = True
        response.message = 'return-to-dock requested'
        return response

    def _status_callback(self, _request, response):
        response.success = True
        response.message = json.dumps(self._status_payload(), sort_keys=True)
        return response

    def _start_queued_task(self):
        if self.current_goal_handle is not None or self.goal_request_pending:
            return
        if self.state not in ('IDLE', 'DELIVERY_COMPLETE'):
            return
        if self.manual_dock_requested:
            return
        if not self.queue:
            if self.state == 'DELIVERY_COMPLETE':
                self._return_to_dock()
            return
        self.current_location = self.queue.popleft()
        self.current_stage = 'pickup'
        self.state = 'NAVIGATING_TO_PICKUP'
        self._publish_status(f'going to pickup for {self.current_location}')
        self._send_navigation_goal(self.pickup_location, 'pickup')

    def _return_to_dock(self):
        self.current_stage = 'dock'
        self.state = 'RETURNING_TO_DOCK'
        self._publish_status('returning to first-floor dock')
        self._send_navigation_goal(self.dock_location, 'dock')

    def _send_navigation_goal(self, location, stage):
        if location not in self.locations:
            self._fail(f'cannot navigate: missing semantic location {location}')
            return
        if not self.navigator.wait_for_server(timeout_sec=0.5):
            self._fail('navigate_to_pose action server is unavailable')
            return
        pose_data = self.locations[location]
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.frame_id
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = pose_data['x']
        goal.pose.pose.position.y = pose_data['y']
        goal.pose.pose.orientation.z = math.sin(pose_data['yaw'] / 2.0)
        goal.pose.pose.orientation.w = math.cos(pose_data['yaw'] / 2.0)
        self.current_stage = stage
        self.get_logger().info(
            f'NavigateToPose: stage={stage}, location={location}, '
            f'x={pose_data["x"]:.2f}, y={pose_data["y"]:.2f}')
        self.goal_request_pending = True
        future = self.navigator.send_goal_async(
            goal, feedback_callback=self._feedback_callback)
        future.add_done_callback(
            lambda completed, target=location, target_stage=stage:
            self._goal_response_callback(completed, target, target_stage))

    def _goal_response_callback(self, future, location, stage):
        self.goal_request_pending = False
        try:
            handle = future.result()
        except Exception as error:
            self._fail(f'Nav2 goal request failed: {error}')
            return
        if handle is None or not handle.accepted:
            self._fail(f'Nav2 rejected goal for {location}')
            return
        self.current_goal_handle = handle
        if self.manual_dock_requested and stage != 'dock':
            handle.cancel_goal_async()
        result_future = handle.get_result_async()
        result_future.add_done_callback(
            lambda completed: self._goal_result_callback(completed, location, stage))

    def _feedback_callback(self, feedback_message):
        distance = getattr(feedback_message.feedback, 'distance_remaining', None)
        if distance is not None:
            self.last_message = f'{self.current_stage}: {distance:.2f} m remaining'
            self._publish_status(self.last_message, log=False)

    def _goal_result_callback(self, future, location, stage):
        self.current_goal_handle = None
        try:
            result = future.result()
            status = result.status
        except Exception as error:
            self._fail(f'Nav2 result unavailable for {location}: {error}')
            return
        self.last_result = int(status)
        # A manual return wins even if the previous goal finishes before its
        # cancellation is processed. A failed dock goal must stop in ERROR,
        # rather than recursively retrying forever.
        if self.manual_dock_requested and stage != 'dock':
            self._return_to_dock()
            return
        if status != GoalStatus.STATUS_SUCCEEDED:
            self._fail(
                f'Nav2 failed at {location} with action status {int(status)}')
            return

        if stage == 'pickup':
            self.state = 'NAVIGATING_TO_CUSTOMER'
            self._publish_status(f'pickup reached; going to {self.current_location}')
            self._send_navigation_goal(self.current_location, 'customer')
        elif stage == 'customer':
            delivered = self.current_location
            self.state = 'DELIVERY_COMPLETE'
            self._publish_status(f'delivery complete at {delivered}')
            self.current_location = None
            if self.queue:
                self.state = 'IDLE'
                self._start_queued_task()
            else:
                self._return_to_dock()
        elif stage == 'dock':
            self.manual_dock_requested = False
            self.current_location = None
            self.current_stage = None
            self.state = 'IDLE'
            self._publish_status('IDLE at first-floor dock')

    def _fail(self, message):
        self.current_goal_handle = None
        self.goal_request_pending = False
        self.manual_dock_requested = False
        self.state = 'ERROR'
        self.last_message = message
        self._publish_status(message)
        self.get_logger().error(message)

    def _reject(self, message):
        self.last_message = f'rejected: {message}'
        self._publish_status(self.last_message)
        self.get_logger().warn(self.last_message)

    def _status_payload(self):
        return {
            'state': self.state,
            'current_location': self.current_location,
            'current_stage': self.current_stage,
            'queue': list(self.queue),
            'last_result': self.last_result,
            'message': self.last_message,
        }

    def _publish_status(self, message, log=True):
        self.last_message = message
        self.status_publisher.publish(String(data=json.dumps(self._status_payload())))
        if log:
            self.get_logger().info(message)


def main(args=None):
    rclpy.init(args=args)
    node = DeliveryTaskManager()
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
