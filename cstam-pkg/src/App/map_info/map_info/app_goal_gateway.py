import os
import yaml
import difflib
from math import sin, cos
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
try:
    from audio_common_msgs.action import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
from std_msgs.msg import String, Empty
from geometry_msgs.msg import PoseStamped, Quaternion
from visualization_msgs.msg import MarkerArray
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
import json
import time
import uuid
current_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_YAML = os.path.abspath(os.path.join(current_dir, '../named_poses.yaml'))
def yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = sin(yaw / 2.0)
    q.w = cos(yaw / 2.0)
    return q
def load_named_poses(path: str):
    """Return dict: name -> {position:{x,y,z}, orientation:{x,y,z,w}}."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        data = yaml.safe_load(f) or {}
    base = data.get('waypoints', data) if isinstance(data, dict) else {}
    poses = {}
    for name, pose in (base.items() if isinstance(base, dict) else []):
        if not isinstance(pose, dict):
            continue
        p = (pose.get('position') or {}) if isinstance(pose.get('position'), dict) else {}
        o = pose.get('orientation')
        if not isinstance(o, dict):
            if 'yaw' in pose:
                q = yaw_to_quat(float(pose['yaw']))
            else:
                q = yaw_to_quat(0.0)
            o = {'x': q.x, 'y': q.y, 'z': q.z, 'w': q.w}
        poses[str(name)] = {
            'position': {
                'x': float(p.get('x', 0.0)),
                'y': float(p.get('y', 0.0)),
                'z': float(p.get('z', 0.0)),
            },
            'orientation': {
                'x': float(o.get('x', 0.0)),
                'y': float(o.get('y', 0.0)),
                'z': float(o.get('z', 0.0)),
                'w': float(o.get('w', 1.0)),
            },
        }
    return poses
class AppGoalGateway(Node):
    def __init__(self):
        super().__init__('app_goal_gateway')
        self.declare_parameter('yaml_path', DEFAULT_YAML)
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('topic_goal_name', '/app/goal_name')
        self.declare_parameter('topic_direct_nav', '/app/direct_nav')  # Navigation without order
        self.declare_parameter('topic_goal_cancel', '/app/goal_cancel')
        self.declare_parameter('topic_status', '/app/goal_status')
        self.declare_parameter('server_timeout', 8.0)
        self.declare_parameter('fuzzy_cutoff', 0.7)
        self.yaml_path = self.get_parameter('yaml_path').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value
        self.topic_goal_name = self.get_parameter('topic_goal_name').get_parameter_value().string_value
        self.topic_direct_nav = self.get_parameter('topic_direct_nav').get_parameter_value().string_value
        self.topic_goal_cancel = self.get_parameter('topic_goal_cancel').get_parameter_value().string_value
        self.topic_status = self.get_parameter('topic_status').get_parameter_value().string_value
        self.server_timeout = self.get_parameter('server_timeout').get_parameter_value().double_value
        self.fuzzy_cutoff = float(self.get_parameter('fuzzy_cutoff').get_parameter_value().double_value)
        
        latched_qos = QoSProfile(depth=1)
        latched_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        latched_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self.sub_map_path = self.create_subscription(String, '/app/map_path', self.on_map_path, latched_qos)
        self.sub_goal_name = self.create_subscription(String, self.topic_goal_name, self.on_name, 10)
        self.sub_direct_nav = self.create_subscription(String, self.topic_direct_nav, self.on_direct_nav, 10)  # Chatbot navigation
        self.order_pub = self.create_publisher(String, '/order/json', 10)
        self.pub_status = self.create_publisher(String, self.topic_status, 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        if TTS_AVAILABLE:
            self.tts_client = ActionClient(self, TTS, '/say')
            self.get_logger().info("Connected to TTS Action Server")
        else:
            self.tts_client = None
            self.get_logger().warn("Audio Common Msgs not found - TTS disabled")
        self.named_poses = load_named_poses(self.yaml_path)
        self.current_handle = None
        self.get_logger().info(
            f'Attempting to load waypoints from: {self.yaml_path}'
        )
        self.named_poses = load_named_poses(self.yaml_path)
        keys = list(self.named_poses.keys())
        self.get_logger().info(f'Loaded {len(keys)} waypoints: {keys}')
        if not keys:
             self.get_logger().error(f"WARNING: No waypoints loaded! Check path: {self.yaml_path}")
        self._status('ready')
    def on_name(self, msg: String):
        name = msg.data.strip()
        if not name:
            return
        self.get_logger().info(f"Reloading map from: {self.yaml_path}")
        self.named_poses = load_named_poses(self.yaml_path)
        self.get_logger().info(f"Keys available after reload: {list(self.named_poses.keys())}")
        resolved = self._resolve_name(name)
        if not resolved:
            self.get_logger().warn(f'Name "{name}" not found.')
            self._status(f'not_found:{name}')
            return
        if resolved != name:
            self.get_logger().info(f'Using closest match: {resolved} (from "{name}")')
            self._status(f'resolved:{name}->{resolved}')
        lower_res = resolved.lower()
        if 'office' in lower_res or 'garage' in lower_res or 'home' in lower_res or 'r403' in lower_res:
            self.speak("I have finished. I am going to the garage.")
        else:
            self.speak("I received an order. I will deliver it and send a QR code to the customer.")
        self._go_to(resolved)
        self.publish_new_order(resolved)

    def on_direct_nav(self, msg: String):
        """Handle direct navigation from chatbot - NO order creation, NO QR."""
        name = msg.data.strip()
        if not name:
            return
        self.get_logger().info(f"🚀 Direct Navigation (No Order): {name}")
        self.named_poses = load_named_poses(self.yaml_path)
        resolved = self._resolve_name(name)
        if not resolved:
            self.get_logger().warn(f'Direct Nav: Name "{name}" not found.')
            self._status(f'not_found:{name}')
            return
        if resolved != name:
            self.get_logger().info(f'Using closest match: {resolved}')
        # Navigate WITHOUT order creation
        self.speak(f"Going to {resolved}.")
        self._go_to(resolved)
    def publish_new_order(self, location: str):
        """Publish order event for Dashboard."""
        try:
            order_id = str(uuid.uuid4())[:8].upper()
            payload = {
                "order_id": order_id,
                "target_location": location,
                "timestamp": time.time(),
                "status": "In Progress"
            }
            msg = String()
            msg.data = json.dumps(payload)
            self.order_pub.publish(msg)
            self.get_logger().info(f"📦 Central Order Logged: {order_id} -> {location}")
        except Exception as e:
            self.get_logger().error(f"Failed to log order: {e}")
    def on_cancel(self, _):
        if self.current_handle:
            self._status('cancel_requested')
            self.current_handle.cancel_goal_async()
        else:
            self._status('no_active_goal')
    def on_map_path(self, msg: String):
        """Reload map when goal_name_node publishes a new selected path."""
        new_path = msg.data.strip()
        if not new_path or new_path == self.yaml_path:
            return
        self.get_logger().info(f"🔄 Syncing Map: Switching to {new_path}")
        self.yaml_path = new_path
        self.named_poses = load_named_poses(self.yaml_path)
        keys = list(self.named_poses.keys())
        self.get_logger().info(f'Loaded {len(keys)} waypoints from new map: {keys}')
        self._status(f'map_loaded:{os.path.basename(new_path)}')
    def _resolve_name(self, name: str):
        if name in self.named_poses:
            return name
        names = list(self.named_poses.keys())
        lower_map = {n.lower(): n for n in names}
        if name.lower() in lower_map:
            return lower_map[name.lower()]
        cand = difflib.get_close_matches(name.lower(), [n.lower() for n in names], n=1, cutoff=self.fuzzy_cutoff)
        return lower_map[cand[0]] if cand else None
    def _go_to(self, name: str):
        if not self.client.wait_for_server(timeout_sec=self.server_timeout):
            self._status('error:navigate_to_pose_unavailable')
            self.get_logger().error('navigate_to_pose action server not available')
            return
        p = self.named_poses[name]['position']
        o = self.named_poses[name]['orientation']
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.frame_id
        goal.pose.header.stamp.sec = 0
        goal.pose.header.stamp.nanosec = 0
        goal.pose.pose.position.x = p['x']
        goal.pose.pose.position.y = p['y']
        goal.pose.pose.position.z = p.get('z', 0.0)
        goal.pose.pose.orientation = Quaternion(x=o['x'], y=o['y'], z=o['z'], w=o['w'])
        self._status(f'sending:{name}')
        send_future = self.client.send_goal_async(goal, feedback_callback=self._on_feedback)
        send_future.add_done_callback(self._on_sent)
    def _on_sent(self, fut):
        self.current_handle = fut.result()
        if not self.current_handle or not self.current_handle.accepted:
            self._status('rejected')
            self.get_logger().warn('Goal rejected')
            return
        res_fut = self.current_handle.get_result_async()
        res_fut.add_done_callback(self._on_result)
    def _on_feedback(self, fb_msg):
        fb = fb_msg.feedback
        dist = getattr(fb, 'distance_remaining', None)
        if dist is not None:
            self._status(f'feedback:{dist:.2f}')
        else:
            self._status('feedback')
    def _on_result(self, fut):
        self.current_handle = None
        try:
            result = fut.result()
            status = getattr(result, 'status', None)
        except Exception:
            status = None
        if status == GoalStatus.STATUS_SUCCEEDED:
            self._status('succeeded')
        elif status == GoalStatus.STATUS_ABORTED:
            self._status('finished:aborted')
        elif status == GoalStatus.STATUS_CANCELED:
            self._status('finished:canceled')
        else:
            self._status(f'finished:{status}')
    def speak(self, text):
        if self.tts_client and self.tts_client.wait_for_server(timeout_sec=0.5):
            goal = TTS.Goal()
            goal.text = text
            self.tts_client.send_goal_async(goal)
    def _status(self, text: str):
        self.pub_status.publish(String(data=text))
        self.get_logger().info(text)
def main():
    rclpy.init()
    node = AppGoalGateway()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()
