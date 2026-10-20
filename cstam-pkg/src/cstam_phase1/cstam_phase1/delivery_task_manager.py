"""Small, explicit first-floor delivery state machine for CSTAM.

The node deliberately delegates motion to Nav2's real NavigateToPose action.
It only resolves semantic locations, queues requests, and advances task state
when Nav2 reports a real result.

Battery policy (sensor_msgs/BatteryState on /battery/state):
- below min_start_percentage a new delivery is not started; the robot goes
  to (or stays at) the dock and charges until resume_percentage;
- below low_battery_percentage an active delivery is interrupted, its order
  is requeued at the front, and the robot returns to the dock to charge;
- at 0% the active goal is cancelled and the robot reports BATTERY_DEPLETED.

Navigation failure policy: Nav2 already runs its own recoveries (clear,
wait, back up). If it still aborts, the same goal is retried up to
goal_retries times, retry_delay_sec apart (a person in a doorway usually
moves on). A pickup or customer goal that still fails is given up: the order
is recorded in failed_orders and the robot returns to the dock and carries
on with the queue. A dock goal that still fails ends in ERROR.

Doors: a trip between the dining room and the terrace is routed square
through a terrace door (inside staging pose, outside staging pose, target).
Sharp turns inside a 0.92 m doorway otherwise stalled the controller. If a
door leg still fails after its retries, the other door is tried before the
order is given up.
"""

from collections import deque
import json
import math
import os

import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from std_srvs.srv import Trigger
import yaml


class DeliveryTaskManager(Node):
    STATES = {
        'IDLE', 'NAVIGATING_TO_PICKUP', 'NAVIGATING_TO_CUSTOMER',
        'DELIVERY_COMPLETE', 'RETURNING_TO_DOCK', 'CHARGING',
        'BATTERY_DEPLETED', 'ERROR',
    }
    DELIVERY_STATES = {
        'NAVIGATING_TO_PICKUP', 'NAVIGATING_TO_CUSTOMER', 'DELIVERY_COMPLETE',
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
        # One complete restaurant delivery uses roughly 10-15% with the default
        # battery model, so starting above 35% leaves a reserve above 20%.
        self.declare_parameter('min_start_percentage', 35.0)
        self.declare_parameter('low_battery_percentage', 20.0)
        self.declare_parameter('resume_percentage', 80.0)
        self.declare_parameter('goal_retries', 3)
        self.declare_parameter('retry_delay_sec', 5.0)
        # Through a clear door the planned path is ~1.4 m; much longer means
        # the planner is going around: the door is blocked.
        self.declare_parameter('door_path_max_m', 2.5)
        self.declare_parameter('door_recheck_sec', 5.0)

        self.locations_file = str(self.get_parameter('locations_file').value)
        self.pickup_location = str(self.get_parameter('pickup_location').value)
        self.dock_location = str(self.get_parameter('dock_location').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.min_start_percentage = float(
            self.get_parameter('min_start_percentage').value)
        self.low_battery_percentage = float(
            self.get_parameter('low_battery_percentage').value)
        self.resume_percentage = float(self.get_parameter('resume_percentage').value)
        self.goal_retries = int(self.get_parameter('goal_retries').value)
        self.retry_delay = float(self.get_parameter('retry_delay_sec').value)
        self.door_path_max = float(self.get_parameter('door_path_max_m').value)
        self.door_recheck = float(self.get_parameter('door_recheck_sec').value)
        self.door_checks = 0
        self.goal_attempts = 0
        self.retry_timer = None
        self.failed_orders = []
        self.locations = self._load_locations(self.locations_file)
        self.doors = self._load_doors(self.locations_file)
        self.zone = 'room'           # the robot starts at the dock, indoors
        self.last_terrace_y = 0.0
        self.legs = []               # remaining waypoint legs of this stage
        self.door_tried = set()      # doors already given up for this stage
        self.door_in_use = None
        self.queue = deque()
        self.current_location = None
        self.current_stage = None
        self.current_goal_handle = None
        self.goal_request_pending = False
        self.manual_dock_requested = False
        self.state = 'IDLE'
        self.last_message = 'ready'
        self.last_result = None
        # Unknown until the first BatteryState; without a battery node the
        # manager behaves exactly as before.
        self.battery_percentage = None
        self.battery_charging = False
        self.battery_return = False
        # Normal mode spawns at the dock.
        self.at_dock = True

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
        battery_qos = QoSProfile(depth=1)
        battery_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        battery_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.battery_subscription = self.create_subscription(
            BatteryState, '/battery/state', self._battery_callback, battery_qos)
        self.navigator = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.path_planner = ActionClient(self, ComputePathToPose, 'compute_path_to_pose')
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
            if name in ('supported_floors', 'doors') or not isinstance(value, dict):
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

    @staticmethod
    def _load_doors(path):
        with open(path, encoding='utf-8') as stream:
            data = (yaml.safe_load(stream) or {}).get('doors')
        if not data:
            return None
        doors = {name: float(value['y']) for name, value in data.items()
                 if isinstance(value, dict)}
        return {'terrace_x': float(data['terrace_x']), 'inside_x': float(data['inside_x']),
                'outside_x': float(data['outside_x']), 'y': doors}

    def _zone_of(self, pose):
        if self.doors is None:
            return 'room'
        return 'terrace' if pose['x'] < self.doors['terrace_x'] else 'room'

    def _door_legs(self, door, outbound):
        """Waypoint poses square through a door (outbound = room to terrace)."""
        d = self.doors
        y = d['y'][door]
        yaw = math.pi if outbound else 0.0
        first, second = (d['inside_x'], d['outside_x']) if outbound else (
            d['outside_x'], d['inside_x'])
        return [{'name': f'{door}_{"out" if outbound else "in"}_1', 'x': first, 'y': y, 'yaw': yaw},
                {'name': f'{door}_{"out" if outbound else "in"}_2', 'x': second, 'y': y, 'yaw': yaw}]

    def _plan_legs(self, location):
        """Waypoint legs before `location`, choosing an untried door."""
        target = self.locations[location]
        target_zone = self._zone_of(target)
        if self.doors is None or target_zone == self.zone:
            return []
        terrace_y = target['y'] if target_zone == 'terrace' else self.last_terrace_y
        candidates = sorted(self.doors['y'], key=lambda d: abs(self.doors['y'][d] - terrace_y))
        untried = [d for d in candidates if d not in self.door_tried]
        if not untried:
            return None
        self.door_in_use = untried[0]
        return self._door_legs(self.door_in_use, outbound=target_zone == 'terrace')

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
        response.success, response.message = self._request_dock_return('manual')
        return response

    def _request_dock_return(self, reason):
        if self.dock_location not in self.locations:
            return False, 'dock is missing from locations.yaml'
        if self.state == 'RETURNING_TO_DOCK' and self.current_stage == 'dock':
            return True, 'already returning to dock'
        self.get_logger().info(f'Return to dock requested ({reason}).')
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
            # Possibly waiting between navigation retries: keep the order.
            self._cancel_retry()
            if self.current_location is not None:
                self._requeue_interrupted_order()
            self.current_stage = 'dock'
            self.state = 'RETURNING_TO_DOCK'
            self._navigate(self.dock_location, 'dock')
        return True, 'return-to-dock requested'

    def _battery_callback(self, message):
        percentage = 100.0 * float(message.percentage)
        if not math.isfinite(percentage):
            return
        self.battery_percentage = percentage
        self.battery_charging = message.power_supply_status in (
            BatteryState.POWER_SUPPLY_STATUS_CHARGING,
            BatteryState.POWER_SUPPLY_STATUS_FULL)

        if percentage <= 0.0:
            if self.state != 'BATTERY_DEPLETED':
                self._battery_depleted()
            return
        if self.state == 'BATTERY_DEPLETED':
            # Only reachable after an external recharge or level override.
            if percentage >= self.low_battery_percentage:
                self.state = 'IDLE' if self.at_dock else 'ERROR'
                self._publish_status(
                    f'battery restored to {percentage:.0f}%'
                    + ('' if self.at_dock else '; robot is not at dock'))
            return
        if self.state == 'CHARGING':
            if percentage >= self.resume_percentage:
                self.battery_return = False
                self.state = 'IDLE'
                self._publish_status(f'charged to {percentage:.0f}%; resuming')
                self._start_queued_task()
            return
        if (percentage <= self.low_battery_percentage
                and self.state in self.DELIVERY_STATES
                and not self.manual_dock_requested):
            self.battery_return = True
            self._publish_status(
                f'low battery {percentage:.0f}%; returning to dock to charge')
            self._request_dock_return('low battery')

    def _battery_depleted(self):
        if self.current_goal_handle is not None:
            self.current_goal_handle.cancel_goal_async()
        if self.current_location is not None and self.current_location not in self.queue:
            self.queue.appendleft(self.current_location)
        self.current_location = None
        self.current_goal_handle = None
        self.manual_dock_requested = False
        self.state = 'BATTERY_DEPLETED'
        self._publish_status('battery depleted; robot stopped')
        self.get_logger().error('Battery depleted; navigation cancelled.')

    def _battery_low_for_new_task(self):
        return (self.battery_percentage is not None
                and self.battery_percentage < self.min_start_percentage)

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
        if self._battery_low_for_new_task():
            self.battery_return = True
            if not self.at_dock:
                self._publish_status(
                    f'battery {self.battery_percentage:.0f}% too low for a new '
                    'delivery; returning to dock')
                self._return_to_dock()
            else:
                self.state = 'CHARGING'
                self._publish_status(
                    f'charging at dock from {self.battery_percentage:.0f}%')
            return
        if not self.queue:
            if self.state == 'DELIVERY_COMPLETE':
                self._return_to_dock()
            return
        self.current_location = self.queue.popleft()
        self.current_stage = 'pickup'
        self.state = 'NAVIGATING_TO_PICKUP'
        self._publish_status(f'going to pickup for {self.current_location}')
        self._navigate(self.pickup_location, 'pickup')

    def _return_to_dock(self):
        self.current_stage = 'dock'
        self.state = 'RETURNING_TO_DOCK'
        self._publish_status('returning to first-floor dock')
        self._navigate(self.dock_location, 'dock')

    def _navigate(self, location, stage):
        """Start a stage towards `location`, through a door when needed."""
        self.door_tried = set()
        self.goal_attempts = 0
        legs = self._plan_legs(location) if location in self.locations else []
        self.legs = (legs or []) + [location]
        self._send_next_leg(stage)

    def _send_next_leg(self, stage):
        leg = self.legs[0]
        if isinstance(leg, dict):
            self._send_pose_goal(leg['name'], leg, stage)
        else:
            self._send_navigation_goal(leg, stage)

    def _send_navigation_goal(self, location, stage):
        if location not in self.locations:
            self._fail(f'cannot navigate: missing semantic location {location}')
            return
        self._send_pose_goal(location, self.locations[location], stage)

    def _send_pose_goal(self, location, pose_data, stage):
        if not self.navigator.wait_for_server(timeout_sec=0.5):
            self._fail('navigate_to_pose action server is unavailable')
            return
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.frame_id
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = pose_data['x']
        goal.pose.pose.position.y = pose_data['y']
        goal.pose.pose.orientation.z = math.sin(pose_data['yaw'] / 2.0)
        goal.pose.pose.orientation.w = math.cos(pose_data['yaw'] / 2.0)
        self.current_stage = stage
        self.at_dock = False
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
        if self.state == 'BATTERY_DEPLETED' or (
                self.manual_dock_requested and stage != 'dock'):
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
        if self.state == 'BATTERY_DEPLETED':
            return
        # A manual return wins even if the previous goal finishes before its
        # cancellation is processed. A failed dock goal must stop in ERROR,
        # rather than recursively retrying forever.
        if self.manual_dock_requested and stage != 'dock':
            self._requeue_interrupted_order()
            self._return_to_dock()
            return
        if status != GoalStatus.STATUS_SUCCEEDED:
            self._navigation_failed(location, stage, int(status))
            return
        self.goal_attempts = 0
        reached = self.legs.pop(0) if self.legs else location
        reached_pose = reached if isinstance(reached, dict) else self.locations.get(reached)
        if reached_pose is not None:
            self.zone = self._zone_of(reached_pose)
            if self.zone == 'terrace':
                self.last_terrace_y = reached_pose['y']
        if self.legs:
            if isinstance(reached, dict) and reached['name'].endswith('_1'):
                self.door_checks = 0
                self._check_door(stage)
            else:
                self._send_next_leg(stage)
            return

        if stage == 'pickup':
            self.state = 'NAVIGATING_TO_CUSTOMER'
            self._publish_status(f'pickup reached; going to {self.current_location}')
            self._navigate(self.current_location, 'customer')
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
            self.at_dock = True
            if self.battery_return and (
                    self.battery_percentage is None
                    or self.battery_percentage < self.resume_percentage):
                self.state = 'CHARGING'
                self._publish_status('docked; charging until '
                                     f'{self.resume_percentage:.0f}%')
            else:
                self.battery_return = False
                self.state = 'IDLE'
                self._publish_status('IDLE at first-floor dock')

    def _check_door(self, stage):
        """Ask the planner for the path through the door before driving it."""
        leg = self.legs[0]
        if not self.path_planner.wait_for_server(timeout_sec=0.5):
            self._send_next_leg(stage)  # cannot check: just try the door
            return
        goal = ComputePathToPose.Goal()
        goal.goal.header.frame_id = self.frame_id
        goal.goal.pose.position.x = leg['x']
        goal.goal.pose.position.y = leg['y']
        goal.goal.pose.orientation.z = math.sin(leg['yaw'] / 2.0)
        goal.goal.pose.orientation.w = math.cos(leg['yaw'] / 2.0)
        goal.use_start = False
        self.goal_request_pending = True
        future = self.path_planner.send_goal_async(goal)
        future.add_done_callback(lambda f: self._door_check_accepted(f, stage))

    def _door_check_accepted(self, future, stage):
        try:
            handle = future.result()
        except Exception:
            handle = None
        if handle is None or not handle.accepted:
            self._door_checked(None, stage)
            return
        handle.get_result_async().add_done_callback(
            lambda f: self._door_checked(f, stage))

    def _door_checked(self, future, stage):
        self.goal_request_pending = False
        if self.manual_dock_requested and stage != 'dock':
            # A manual or low-battery return arrived during the check.
            self._requeue_interrupted_order()
            self._return_to_dock()
            return
        if self.current_stage != stage or not self.legs:
            return  # something else took over meanwhile
        length = None
        try:
            poses = future.result().result.path.poses if future is not None else []
            if poses:
                length = sum(math.hypot(b.pose.position.x - a.pose.position.x,
                                        b.pose.position.y - a.pose.position.y)
                             for a, b in zip(poses, poses[1:]))
        except Exception:
            length = None
        self._door_decision(length, stage)

    def _door_decision(self, length, stage):
        door = self.door_in_use
        if length is not None and length <= self.door_path_max:
            self._send_next_leg(stage)
            return
        self.door_checks += 1
        if self.door_checks < 2:
            self._publish_status(f'{door} looks blocked; waiting {self.door_recheck:.0f} s')
            self._cancel_retry()
            self.retry_timer = self.create_timer(
                self.door_recheck, lambda: self._recheck_door(stage))
            return
        final = self.legs[-1]
        self.door_tried.add(door)
        legs = self._plan_legs(final)
        if legs:
            self.legs = legs + [final]
            self.door_checks = 0
            self._publish_status(f'{door} blocked; rerouting through {self.door_in_use} to {final}')
            self._send_next_leg(stage)
            return
        if stage in ('pickup', 'customer') and self.current_location is not None:
            failed = self.current_location
            self.failed_orders.append(failed)
            self.current_location = None
            self._publish_status(f'all doors blocked; giving up on {failed}; returning to dock')
            self._return_to_dock()
            return
        # Cannot get back inside: wait outside and keep checking the doors.
        self.door_tried = set()
        self.door_checks = 0
        self._publish_status('all doors blocked; waiting to get back inside')
        self._cancel_retry()
        self.retry_timer = self.create_timer(
            2.0 * self.door_recheck, lambda: self._recheck_door(stage, replan=True))

    def _recheck_door(self, stage, replan=False):
        self._cancel_retry()
        if self.current_stage != stage or self.manual_dock_requested or not self.legs:
            return
        if replan:
            final = self.legs[-1]
            self.legs = (self._plan_legs(final) or []) + [final]
            self._send_next_leg(stage)  # back to the inside pose of a door
            return
        self._check_door(stage)

    def _navigation_failed(self, location, stage, status):
        if self.goal_attempts < self.goal_retries:
            self.goal_attempts += 1
            self._publish_status(
                f'Nav2 failed at {location} (status {status}); retry '
                f'{self.goal_attempts}/{self.goal_retries} in {self.retry_delay:.0f} s')
            self._cancel_retry()
            self.retry_timer = self.create_timer(
                self.retry_delay, lambda: self._retry(location, stage))
            return
        self.goal_attempts = 0
        final = self.legs[-1] if self.legs else location
        if len(self.legs) > 1 and self.door_in_use is not None:
            # A door leg kept failing: try the route through another door.
            self.door_tried.add(self.door_in_use)
            legs = self._plan_legs(final)
            if legs:
                self.legs = legs + [final]
                self._publish_status(
                    f'door blocked; rerouting through {self.door_in_use} to {final}')
                self._send_next_leg(stage)
                return
        if stage in ('pickup', 'customer') and self.current_location is not None:
            failed = self.current_location
            self.failed_orders.append(failed)
            self.current_location = None
            self.last_result = status
            self._publish_status(
                f'giving up on {failed} after {self.goal_retries} retries; '
                'returning to dock')
            self._return_to_dock()
            return
        self._fail(
            f'Nav2 failed at {location} with action status {status} '
            f'after {self.goal_retries} retries')

    def _cancel_retry(self):
        if self.retry_timer is not None:
            self.retry_timer.cancel()
            self.destroy_timer(self.retry_timer)
            self.retry_timer = None

    def _retry(self, location, stage):
        self._cancel_retry()
        # Something else (manual or low-battery return, depletion) may have
        # taken over while we waited; then this retry is stale.
        if (stage != self.current_stage or self.manual_dock_requested
                or self.current_goal_handle is not None or self.goal_request_pending
                or self.state in ('ERROR', 'BATTERY_DEPLETED', 'CHARGING', 'IDLE')):
            return
        self._publish_status(f'retrying {stage} ({location})')
        if self.legs:
            self._send_next_leg(stage)
        else:
            self._send_navigation_goal(location, stage)

    def _requeue_interrupted_order(self):
        # A manual return must not silently drop the customer being served.
        # Put the order back at the head of the queue so it is served first.
        interrupted = self.current_location
        self.current_location = None
        if interrupted is None or interrupted in self.queue:
            return
        self.queue.appendleft(interrupted)
        self._publish_status(f'interrupted {interrupted}; requeued at front')

    def _fail(self, message):
        self._cancel_retry()
        self.goal_attempts = 0
        self.current_goal_handle = None
        self.goal_request_pending = False
        self.manual_dock_requested = False
        self.battery_return = False
        self.state = 'ERROR'
        self.last_message = message
        self._publish_status(message)
        self.get_logger().error(message)

    def _reject(self, message):
        self._publish_status(f'rejected: {message}', log=False)
        self.get_logger().warn(self.last_message)

    def _status_payload(self):
        return {
            'state': self.state,
            'current_location': self.current_location,
            'current_stage': self.current_stage,
            'queue': list(self.queue),
            'last_result': self.last_result,
            'battery_percentage': (
                None if self.battery_percentage is None
                else round(self.battery_percentage, 1)),
            'battery_charging': self.battery_charging,
            'failed_orders': list(self.failed_orders),
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
