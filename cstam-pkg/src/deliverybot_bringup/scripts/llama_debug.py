#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from llama_msgs.action import GenerateResponse
import time
class LlamaDebug(Node):
    def __init__(self):
        super().__init__('llama_debug')
        self.client = ActionClient(self, GenerateResponse, '/llama/generate_response')
        self.get_logger().info('Waiting for server...')
        self.client.wait_for_server()
        self.send_goal()
    def send_goal(self):
        goal = GenerateResponse.Goal()
        goal.prompt = "Say Test"
        goal.reset = True
        self.get_logger().info('Sending goal...')
        future = self.client.send_goal_async(goal, feedback_callback=self.feedback_cb)
        future.add_done_callback(self.goal_response_cb)
    def feedback_cb(self, feedback_msg):
        partial = feedback_msg.feedback.partial_response
        self.get_logger().info(f'FEEDBACK RAW: {partial}')
        if hasattr(partial, 'text'):
            self.get_logger().info(f'FEEDBACK TEXT: "{partial.text}"')
    def goal_response_cb(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Goal rejected')
            return
        self.get_logger().info('Goal accepted')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_cb)
    def get_result_cb(self, future):
        result = future.result().result
        self.get_logger().info(f'RESULT TYPE: {type(result)}')
        self.get_logger().info(f'RESULT DIR: {dir(result)}')
        if hasattr(result, 'response'):
            resp = result.response
            self.get_logger().info(f'RESPONSE DIR: {dir(resp)}')
            if hasattr(resp, 'text'):
                self.get_logger().info(f'RESPONSE TEXT: "{resp.text}"')
            else:
                self.get_logger().info('Response has no text attr')
        else:
            self.get_logger().info('Result has no response attr')
        rclpy.shutdown()
def main():
    rclpy.init()
    node = LlamaDebug()
    rclpy.spin(node)
if __name__ == '__main__':
    main()
