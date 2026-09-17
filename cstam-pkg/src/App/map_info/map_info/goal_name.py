import os
import yaml
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
from geometry_msgs.msg import PointStamped, Point, Quaternion
from visualization_msgs.msg import Marker, MarkerArray
from std_srvs.srv import Trigger
from std_msgs.msg import String
from math import sin, cos
from ament_index_python.packages import get_package_share_directory

try:
    share_dir = get_package_share_directory('map_info')
    DEFAULT_YAML_PATH = os.path.join(share_dir, 'maps', 'hti.yaml')
except Exception as e:
    # Fallback to local relative path for development if package not installed
    current_dir = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_YAML_PATH = os.path.abspath(os.path.join(current_dir, '../maps/hti.yaml'))
def yaw_to_quat(yaw: float):
    return {'x': 0.0, 'y': 0.0, 'z': sin(yaw / 2.0), 'w': cos(yaw / 2.0)}
def load_named_poses(yaml_path: str):
    """Load poses from YAML and normalize to: {name: {position, orientation}}."""
    if not os.path.exists(yaml_path):
        return {}, 'flat'
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, dict) and 'waypoints' in data:
        poses = {}
        for name, pose in (data.get('waypoints') or {}).items():
            p = pose.get('position', {})
            o = pose.get('orientation', {})
            poses[name] = {
                'position': {'x': float(p.get('x', 0.0)), 'y': float(p.get('y', 0.0)), 'z': float(p.get('z', 0.0))},
                'orientation': {
                    'x': float(o.get('x', 0.0)),
                    'y': float(o.get('y', 0.0)),
                    'z': float(o.get('z', 0.0)),
                    'w': float(o.get('w', 1.0)),
                },
            }
        return poses, 'waypoints'
    elif isinstance(data, dict):
        poses = {}
        for name, pose in data.items():
            if not isinstance(pose, dict):
                continue
            p = pose.get('position', {})
            pos = {'x': float(p.get('x', 0.0)), 'y': float(p.get('y', 0.0)), 'z': float(p.get('z', 0.0))}
            if 'orientation' in pose:
                o = pose['orientation']
                ori = {
                    'x': float(o.get('x', 0.0)),
                    'y': float(o.get('y', 0.0)),
                    'z': float(o.get('z', 0.0)),
                    'w': float(o.get('w', 1.0)),
                }
            elif 'yaw' in pose:
                ori = yaw_to_quat(float(pose['yaw']))
            else:
                ori = yaw_to_quat(0.0)
            poses[name] = {'position': pos, 'orientation': ori}
        return poses, 'flat'
    else:
        return {}, 'flat'
def save_named_pose(yaml_path: str, name: str, position: dict, orientation: dict, schema: str):
    """Save a pose back to YAML while preserving the original schema."""
    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    data = {}
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f) or {}
    if schema == 'waypoints':
        data.setdefault('waypoints', {})
        data['waypoints'][name] = {'position': position, 'orientation': orientation}
    else:
        data[name] = {'position': position, 'orientation': orientation}
    with open(yaml_path, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=True)
class GoalNameNode(Node):
    def __init__(self):
        super().__init__('goal_name')
        self.declare_parameter('yaml_path', DEFAULT_YAML_PATH)
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('enable_click_input', False)  
        self.declare_parameter('watch_yaml', True)
        self.declare_parameter('watch_interval', 1.0)
        self.yaml_path = self.get_parameter('yaml_path').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value
        self.enable_click_input = self.get_parameter('enable_click_input').get_parameter_value().bool_value
        self.watch_yaml = self.get_parameter('watch_yaml').get_parameter_value().bool_value
        self.watch_interval = self.get_parameter('watch_interval').get_parameter_value().double_value
        print(f"DEBUG: enable_click_input is {self.enable_click_input}")
        if self.enable_click_input:
            print(f"DEBUG: Entering select_map_interactive with path {self.yaml_path}")
            self.yaml_path = self.select_map_interactive(self.yaml_path)
        latched_qos = QoSProfile(depth=1)
        latched_qos.reliability = QoSReliabilityPolicy.RELIABLE
        latched_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        self.marker_pub = self.create_publisher(MarkerArray, '/named_poses/markers', latched_qos)
        self.marker_pub = self.create_publisher(MarkerArray, '/named_poses/markers', latched_qos)
        self.single_text_pub = self.create_publisher(Marker, '/place_labels', latched_qos)  
        self.path_pub = self.create_publisher(String, '/app/map_path', latched_qos) 
        if self.enable_click_input:
            self.click_sub = self.create_subscription(PointStamped, '/clicked_point', self.on_click, 10)
            self.get_logger().info('Add mode: click in RViz (Publish Point) then enter a label in the terminal.')
        else:
            self.click_sub = None
            self.get_logger().info('Publish-only mode: publishing markers from YAML.')
        self.named_poses, self.schema = load_named_poses(self.yaml_path)
        self.id_map = {}
        self.next_id = 1
        self.publish_all()
        self.last_mtime = os.path.getmtime(self.yaml_path) if os.path.exists(self.yaml_path) else 0.0
        if self.watch_yaml:
            self.timer = self.create_timer(self.watch_interval, self.check_yaml_change)
        self.reload_srv = self.create_service(Trigger, 'reload', self.on_reload)
        self.publish_timer = self.create_timer(2.0, self.publish_all)
        self.get_logger().info(f'YAML: {self.yaml_path} (schema: {self.schema}) | frame: {self.frame_id}')
        self.path_pub.publish(String(data=self.yaml_path))
    def select_map_interactive(self, current_path: str) -> str:
        """Present a menu to select an existing YAML map file or create a new one."""
        # Resolve symlink to ensure we work with the source file if possible
        if os.path.exists(current_path):
             real_path = os.path.realpath(current_path)
             if real_path != current_path:
                 print(f"DEBUG: Resolved symlink to source: {real_path}")
                 current_path = real_path
        
        # Custom logic: check for standard 'ws' path shared by team
        home = os.path.expanduser('~')
        standard_src_path = os.path.join(home, 'ws', 'src', 'App', 'map_info', 'maps')
        if os.path.exists(standard_src_path):
             print(f"DEBUG: Standard source path found, switching to: {standard_src_path}")
             current_path = os.path.join(standard_src_path, os.path.basename(current_path))

        directory = os.path.dirname(current_path)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError:
                print(f"Warning: Could not create directory {directory}. Using default path.")
                return current_path
        print("\n--- Map Selection Menu ---")
        yaml_files = [f for f in os.listdir(directory) if f.endswith('.yaml')]
        yaml_files.sort()
        print("Available Maps:")
        for idx, f in enumerate(yaml_files):
            print(f"  {idx + 1}. {f}")
        print(f"  {len(yaml_files) + 1}. [Create New Map]")
        while True:
            try:
                choice = input(f"\nSelect an option (1-{len(yaml_files) + 1}): ").strip()
                if not choice.isdigit():
                    continue
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(yaml_files):
                    selected_file = yaml_files[choice_idx]
                    print(f"Selected: {selected_file}")
                    return os.path.join(directory, selected_file)
                elif choice_idx == len(yaml_files):
                    new_name = input("Enter new map name (without .yaml): ").strip()
                    if not new_name:
                        print("Invalid name.")
                        continue
                    if not new_name.endswith('.yaml'):
                        new_name += '.yaml'
                    full_path = os.path.join(directory, new_name)
                    if not os.path.exists(full_path):
                        with open(full_path, 'w') as f:
                            f.write("{}")  
                        print(f"Created new map file: {new_name}")
                    else:
                        print(f"File {new_name} already exists. Using it.")
                    return full_path
                else:
                    print("Invalid selection.")
            except (KeyboardInterrupt, EOFError):
                print("\nSelection cancelled. Using default.")
                return current_path
            except Exception as e:
                print(f"Error during selection: {e}")
                return current_path
    def on_click(self, msg: PointStamped):
        name = input('Enter label name: ').strip().replace(' ', '_')
        if not name:
            print('Invalid name. Ignored.')
            return
        base = name
        i = 2
        while name in self.named_poses:
            name = f'{base}_{i}'
            i += 1
        pos = {'x': float(msg.point.x), 'y': float(msg.point.y), 'z': 0.0}
        ori = yaw_to_quat(0.0)
        self.named_poses[name] = {'position': pos, 'orientation': ori}
        save_named_pose(self.yaml_path, name, pos, ori, self.schema)
        self.touch_mtime()
        self.publish_one(name, pos, ori)
        self.get_logger().info(f'Added "{name}" at ({pos["x"]:.2f}, {pos["y"]:.2f}) and saved to YAML.')
    def on_reload(self, request, response):
        try:
            self.named_poses, self.schema = load_named_poses(self.yaml_path)
            self.publish_all()
            response.success = True
            response.message = 'Reloaded and republished markers.'
        except Exception as e:
            response.success = False
            response.message = f'Failed to reload: {e}'
        return response
    def touch_mtime(self):
        self.last_mtime = os.path.getmtime(self.yaml_path) if os.path.exists(self.yaml_path) else time.time()
    def check_yaml_change(self):
        try:
            mtime = os.path.getmtime(self.yaml_path)
        except FileNotFoundError:
            mtime = 0.0
        if mtime != self.last_mtime:
            self.last_mtime = mtime
            self.named_poses, self.schema = load_named_poses(self.yaml_path)
            self.publish_all()
            self.get_logger().info('YAML changed on disk; republished markers.')
    def reserve_ids(self, name: str):
        if name not in self.id_map:
            self.id_map[name] = (self.next_id, self.next_id + 1)  
            self.next_id += 2
        return self.id_map[name]
    def publish_all(self):
        """Publish DELETEALL + ALL markers (arrow+text) in a single latched message."""
        ma = MarkerArray()
        clear = Marker()
        clear.header.frame_id = self.frame_id
        clear.action = Marker.DELETEALL
        ma.markers.append(clear)
        now = self.get_clock().now().to_msg()
        for name, item in self.named_poses.items():
            pos = item['position']
            ori = item.get('orientation', yaw_to_quat(0.0))
            arrow_id, text_id = self.reserve_ids(name)
            arrow = Marker()
            arrow.header.frame_id = self.frame_id
            arrow.header.stamp = now
            arrow.ns = 'named_poses'
            arrow.id = arrow_id
            arrow.type = Marker.ARROW
            arrow.action = Marker.ADD
            arrow.pose.position.x = pos['x']
            arrow.pose.position.y = pos['y']
            arrow.pose.position.z = 0.0
            arrow.pose.orientation = Quaternion(x=ori['x'], y=ori['y'], z=ori['z'], w=ori['w'])
            arrow.scale.x = 0.5
            arrow.scale.y = 0.1
            arrow.scale.z = 0.1
            arrow.color.r = 0.0
            arrow.color.g = 1.0
            arrow.color.b = 0.0
            arrow.color.a = 1.0
            text = Marker()
            text.header.frame_id = self.frame_id
            text.header.stamp = now
            text.ns = 'named_poses_text'
            text.id = text_id
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = pos['x']
            text.pose.position.y = pos['y']
            text.pose.position.z = 0.4
            text.scale.z = 0.35
            text.color.r = 0.1
            text.color.g = 0.1
            text.color.b = 1.0
            text.color.a = 1.0
            text.text = name
            ma.markers.extend([arrow, text])
        self.marker_pub.publish(ma)
        self.get_logger().info(f'Published {len(ma.markers)-1} markers ({len(self.named_poses)} waypoints) in one message.')
    def publish_one(self, name: str, pos: dict, ori: dict, log: bool = True):
        """Publish a single waypoint (arrow+text) as a small MarkerArray."""
        arrow_id, text_id = self.reserve_ids(name)
        now = self.get_clock().now().to_msg()
        arrow = Marker()
        arrow.header.frame_id = self.frame_id
        arrow.header.stamp = now
        arrow.ns = 'named_poses'
        arrow.id = arrow_id
        arrow.type = Marker.ARROW
        arrow.action = Marker.ADD
        arrow.pose.position.x = pos['x']
        arrow.pose.position.y = pos['y']
        arrow.pose.position.z = 0.0
        arrow.pose.orientation = Quaternion(x=ori['x'], y=ori['y'], z=ori['z'], w=ori['w'])
        arrow.scale.x = 0.5
        arrow.scale.y = 0.1
        arrow.scale.z = 0.1
        arrow.color.r = 0.0
        arrow.color.g = 1.0
        arrow.color.b = 0.0
        arrow.color.a = 1.0
        text = Marker()
        text.header.frame_id = self.frame_id
        text.header.stamp = now
        text.ns = 'named_poses_text'
        text.id = text_id
        text.type = Marker.TEXT_VIEW_FACING
        text.action = Marker.ADD
        text.pose.position.x = pos['x']
        text.pose.position.y = pos['y']
        text.pose.position.z = 0.4
        text.scale.z = 0.35
        text.color.r = 0.1
        text.color.g = 0.1
        text.color.b = 1.0
        text.color.a = 1.0
        text.text = name
        arr = MarkerArray()
        arr.markers.extend([arrow, text])
        self.marker_pub.publish(arr)
        self.single_text_pub.publish(text)
        if log:
            self.get_logger().info(f'Published "{name}".')
def main():
    rclpy.init()
    node = GoalNameNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()
