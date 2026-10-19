#!/usr/bin/env bash
# Phase 2 dynamic-obstacle acceptance run.
#
# Launches the headless simulation in its own process group, waits for the
# startup health check, runs recorded deliveries among the scenario
# pedestrians, then stops the whole group.
#
# Usage: phase2_acceptance.sh OUTPUT_DIR [DELIVERIES]
#   DELIVERIES defaults to "['table_1', 'table_2', 'table_3']".
# Writes OUTPUT_DIR/{launch.log, health.txt, trial.json, trace.jsonl}.
set -u

OUT="${1:?usage: phase2_acceptance.sh OUTPUT_DIR [DELIVERIES]}"
DELIVERIES="${2:-['table_1', 'table_2', 'table_3']}"
mkdir -p "${OUT}"

PHASE1_SHARE="$(ros2 pkg prefix --share cstam_phase1)"
export FASTDDS_DEFAULT_PROFILES_FILE="${PHASE1_SHARE}/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_DEFAULT_PROFILES_FILE}"

setsid ros2 launch cstam_phase1 phase1.launch.py headless:=True rviz:=false \
  > "${OUT}/launch.log" 2>&1 &
LAUNCH=$!
cleanup() {
  kill -INT -- "-${LAUNCH}" 2>/dev/null
  sleep 10
  kill -9 -- "-${LAUNCH}" 2>/dev/null
}
trap cleanup EXIT

CSTAM_PHASE1_HEALTH_TIMEOUT=100.0 CSTAM_PHASE1_HARD_TIMEOUT=115 \
  bash "${PHASE1_SHARE}/scripts/phase1_smoke_test.sh" > "${OUT}/health.txt" 2>&1
grep -E "PASS=" "${OUT}/health.txt"

ros2 run cstam_phase1 dynamic_obstacle_trial --ros-args \
  -p deliveries:="${DELIVERIES}" -p timeout_sec:=1200.0 \
  -p output_file:="${OUT}/trial.json" -p record_file:="${OUT}/trace.jsonl"
