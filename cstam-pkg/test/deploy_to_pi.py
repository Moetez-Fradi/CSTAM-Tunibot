#!/usr/bin/env python3
import paramiko
import os
import sys
HOSTNAME = '192.168.200.13'
USERNAME = 'pi'
PASSWORD = 'admin'
PORT = 22
def upload_files(sftp):
    local_base = '/home/mo/ws/'
    remote_base = 'ws/'
    source_dir = 'src/andino'
    
    print(f"Starting recursive upload of {source_dir}...")
    
    abs_source = os.path.join(local_base, source_dir)
    for root, dirs, files in os.walk(abs_source):
        for file in files:
            if file.endswith('.pyc') or file.startswith('.') or '__pycache__' in root:
                continue
                
            local_path = os.path.join(root, file)
            rel_path = os.path.relpath(local_path, local_base)
            remote_path = os.path.join(remote_base, rel_path)
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                # Recursively create directories
                parts = remote_dir.split('/')
                current = ""
                for part in parts:
                    if not part: continue
                    current += part + "/"
                    try:
                        sftp.stat(current)
                    except FileNotFoundError:
                        sftp.mkdir(current)

            try:
                # print(f"Uploading {rel_path}...")
                sftp.put(local_path, remote_path)
            except Exception as e:
                print(f"Failed to upload {rel_path}: {e}")
    print("Upload finished.")

COMMANDS_TO_RUN = [
    "source /opt/ros/humble/setup.bash && cd ~/ws && colcon build --symlink-install --cmake-clean-first --packages-select andino_base andino_control andino_description andino_bringup andino_navigation"
]

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOSTNAME, PORT, USERNAME, PASSWORD, timeout=10)
        return client
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

def run_remote_commands(client):
    print("\nRunning remote commands...")
    for cmd in COMMANDS_TO_RUN:
        print(f"Executing: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        for line in iter(stdout.readline, ""):
            print(line, end="")
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"Error executing command: {cmd}")
            print(stderr.read().decode())
        else:
            print("Command Success.\n")
def main():
    client = create_ssh_client()
    if not client:
        sys.exit(1)
    client.exec_command("mkdir -p ws/src/andino/andino_bringup/scripts")
    
    # Sync time
    import time
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Syncing remote time to: {current_time}")
    # Using sudo -S to accept password from stdin if needed, though often pi user has passwordless sudo.
    # We try both or just assume passwordless or use the password variable.
    # Safe approach: echo password | sudo -S date ...
    sync_cmd = f'echo {PASSWORD} | sudo -S date -s "{current_time}"'
    stdin, stdout, stderr = client.exec_command(sync_cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        print("Time synced successfully.")
    else:
        print(f"Failed to sync time: {stderr.read().decode()}")

    sftp = client.open_sftp()
    upload_files(sftp)
    sftp.close()
    run_remote_commands(client)
    client.close()
    print("\nDeployment Completed.")
if __name__ == '__main__':
    main()
