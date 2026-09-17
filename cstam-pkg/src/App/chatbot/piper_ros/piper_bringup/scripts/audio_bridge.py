#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from audio_common_msgs.msg import AudioStamped
from rclpy.qos import qos_profile_sensor_data
import subprocess
import struct

class AudioBridge(Node):
    def __init__(self):
        super().__init__('audio_bridge')
        self.subscription = self.create_subscription(
            AudioStamped,
            '/piper/audio',
            self.listener_callback,
            qos_profile_sensor_data)
        self.get_logger().info('Dynamic Audio Bridge started. Waiting for stream...')
        
        self.paplay = None
        self.current_rate = None
        self.current_channels = None

    def start_paplay(self, rate, channels):
        if self.paplay:
            try:
                self.paplay.stdin.close()
                self.paplay.terminate()
                self.paplay.wait(timeout=1)
            except:
                self.paplay.kill()
        
        self.get_logger().info(f'Initializing paplay: {rate}Hz, {channels}ch, s16le')
        self.paplay = subprocess.Popen(
            ['paplay', '--raw', f'--channels={channels}', f'--rate={rate}', '--format=s16le'],
            stdin=subprocess.PIPE
        )
        self.current_rate = rate
        self.current_channels = channels

    def listener_callback(self, msg):
        try:
            rate = msg.audio.info.rate
            channels = msg.audio.info.channels
            
            # Auto-detect format changes
            if self.paplay is None or rate != self.current_rate or channels != self.current_channels:
                self.start_paplay(rate, channels)

            # Convert int16_data (PCM) to bytes
            if msg.audio.audio_data.int16_data:
                data = struct.pack('<' + 'h' * len(msg.audio.audio_data.int16_data), *msg.audio.audio_data.int16_data)
                self.paplay.stdin.write(data)
                self.paplay.stdin.flush()
        except Exception as e:
            self.get_logger().error(f'Bridge Error: {e}')

def main(args=None):
    rclpy.init(args=args)
    bridge = AudioBridge()
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        pass
    finally:
        if bridge.paplay:
            bridge.paplay.stdin.close()
            bridge.paplay.terminate()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
