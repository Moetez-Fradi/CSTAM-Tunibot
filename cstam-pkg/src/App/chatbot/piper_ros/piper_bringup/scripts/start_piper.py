#!/usr/bin/env python3

import sys
import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition

class PiperStarter(Node):
    def __init__(self):
        super().__init__('piper_starter')
        self.state_client = self.create_client(GetState, '/piper_node/get_state')
        self.change_state_client = self.create_client(ChangeState, '/piper_node/change_state')

    def wait_for_service(self):
        self.get_logger().info('Waiting for piper_node services...')
        if not self.state_client.wait_for_service(timeout_sec=20.0):
            self.get_logger().error('piper_node get_state service not available.')
            return False
        if not self.change_state_client.wait_for_service(timeout_sec=20.0):
            self.get_logger().error('piper_node change_state service not available.')
            return False
        return True

    def get_current_state(self):
        req = GetState.Request()
        future = self.state_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is not None:
            return future.result().current_state.id
        else:
            self.get_logger().error('Failed to get current state')
            return -1

    def change_state(self, transition_id):
        req = ChangeState.Request()
        req.transition.id = transition_id
        future = self.change_state_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def start(self):
        if not self.wait_for_service():
            return

        current_state = self.get_current_state()
        self.get_logger().info(f'Current State ID: {current_state}')

        # 1 = Unconfigured, 2 = Inactive, 3 = Active, 4 = Finalized
        if current_state == 1: # unconfigured
            self.get_logger().info('Configuring...')
            res = self.change_state(Transition.TRANSITION_CONFIGURE)
            if res and res.success:
                self.get_logger().info('Configured successfully.')
            else:
                self.get_logger().error('Configuration failed.')
                return

        current_state = self.get_current_state()
        if current_state == 2: # inactive
            self.get_logger().info('Activating...')
            res = self.change_state(Transition.TRANSITION_ACTIVATE)
            if res and res.success:
                self.get_logger().info('Activated successfully.')
            else:
                self.get_logger().error('Activation failed.')
                return

        self.get_logger().info('Piper Node is Active!')

def main(args=None):
    rclpy.init(args=args)
    starter = PiperStarter()
    starter.start()
    starter.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
