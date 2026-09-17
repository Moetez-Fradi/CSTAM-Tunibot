#!/usr/bin/env bash
set -e
PORT="$1"
if [ -z "$PORT" ]; then
  echo "Usage: $0 <port>"; exit 1
fi
if command -v fuser >/dev/null 2>&1; then
  fuser -k -n tcp "$PORT" 2>/dev/null || true
else
  PIDS=$(lsof -t -i tcp:"$PORT" || true)
  [ -n "$PIDS" ] && kill -9 $PIDS || true
fi
echo "Freed TCP port $PORT (if it was busy)."
