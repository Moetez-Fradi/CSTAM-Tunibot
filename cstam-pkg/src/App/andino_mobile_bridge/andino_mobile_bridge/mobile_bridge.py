import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import time
import uuid
class MobileBridge(Node):
    def __init__(self):
        super().__init__('mobile_bridge')
        self.addr = None
        self.phone = None
        self.create_pub = self.create_publisher(String, '/order/create', 10)
        self.create_pub_raw = self.create_publisher(String, '/order/raw', 10)
        self.addr_sub = self.create_subscription(String, '/app/address', self.on_address, 10)
        self.phone_sub = self.create_subscription(String, '/app/phone', self.on_phone, 10)
        self.get_logger().info('mobile_bridge ready')
    def on_address(self, msg: String):
        self.addr = msg.data
        self.get_logger().info(f"Got address: {self.addr}")
        self.try_create()
    def on_phone(self, msg: String):
        self.phone = msg.data
        self.get_logger().info(f"Got phone: {self.phone}")
        self.try_create()
    def try_create(self):
        if self.addr and self.phone:
            order = {
                "order_id": str(uuid.uuid4())[:8],
                "address": self.addr,
                "phone": self.phone,
                "timestamp": time.time()
            }
            payload = String()
            payload.data = json.dumps(order)
            self.create_pub.publish(payload)
            p2 = String()
            p2.data = f"ORDER_CREATED {order['order_id']} -> {self.addr} / {self.phone}"
            self.create_pub_raw.publish(p2)
            self.get_logger().info(f"Published order: {order['order_id']}")
            self.addr = None
            self.phone = None
def main(args=None):
    rclpy.init(args=args)
    node = MobileBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
