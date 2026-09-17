import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from std_msgs.msg import String
import time

def main():
    rclpy.init()
    node = Node('test_map_publisher')
    
    latched_qos = QoSProfile(depth=1)
    latched_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
    latched_qos.reliability = QoSReliabilityPolicy.RELIABLE
    
    pub = node.create_publisher(String, '/app/map_path', latched_qos)
    
    msg = String()
    msg.data = "/home/mo/ws/src/App/map_info/maps/map.yaml"
    
    # Transient local needs to be published, and then we wait a bit for subscribers to catch up (though latched handles late joiners, we want to ensure the message is "there")
    print("Publishing map path...")
    pub.publish(msg)
    
    # Spin a bit to ensure the message is sent
    start = time.time()
    while time.time() - start < 3:
        rclpy.spin_once(node, timeout_sec=0.1)
        
    print("Done publishing.")
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
