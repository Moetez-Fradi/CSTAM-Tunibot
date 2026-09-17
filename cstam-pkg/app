#!/usr/bin/env bash

# ---------- Kill stale rosbridge port FIRST ----------
echo "⚙️  Killing any process on port 9090..."
sudo fuser -k 9090/tcp 2>/dev/null || true
sleep 0.5

set -e  # don't use -u to avoid ROS env var issues

# ---------- Portable defaults ----------
PKG=${PKG:-deliverybot_bringup}
ROSBRIDGE_PORT=${ROSBRIDGE_PORT:-9090}
WEB_VIDEO_PORT=${WEB_VIDEO_PORT:-8080}
DASHBOARD_PORT=${DASHBOARD_PORT:-8502}
START_SLAM=${START_SLAM:-false}
START_MAP_HTTP=${START_MAP_HTTP:-false}
MAP_HTTP_PORT=${MAP_HTTP_PORT:-8070}

# ---------- Paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="${SCRIPT_DIR}"           # assume this script lives at the repo root
LOG_DIR="${HOME}/.ros"
mkdir -p "${LOG_DIR}"

echo "✅ app: workspace=${WS_ROOT}"

# ---------- Source ROS 2 (Humble) ----------
if [[ -f /opt/ros/humble/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  echo "Sourced /opt/ros/humble/setup.bash"
else
  echo "❌ ROS 2 Humble not found at /opt/ros/humble/setup.bash"
  echo "   Please install ROS 2 Humble or adjust the path in ./app"
  exit 1
fi

# ---------- Build & source workspace if needed ----------
pushd "${WS_ROOT}" >/dev/null
if [[ -f "install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source install/setup.bash || true
  echo "Sourced install/setup.bash"
else
  if [[ -d "src" ]]; then
    echo "⚙️  No install/ found. Building workspace with colcon..."
    colcon build --symlink-install
    # shellcheck disable=SC1091
    source install/setup.bash || true
    echo "Workspace built and sourced."
  else
    echo "❌ src/ folder not found at ${WS_ROOT}. Is this a ROS2 workspace?"
    popd >/dev/null
    exit 1
  fi
fi

# ---------- DDS / Domain (inherit-safe) ----------
# If you already exported ROS_DOMAIN_ID before running, we'll keep it.
: "${ROS_DOMAIN_ID:=0}"
: "${ROS_LOCALHOST_ONLY:=0}"   # 0 = allow LAN; set to 1 manually if you want loopback-only
export ROS_DOMAIN_ID ROS_LOCALHOST_ONLY
export CYCLONEDDS_URI="file://${WS_ROOT}/src/andino/andino_bringup/config/cyclonedds.xml"
echo "Using ROS_DOMAIN_ID=${ROS_DOMAIN_ID}, ROS_LOCALHOST_ONLY=${ROS_LOCALHOST_ONLY}"
echo "Using CYCLONEDDS_URI=${CYCLONEDDS_URI}"

# ---------- Launch ----------
echo "==> launching ${PKG}/app.launch.py (rosbridge:${ROSBRIDGE_PORT}, web_video:${WEB_VIDEO_PORT}, slam:${START_SLAM}, map_http:${START_MAP_HTTP}, map_http_port:${MAP_HTTP_PORT})"

set +e
ros2 launch "${PKG}" app.launch.py \
  rosbridge_port:="${ROSBRIDGE_PORT}" \
  web_video_port:="${WEB_VIDEO_PORT}" \
  start_slam:="${START_SLAM}" \
  start_map_http:="${START_MAP_HTTP}" \
  map_http_port:="${MAP_HTTP_PORT}" \
  yaml_path:="${WS_ROOT}/src/App/map_info/maps/office_simulation.yaml"
RC=$?
set -e
popd >/dev/null

# ---------- Fallback minimal stack ----------
if [[ ${RC} -ne 0 ]]; then
  echo "⚠️  Launch failed (rc=${RC}); starting minimal background services..."

  # rosbridge
  if ! pgrep -f "rosbridge_websocket" >/dev/null; then
    nohup env ROS_DOMAIN_ID="${ROS_DOMAIN_ID}" ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY}" \
      ros2 run rosbridge_server rosbridge_websocket --port "${ROSBRIDGE_PORT}" \
      > "${LOG_DIR}/rosbridge.log" 2>&1 &
    echo "  -> rosbridge_server on ${ROSBRIDGE_PORT}"
  else
    echo "  -> rosbridge_server already running"
  fi

  # web_video
  if ! pgrep -f "web_video_server" >/dev/null; then
    nohup env ROS_DOMAIN_ID="${ROS_DOMAIN_ID}" ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY}" \
      ros2 run web_video_server web_video_server --port "${WEB_VIDEO_PORT}" \
      > "${LOG_DIR}/web_video.log" 2>&1 &
    echo "  -> web_video_server on ${WEB_VIDEO_PORT}"
  else
    echo "  -> web_video_server already running"
  fi

  # slam (optional)
  if [[ "${START_SLAM}" == "true" ]] && ! pgrep -f "async_slam_toolbox_node" >/dev/null; then
    nohup env ROS_DOMAIN_ID="${ROS_DOMAIN_ID}" ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY}" \
      ros2 launch slam_toolbox online_async_launch.py \
      > "${LOG_DIR}/slam_toolbox.log" 2>&1 &
    echo "  -> slam_toolbox (online_async)"
  fi

  # map_http_bridge (optional)
  if [[ "${START_MAP_HTTP}" == "true" ]]; then
    if ros2 pkg executables map_http_bridge >/dev/null 2>&1; then
      if ! pgrep -f "map_http_bridge" >/dev/null; then
        nohup env ROS_DOMAIN_ID="${ROS_DOMAIN_ID}" ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY}" \
          ros2 run map_http_bridge map_http_bridge --port "${MAP_HTTP_PORT}" \
          > "${LOG_DIR}/map_http_bridge.log" 2>&1 &
        echo "  -> map_http_bridge on ${MAP_HTTP_PORT}"
      else
        echo "  -> map_http_bridge already running"
      fi
    else
      echo "  !! map_http_bridge package not found; skipping"
    fi
  fi

  echo "Minimal stack started. Logs in ${LOG_DIR}/"
fi

# ---------- Streamlit Dashboard (always start in background) ----------
DASHBOARD_SCRIPT="${WS_ROOT}/src/App/order_logger/dashboard/dashboard.py"
if [[ -f "${DASHBOARD_SCRIPT}" ]]; then
  # Kill any existing dashboard on this port
  if pgrep -f "streamlit.*${DASHBOARD_PORT}" >/dev/null; then
    echo "  -> Dashboard already running on port ${DASHBOARD_PORT}"
  else
    echo "  -> Starting Streamlit Dashboard on port ${DASHBOARD_PORT}..."
    
    # Auto-install dependencies for friends/users who might miss them
    if [[ -f "${WS_ROOT}/src/App/order_logger/dashboard/requirements.txt" ]]; then
        pip3 install -r "${WS_ROOT}/src/App/order_logger/dashboard/requirements.txt" >/dev/null 2>&1 || echo "  ⚠️  Auto-install of dashboard requirements failed (might need sudo or venv)"
    fi

    nohup python3 -m streamlit run "${DASHBOARD_SCRIPT}" \
      --server.port="${DASHBOARD_PORT}" \
      --server.address="0.0.0.0" \
      --server.headless=true \
      > "${LOG_DIR}/dashboard.log" 2>&1 &
    echo "  -> Dashboard started: http://0.0.0.0:${DASHBOARD_PORT}"
    echo "     Log: ${LOG_DIR}/dashboard.log"
  fi
else
  echo "  !! Dashboard script not found: ${DASHBOARD_SCRIPT}"
fi

exit 0

