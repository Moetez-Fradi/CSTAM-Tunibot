#!/usr/bin/env python3
import paramiko
import time
import threading
HOSTNAME = '192.168.79.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22
def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        return client
    except Exception as e:
        print(f"Connection Failed: {e}")
        return None
def main():
    client = create_client()
    if not client: return
    print("Connected. Fixing Permissions...")
    client.exec_command("chmod +x ~/ws/src/andino/andino_bringup/scripts/range_to_laserscan.py")
    print("Starting Robot (Lidar Disabled)...")
    print("Connected. Checking Topic (System Launched Manually)...")
    print("Running Diagnostics...")
    commands = [
        "ros2 topic list | grep ultrasonic",
        "ros2 control list_controllers"
    ]
    for cmd in commands:
        print(f"\nExample Command: {cmd}")
        stdin, stdout, stderr = client.exec_command(f"source ~/ws/install/setup.bash && {cmd}")
        print(stdout.read().decode())
        print(stderr.read().decode())
    print("Checking Driver Health (Odom Data)...")
    stdin, stdout, stderr = client.exec_command("source ~/ws/install/setup.bash && timeout 8 ros2 topic echo /odom")
    print(stdout.read().decode())
    print("Checking Ultrasonic Sensor Data...")
    stdin, stdout, stderr = client.exec_command("source ~/ws/install/setup.bash && timeout 8 ros2 topic echo /ultrasonic_sensor/range")
    print(stdout.read().decode())
    client.close()
if __name__ == '__main__':
    main()
