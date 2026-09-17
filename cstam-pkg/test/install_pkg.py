#!/usr/bin/env python3
import paramiko
import sys
import time
HOSTNAME = '192.168.79.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22
def install_remote():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {HOSTNAME}...")
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        transport = client.get_transport()
        session = transport.open_session()
        session.get_pty()
        cmd = "echo admin | sudo -S apt update && echo admin | sudo -S apt install -y ros-humble-range-sensor-broadcaster"
        print(f"Executing: {cmd}")
        session.exec_command(cmd)
        while True:
            if session.recv_ready():
                print(session.recv(1024).decode(), end="")
            if session.exit_status_ready():
                break
            time.sleep(0.1)
        status = session.recv_exit_status()
        if status == 0:
            print("\nInstallation Successful.")
        else:
            print(f"\nInstallation Failed with exit code {status}")
        client.close()
    except Exception as e:
        print(f"Connection Failed: {e}")
if __name__ == '__main__':
    install_remote()
