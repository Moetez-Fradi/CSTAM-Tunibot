#!/usr/bin/env python3
import paramiko
import time
import sys
import re
HOSTNAME = '192.168.79.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22
def test_launch():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {HOSTNAME}...")
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        transport = client.get_transport()
        channel = transport.open_session()
        channel.get_pty() 
        cmd = "source /opt/ros/humble/setup.bash && source ~/ws/install/setup.bash && ros2 launch andino_bringup andino_robot.launch.py"
        print(f"Executing: ros2 launch andino_bringup andino_robot.launch.py")
        channel.exec_command(cmd)
        start_time = time.time()
        output_buffer = ""
        try:
            while time.time() - start_time < 60.0:
                if channel.recv_ready():
                    chunk = channel.recv(1024).decode('utf-8', 'ignore')
                    sys.stdout.write(chunk)
                    output_buffer += chunk
                if channel.exit_status_ready():
                    print("\nProcess exited early.")
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            print("\nStopping remote process (Ctrl+C)...")
            channel.send(chr(3))
            time.sleep(2.0)
            channel.close()
            client.close()
        if "Free fall" in output_buffer:
            print("\n[FAIL] 'Free fall' warning detected!")
        elif "IMU Init: SUCCESS" in output_buffer or "Starting ImuFilter" in output_buffer:
             print("\n[SUCCESS] No 'Free fall' warnings detected.")
        else:
             print("\n[INFO] Launch ran, analyze logs above.")
    except Exception as e:
        print(f"Connection Failed: {e}")
if __name__ == '__main__':
    test_launch()
