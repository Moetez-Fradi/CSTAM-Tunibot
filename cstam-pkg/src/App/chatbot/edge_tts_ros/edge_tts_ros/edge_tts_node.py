#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from audio_common_msgs.action import TTS
import asyncio
import edge_tts
import pygame
import os
import tempfile
import threading

class EdgeTtsNode(Node):
    def __init__(self):
        super().__init__('edge_tts_node')
        
        self.voice = self.declare_parameter('voice', 'en-US-ChristopherNeural').value
        
        # Initialize pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            
        self._action_server = ActionServer(
            self,
            TTS,
            '/say',
            self.execute_callback
        )
        
        self.get_logger().info(f"Edge TTS Node started using voice: {self.voice}")

    async def speak(self, text):
        try:
            # Create a temporary file for the mp3
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                filename = tmp_file.name
            
            self.get_logger().info(f"Synthesizing: {text}")
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(filename)
            
            # Play using pygame
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            
            pygame.mixer.music.unload()
            os.remove(filename)
            return True
        except Exception as e:
            self.get_logger().error(f"Speech error: {e}")
            return False

    def execute_callback(self, goal_handle):
        self.get_logger().info(f"Received speech request: {goal_handle.request.text}")
        
        # We need to run the async speak in the event loop
        # Since ROS 2 callbacks run in their own executor threads, we might need a dedicated loop or use asyncio.run
        
        text = goal_handle.request.text
        
        # Create a new event loop for this thread if needed, or use a global one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(self.speak(text))
        loop.close()
        
        goal_handle.succeed()
        
        result = TTS.Result()
        result.text = text
        return result

def main(args=None):
    rclpy.init(args=args)
    node = EdgeTtsNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
