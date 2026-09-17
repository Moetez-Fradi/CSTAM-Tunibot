#!/usr/bin/env python3
import paramiko
import sys
HOSTNAME = '192.168.79.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22
def check_pkg():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        cmd = "source /opt/ros/humble/setup.bash && ros2 pkg list | grep range_sensor_broadcaster"
        stdin, stdout, stderr = client.exec_command(cmd)
        content = stdout.read().decode()
        if "range_sensor_broadcaster" in content:
            print("FOUND: range_sensor_broadcaster")
        else:
            print("NOT FOUND: range_sensor_broadcaster")
        client.close()
    except Exception as e:
        print(f"Connection Failed: {e}")
if __name__ == '__main__':
    check_pkg()
