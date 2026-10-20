"""Run deliveries among pedestrians and report safety and task outcomes.

Usage (with the normal launch running):
    ros2 run cstam_phase1 dynamic_obstacle_trial --ros-args \
        -p deliveries:="['table_1', 'table_2']" -p timeout_sec:=1500.0

For each delivery it resets the pedestrian metrics, sends the request, waits
for the robot to return to IDLE (or ERROR / timeout) and records the
ground-truth clearance, contacts and collision-monitor interventions. The
summary is printed as JSON and optionally written to output_file.

With record_file set, it also writes a 2 Hz JSON-lines trace (robot ground
truth in the map frame, every pedestrian, delivery state, collision-monitor
action and commands before/after the monitor) for reconstructing encounters.
"""

import json
import math
import time

from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.msg import CollisionMonitorState
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from visualization_msgs.msg import MarkerArray


ACTIONS = {0: 'none', 1: 'stop', 2: 'slowdown', 3: 'approach', 4: 'limit'}


class DynamicObstacleTrial(Node):

    def __init__(self):
        super().__init__('cstam_dynamic_obstacle_trial')
        self.declare_parameter('deliveries', ['table_1'])
        self.declare_parameter('timeout_sec', 1200.0)
        self.declare_parameter('output_file', '')
        self.declare_parameter('record_file', '')
        # world <- map translation (maps/restaurant/world_alignment.yaml).
        self.declare_parameter('world_from_map', [11.22, 6.95])
        self.status = None
        self.metrics = None
        self.monitor_action = 'none'
        self.monitor_since = None
        self.monitor_time = {}
        self.monitor_events = {}

        status_qos = QoSProfile(depth=1)
        status_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        status_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.create_subscription(String, '/delivery/status', self._status, status_qos)
        self.create_subscription(String, '/pedestrians/metrics', self._metrics, 10)
        self.create_subscription(
            CollisionMonitorState, '/collision_monitor_state', self._monitor, 10)
        self.request_pub = self.create_publisher(String, '/delivery/request', 10)
        self.trace = None
        record = str(self.get_parameter('record_file').value)
        if record:
            self.trace = open(record, 'a', encoding='utf-8')
            self.world_from_map = list(self.get_parameter('world_from_map').value)
            self.sample = {'robot': None, 'people': {}, 'tracks': [],
                           'cmd_in': None, 'cmd': None}
            self.create_subscription(PoseStamped, '/model/cstam/pose', self._robot, 10)
            self.create_subscription(String, '/pedestrians/state', self._people, 10)
            self.create_subscription(Twist, '/cmd_vel_smoothed', self._cmd('cmd_in'), 10)
            self.create_subscription(Twist, '/cmd_vel', self._cmd('cmd'), 10)
            self.create_subscription(
                MarkerArray, '/dynamic_obstacles/markers', self._tracks, 10)
            self.create_timer(0.5, self._write_sample)
            self.trace_start = time.monotonic()
        self.reset_client = self.create_client(Trigger, '/pedestrians/reset_metrics')

    def _status(self, message):
        self.status = json.loads(message.data)

    def _metrics(self, message):
        self.metrics = json.loads(message.data)

    def _monitor(self, message):
        action = ACTIONS.get(message.action_type, str(message.action_type))
        now = time.monotonic()
        if action != self.monitor_action:
            if self.monitor_since is not None:
                self.monitor_time[self.monitor_action] = (
                    self.monitor_time.get(self.monitor_action, 0.0)
                    + now - self.monitor_since)
            self.monitor_events[action] = self.monitor_events.get(action, 0) + 1
            self.monitor_action = action
            self.monitor_since = now
        elif self.monitor_since is None:
            self.monitor_since = now

    def _robot(self, message):
        q = message.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self.sample['robot'] = [round(message.pose.position.x - self.world_from_map[0], 3),
                                round(message.pose.position.y - self.world_from_map[1], 3),
                                round(yaw, 3)]

    def _tracks(self, message):
        self.sample['tracks'] = [
            [round(m.pose.position.x, 2), round(m.pose.position.y, 2)]
            for m in message.markers if m.ns == 'person']

    def _people(self, message):
        self.sample['people'] = json.loads(message.data)

    def _cmd(self, key):
        def callback(message):
            self.sample[key] = [round(message.linear.x, 3), round(message.angular.z, 3)]
        return callback

    def _write_sample(self):
        status = self.status or {}
        self.trace.write(json.dumps({
            't': round(time.monotonic() - self.trace_start, 1),
            'state': status.get('state'), 'stage': status.get('current_stage'),
            'location': status.get('current_location'),
            'monitor': self.monitor_action, **self.sample}) + '\n')
        self.trace.flush()

    def _spin_for(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.1)

    def _wait_state(self, accept, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.2)
            if self.status and accept(self.status):
                return True
        return False

    def run_one(self, location, timeout):
        if self.reset_client.wait_for_service(timeout_sec=10.0):
            future = self.reset_client.call_async(Trigger.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        else:
            # Layout-only runs (pedestrians:=false) have no pedestrian metrics.
            self.get_logger().warn('No pedestrian simulator: recording without people metrics.')
            self.metrics = None
        self.monitor_time, self.monitor_events = {}, {}
        self.monitor_since = time.monotonic() if self.monitor_since else None
        if not self._wait_state(lambda s: s['state'] == 'IDLE', 600.0):
            return {'location': location, 'result': 'not idle before start'}
        start = time.monotonic()
        self.request_pub.publish(String(data=location))
        started = self._wait_state(lambda s: s['state'] != 'IDLE', 15.0)
        finished = started and self._wait_state(
            lambda s: s['state'] in ('IDLE', 'ERROR', 'BATTERY_DEPLETED'), timeout)
        self._spin_for(1.5)  # collect the final metrics message
        if self.monitor_since is not None:
            self.monitor_time[self.monitor_action] = (
                self.monitor_time.get(self.monitor_action, 0.0)
                + time.monotonic() - self.monitor_since)
            self.monitor_since = time.monotonic()
        state = self.status['state'] if self.status else None
        given_up = location in ((self.status or {}).get('failed_orders') or [])
        if not finished:
            result = 'timeout'
        elif given_up:
            result = 'given_up'  # delivery abandoned, robot back at the dock
        elif state == 'IDLE':
            result = 'success'
        else:
            result = state
        return {
            'location': location,
            'result': result,
            'wall_time_sec': round(time.monotonic() - start, 1),
            'last_message': self.status.get('message') if self.status else None,
            'pedestrians': self.metrics,
            'collision_monitor_seconds': {
                k: round(v, 1) for k, v in self.monitor_time.items()},
            'collision_monitor_activations': {
                k: v for k, v in self.monitor_events.items() if k != 'none'},
        }

    def run(self):
        timeout = float(self.get_parameter('timeout_sec').value)
        results = [self.run_one(str(location), timeout)
                   for location in self.get_parameter('deliveries').value]
        summary = {
            'trials': results,
            'successes': sum(r['result'] == 'success' for r in results),
            'total': len(results),
            'robot_fault_contacts': sum(
                (r.get('pedestrians') or {}).get('robot_fault_contacts', 0) for r in results),
        }
        text = json.dumps(summary, indent=2)
        print(text)
        output = str(self.get_parameter('output_file').value)
        if output:
            with open(output, 'w', encoding='utf-8') as stream:
                stream.write(text + '\n')
        return summary


def main(args=None):
    rclpy.init(args=args)
    node = DynamicObstacleTrial()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
