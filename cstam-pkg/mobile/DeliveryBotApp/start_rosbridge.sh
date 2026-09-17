#!/usr/bin/env bash
set -e
PORT="${1:-9090}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/kill_port.sh" "$PORT"
# تشغّل rosbridge على البورت المطلوب
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:="$PORT" ssl:=false
