#!/usr/bin/env python3
import asyncio
import json
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import websockets
PORT = 9090
class WSBridge(Node):
    def __init__(self):
        super().__init__('ws_bridge')
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.get_logger().info(f"WSBridge ready on 0.0.0.0:{PORT}")
    def publish_cmd(self, linear_x, angular_z):
        t = Twist()
        t.linear.x = float(linear_x)
        t.angular.z = float(angular_z)
        self.pub.publish(t)
async def handler(websocket, bridge: WSBridge):
    bridge.get_logger().info(f"Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            bridge.get_logger().info(f"RX: {message}")
            try:
                data = json.loads(message)
                t = data.get('type')
                if t == 'cmd_vel':
                    lx = data.get('linear', {}).get('x', 0.0)
                    az = data.get('angular', {}).get('z', 0.0)
                    bridge.publish_cmd(lx, az)
                    await websocket.send(json.dumps({'status':'ok'}))
                elif t == 'ping':
                    await websocket.send(json.dumps({'status':'pong'}))
                else:
                    await websocket.send(json.dumps({'status':'unknown_type'}))
            except Exception as e:
                await websocket.send(json.dumps({'error': str(e)}))
    finally:
        bridge.get_logger().info("Client disconnected")
async def ros_spin(bridge: WSBridge):
    while rclpy.ok():
        rclpy.spin_once(bridge, timeout_sec=0.05)
        await asyncio.sleep(0.01)
async def amain():
    rclpy.init()
    bridge = WSBridge()
    async with websockets.serve(lambda ws: handler(ws, bridge), '0.0.0.0', PORT):
        bridge.get_logger().info(f"WebSocket server started on 0.0.0.0:{PORT}")
        try:
            await ros_spin(bridge)
        finally:
            bridge.get_logger().info("Shutting down...")
            rclpy.shutdown()
def main():
    asyncio.run(amain())
if __name__ == '__main__':
    main()
