#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from audio_common_msgs.msg import AudioStamped
import struct
import subprocess
import threading
import time

class StreamingPlayer(Node):
    def __init__(self):
        super().__init__('streaming_player')
        self.sub = self.create_subscription(
            AudioStamped,
            '/piper/audio',
            self.callback,
            qos_profile_sensor_data
        )
        self.process = None
        self.last_rate = None
        self.get_logger().info("Streaming Player Started (stdin pipe)")

    def callback(self, msg):
        try:
            # Check if rate changed or process died
            if self.process is None or self.process.poll() is not None or self.last_rate != msg.audio.info.rate:
                if self.process:
                    try:
                        self.process.stdin.close()
                        self.process.terminate()
                    except:
                        pass
                
                self.last_rate = msg.audio.info.rate
                cmd = [
                    'paplay',
                    '--raw',
                    f'--rate={msg.audio.info.rate}',
                    f'--channels={msg.audio.info.channels}',
                    '--format=s16le',
                    # Read from stdin
                ]
                # Start new process
                self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                self.get_logger().info(f"Started paplay stream: {msg.audio.info.rate}Hz")

            # Pack data
            data = struct.pack(f'{len(msg.audio.audio_data.int16_data)}h', *msg.audio.audio_data.int16_data)
            
            # Write to stdin
            self.process.stdin.write(data)
            self.process.stdin.flush()
            
        except BrokenPipeError:
            self.get_logger().warn("Paplay broken pipe, restarting...")
            self.process = None
        except Exception as e:
            self.get_logger().error(f"Stream error: {e}")

    def destroy_node(self):
        if self.process:
            self.process.terminate()
        super().destroy_node()

def main():
    rclpy.init()
    node = StreamingPlayer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
