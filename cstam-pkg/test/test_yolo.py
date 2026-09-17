#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

class TestYoloTrigger(Node):
    def __init__(self):
        super().__init__('test_yolo_trigger')
        self.publisher_ = self.create_publisher(Bool, '/robot/qr/verified', 10)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.count = 0

    def timer_callback(self):
        msg = Bool()
        msg.data = True
        self.publisher_.publish(msg)
        self.get_logger().info('Trigging YOLO detection (/robot/qr/verified = True)')
        self.count += 1
        if self.count >= 3:
            self.get_logger().info('Done triggering.')
            raise SystemExit

def main(args=None):
    rclpy.init(args=args)
    node = TestYoloTrigger()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
