#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/kill_port.sh" 8080
python3 "$SCRIPT_DIR/mjpeg_server.py"
