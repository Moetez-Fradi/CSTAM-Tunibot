#!/usr/bin/env bash
# Map the upper dining room (floor 2) with SLAM Toolbox.
#
# Spawns the robot upstairs (map 0.90, -14.40, facing east), drives the
# odometry mapping patrol round the room's aisles, saves the map, and aligns
# it into the shared map frame (scripts/align_floor2_map.py), writing
# maps/restaurant/floor2.{pgm,yaml} in the source tree.
#
# Usage (from the workspace, sourced): map_floor2.sh OUTPUT_DIR SRC_MAPS_DIR
set -u
OUT="${1:?usage: map_floor2.sh OUTPUT_DIR SRC_MAPS_DIR}"
MAPS="${2:?usage: map_floor2.sh OUTPUT_DIR SRC_MAPS_DIR}"
mkdir -p "${OUT}"
SPAWN_X=0.90; SPAWN_Y=-14.40; FLOOR_Z=2.56
PHASE1_SHARE="$(ros2 pkg prefix --share cstam_phase1)"
export FASTDDS_DEFAULT_PROFILES_FILE="${PHASE1_SHARE}/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_DEFAULT_PROFILES_FILE}"
read WX WY < <(python3 -c "import yaml; a = yaml.safe_load(open('${PHASE1_SHARE}/maps/restaurant/world_alignment.yaml'))['world_from_map']; print(a['x'] + ${SPAWN_X}, a['y'] + ${SPAWN_Y})")

setsid ros2 launch cstam_phase1 phase1.launch.py slam:=true headless:=True rviz:=false \
  robot_x:="${WX}" robot_y:="${WY}" robot_z:="$(python3 -c "print(${FLOOR_Z} + 0.02)")" robot_yaw:=0.0 \
  > "${OUT}/launch.log" 2>&1 &
LAUNCH=$!
cleanup() { kill -INT -- "-${LAUNCH}" 2>/dev/null; sleep 8; kill -9 -- "-${LAUNCH}" 2>/dev/null; }
trap cleanup EXIT

# SLAM is up once /map is published.
for _ in $(seq 1 60); do
  timeout 3 ros2 topic echo --once /map nav_msgs/msg/OccupancyGrid --field info.resolution >/dev/null 2>&1 && break
  sleep 2
done
# Round the perimeter aisles (west, south, east, north), then down the centre.
ros2 run cstam_phase1 mapping_route --ros-args \
  -p linear_speed:=0.18 -p angular_speed:=0.3 -p safety_distance:=0.45 \
  -p leg_lengths:="0,6.9,14.6,13.6,14.6,6.7,7.2" -p turn_directions:="1,1,1,1,1,1,1" \
  > "${OUT}/route.log" 2>&1
tail -2 "${OUT}/route.log"
sleep 5
ros2 run nav2_map_server map_saver_cli -f "${OUT}/floor2_slam" --ros-args -p save_map_timeout:=15.0 \
  > "${OUT}/saver.log" 2>&1
python3 "${PHASE1_SHARE}/scripts/align_floor2_map.py" "${OUT}/floor2_slam.yaml" "${SPAWN_X}" "${SPAWN_Y}" "${MAPS}"
