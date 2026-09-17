import os
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose
from math import sin, cos
current_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_YAML_PATH = os.path.abspath(os.path.join(current_dir, '../named_poses.yaml'))
def yaw_to_quat(yaw: float) -> Quaternion:
    """Convert yaw (in radians) to a Quaternion (2D rotation around Z)."""
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = sin(yaw / 2.0)
    q.w = cos(yaw / 2.0)
    return q
def load_named_poses(yaml_path: str):
    """
    Load named poses from YAML.
    Returns:
        dict[name] = {
            'position': {x, y, z},
            'orientation': {x, y, z, w}
        }
    """
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f) or {}
    items = data.get('waypoints', data) if isinstance(data, dict) else {}
    poses = {}
    for name, pose in items.items():
        if not isinstance(pose, dict):
            continue
        p = pose.get('position', {}) or {}
        o = pose.get('orientation', None)
        pos = {
            'x': float(p.get('x', 0.0)),
            'y': float(p.get('y', 0.0)),
            'z': float(p.get('z', 0.0)),
        }
        if o is None and 'yaw' in pose:
            q = yaw_to_quat(float(pose['yaw']))
            ori = {'x': q.x, 'y': q.y, 'z': q.z, 'w': q.w}
        elif o is None:
            q = yaw_to_quat(0.0)
            ori = {'x': q.x, 'y': q.y, 'z': q.z, 'w': q.w}
        else:
            ori = {
                'x': float(o.get('x', 0.0)),
                'y': float(o.get('y', 0.0)),
                'z': float(o.get('z', 0.0)),
                'w': float(o.get('w', 1.0)),
            }
        poses[str(name)] = {'position': pos, 'orientation': ori}
    return poses
def remove_named_pose(yaml_path: str, name_to_remove: str) -> bool:
    if not os.path.exists(yaml_path):
        return False
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f) or {}
    if 'waypoints' in data and isinstance(data['waypoints'], dict):
        container = data['waypoints']
    else:
        container = data
    if name_to_remove in container:
        del container[name_to_remove]
        with open(yaml_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        return True
    return False
class GoMenu(Node):
    """
    Simple terminal-based menu to send Nav2 goals
    based on named poses loaded from a YAML file.
    """
    def __init__(self):
        super().__init__('go_menu')
        self.declare_parameter('yaml_path', DEFAULT_YAML_PATH)
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('timeout_sec', 0.0)  
        self.yaml_path = self.get_parameter('yaml_path').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value
        self.timeout = self.get_parameter('timeout_sec').get_parameter_value().double_value
        
        # Select map interactively before starting menu
        self.yaml_path = self.select_map_interactive(self.yaml_path)
        
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.get_logger().info(f'Interactive menu started. YAML="{self.yaml_path}"')
        self.menu_loop()
    
    def select_map_interactive(self, current_path: str) -> str:
        """Present a menu to select an existing YAML map file or create a new one."""
        # Custom logic: check for standard 'ws' path shared by team
        home = os.path.expanduser('~')
        standard_src_path = os.path.join(home, 'ws', 'src', 'App', 'map_info', 'maps')
        if os.path.exists(standard_src_path):
            current_path = os.path.join(standard_src_path, os.path.basename(current_path))

        directory = os.path.dirname(current_path)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError:
                print(f"Warning: Could not create directory {directory}. Using default path.")
                return current_path
        
        print("\n=== Map Selection Menu ===")
        yaml_files = [f for f in os.listdir(directory) if f.endswith('.yaml')]
        yaml_files.sort()
        
        print("Available Maps:")
        for idx, f in enumerate(yaml_files):
            print(f"  {idx + 1}. {f}")
        print(f"  {len(yaml_files) + 1}. [Create New Map]")
        
        while True:
            try:
                choice = input(f"\nSelect map (1-{len(yaml_files) + 1}): ").strip()
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
    def menu_loop(self):
        """Main interactive loop: list waypoints and ask the user to pick one."""
        try:
            while rclpy.ok():
                poses = load_named_poses(self.yaml_path)
                if not poses:
                    print(f'\nNo waypoints found in {self.yaml_path}')
                    print('Add some labels first, then press [r] to reload, or [q] to quit.')
                    choice = input('Enter choice: ').strip().lower()
                    if choice == 'q':
                        break
                    else:
                        continue
                names = sorted(poses.keys())
                print('\n=== Select Destination ===')
                for i, n in enumerate(names, start=1):
                    p = poses[n]['position']
                    print(f'{i}) {n}  (x={p["x"]:.2f}, y={p["y"]:.2f})')
                print('d) Delete a destination')
                print('r) Reload from YAML')
                print('q) Quit')
                raw_input = input('Enter choice: ').strip().lower()
                if not raw_input:
                    continue
                if raw_input == 'q':
                    break
                if raw_input == 'r':
                    continue
                if raw_input == 'd':
                    rest = raw_input[1:].strip()
                    target_idx = -1
                    if rest.isdigit():
                        target_idx = int(rest)
                    else:
                        sub = input('Enter number to delete: ').strip()
                        if sub.isdigit():
                            target_idx = int(sub)
                    if 1 <= target_idx <= len(names):
                        to_delete = names[target_idx - 1]
                        confirm = input(f'Delete "{to_delete}"? [y/N] ').lower()
                        if confirm == 'y':
                            success = remove_named_pose(self.yaml_path, to_delete)
                            if success:
                                print(f'Successfully deleted "{to_delete}".')
                            else:
                                print(f'Failed to delete "{to_delete}".')
                        else:
                            print('Cancelled.')
                    else:
                        print('Invalid number for deletion.')
                    continue
                if not raw_input.isdigit():
                    print('Invalid input.')
                    continue
                idx = int(raw_input)
                if idx < 1 or idx > len(names):
                    print('Out of range.')
                    continue
                name = names[idx - 1]
                self.navigate_to(poses[name], name)
        except (KeyboardInterrupt, EOFError):
            pass
    def navigate_to(self, item: dict, name: str):
        """Send NavigateToPose goal for a given waypoint."""
        if not self.client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('navigate_to_pose action server not available.')
            return
        p = item['position']
        o = item['orientation']
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.frame_id
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = p['x']
        goal.pose.pose.position.y = p['y']
        goal.pose.pose.position.z = p.get('z', 0.0)
        goal.pose.pose.orientation = Quaternion(
            x=o['x'], y=o['y'], z=o['z'], w=o['w']
        )
        self.get_logger().info(f'Navigating to "{name}" ...')
        send_future = self.client.send_goal_async(
            goal, feedback_callback=self.on_feedback
        )
        rclpy.spin_until_future_complete(self, send_future)
        handle = send_future.result()
        if not handle or not handle.accepted:
            self.get_logger().error('Goal rejected.')
            return
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()
        if result and result.status == 4:
            self.get_logger().info(f'Goal "{name}" reached.')
        else:
            status = None if not result else result.status
            self.get_logger().warn(f'Goal "{name}" finished with status={status}.')
    def on_feedback(self, fb_msg):
        """Print distance remaining if available."""
        fb = fb_msg.feedback
        try:
            print(f'  remaining: {fb.distance_remaining:.2f} m')
        except Exception:
            pass
def main():
    """Entry point for the console_script `go_menu`."""
    rclpy.init()
    node = GoMenu()
    node.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()
