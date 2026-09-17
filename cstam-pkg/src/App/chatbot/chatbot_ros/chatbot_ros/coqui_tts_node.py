#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from audio_common_msgs.action import TTS
import subprocess
import json
import os
import threading
import time

class CoquiTTSNode(Node):
    def __init__(self):
        super().__init__('coqui_tts_node')
        
        # Path to xtts_service
        # Assuming xtts_service.py is in the same directory/package
        service_script = os.path.join(
            os.path.dirname(__file__), 
            'xtts_service.py'
        )
        
        if not os.path.exists(service_script):
            self.get_logger().error(f'XTTS Service script not found at: {service_script}')

        # Start persistent process
        # Use simple 'python3' assuming dependencies are installed in the environment
        # or allow user to configure via 'python_interpreter' parameter
        self.declare_parameter('python_interpreter', 'python3')
        python_exe = self.get_parameter('python_interpreter').get_parameter_value().string_value
        
        # If still using the hardcoded path for local dev, we can verify if it exists, else fallback
        # But better to just default to 'python3' for portability.
        # User's friends will use 'python3'. User can set param if they really need the conda env.
        
        cmd = [python_exe, '-u', service_script]
        self.get_logger().info(f'Launching XTTS Service: {" ".join(cmd)}')
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # Line buffered
        )
        
        # Start stderr reader thread to log service output
        threading.Thread(target=self._log_stderr, daemon=True).start()
        
        self.get_logger().info('Waiting for XTTS Service to initialize (this may take time)...')
        self._wait_for_service()
        self.get_logger().info('Coqui TTS Node ready.')

        self._action_server = ActionServer(
            self,
            TTS,
            'say',
            self.execute_callback)

    def _wait_for_service(self):
        """Blochs untli valid JSON {'status': 'ready'} is received."""
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Service process died during initialization")
            
            try:
                msg = json.loads(line)
                if msg.get('status') == 'ready':
                    self.get_logger().info('XTTS Service is READY.')
                    return
            except json.JSONDecodeError:
                # Likely a library startup log printed to stdout instead of stderr
                self.get_logger().info(f'[XTTS Startup] {line.strip()}')
    
    def _log_stderr(self):
        """Reads stderr from subprocess and logs it to ROS logger."""
        try:
            for line in iter(self.process.stderr.readline, ''):
                if line:
                    self.get_logger().info(f'[XTTS Service] {line.strip()}')
                else:
                    break
        except Exception as e:
            self.get_logger().warn(f'Error reading service stderr: {e}')

    def execute_callback(self, goal_handle):
        self.get_logger().info('Executing goal...')
        text = goal_handle.request.text
        
        if not text:
            self.get_logger().warn('Received empty text goal.')
            goal_handle.succeed()
            return TTS.Result()
            
        self.get_logger().info(f'Requesting speech: "{text}"')

        # Send request to service
        # Note: 'Ana Florence' is strictly hardcoded here as verified working
        req = {'text': text, 'language': 'ar', 'speaker': 'Ana Florence'}
        try:
            # Write to stdin
            self.process.stdin.write(json.dumps(req) + '\n')
            self.process.stdin.flush()
            
            # Read response from stdout
            # We assume one JSON line per request
            response_line = self.process.stdout.readline()
            
            if not response_line:
                self.get_logger().error('Service closed stream unexpectedly (EOF)')
                goal_handle.abort()
                return TTS.Result()
                
            resp = json.loads(response_line)
            
            if resp.get('status') == 'success':
                wav_file = resp.get('file_path')
                self.get_logger().info(f'Playing audio: {wav_file}')
                
                # Play audio using aplay (blocking play for the duration of speech)
                subprocess.run(['aplay', '-q', wav_file])
                
                # Clean up temp file
                try:
                    if os.path.exists(wav_file):
                        os.remove(wav_file)
                except Exception as e:
                    self.get_logger().warn(f'Failed to remove temp file: {e}')
                    
                goal_handle.succeed()
                return TTS.Result()
            else:
                self.get_logger().error(f'TTS Service failed: {resp.get("message")}')
                goal_handle.abort()
                return TTS.Result()
                
        except Exception as e:
            self.get_logger().error(f'Exception during execution: {e}')
            goal_handle.abort()
            return TTS.Result()

def main(args=None):
    rclpy.init(args=args)
    node = CoquiTTSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup process on exit
        if node.process:
            node.process.terminate()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
