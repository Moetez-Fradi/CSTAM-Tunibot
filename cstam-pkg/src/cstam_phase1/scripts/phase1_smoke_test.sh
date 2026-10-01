#!/usr/bin/env bash
set -u

# A single ROS node observes all dependencies concurrently. Keep a hard outer
# timeout as protection against middleware or discovery failures.
HEALTH_TIMEOUT="${CSTAM_PHASE1_HEALTH_TIMEOUT:-25.0}"
HARD_TIMEOUT="${CSTAM_PHASE1_HARD_TIMEOUT:-35}"
PHASE1_SHARE="$(ros2 pkg prefix --share cstam_phase1)"
export FASTDDS_DEFAULT_PROFILES_FILE="${PHASE1_SHARE}/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_DEFAULT_PROFILES_FILE}"

timeout "${HARD_TIMEOUT}" ros2 run cstam_phase1 startup_health_check \
  --ros-args -p "timeout_sec:=${HEALTH_TIMEOUT}"
status=$?

if [ "${status}" -eq 124 ]; then
  echo "FAIL: startup health check exceeded ${HARD_TIMEOUT}s"
  echo "PASS=0 FAIL=1"
fi

exit "${status}"
