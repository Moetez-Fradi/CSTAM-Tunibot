# CSTAM Phase 1 — evaluator demo

Requirements: Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic, declared ROS packages,
OpenGL for GUI. Build and dependency instructions are in [README.md](README.md).
Work from `CSTAM-Tunibot/cstam-pkg`; every command below uses installed assets.

## 1. Build and prepare each terminal

```bash
cd /home/youssef/Desktop/CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to cstam_phase1
source install/setup.bash
export FASTDDS_DEFAULT_PROFILES_FILE="$(ros2 pkg prefix --share cstam_phase1)/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_DEFAULT_PROFILES_FILE"
```

The first path is an example checkout path; replace it on another machine.

## 2. Normal operation

```bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

Gazebo opens the restaurant view, RViz opens the saved map, scan and robot;
AMCL initializes without clicking an initial-pose tool. In terminal 2:

```bash
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase1_smoke_test.sh"
ros2 topic info /cmd_vel -v
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
```

Require `PASS=22 FAIL=0`, one ROS `/cmd_vel` publisher (`velocity_smoother`),
and `IDLE`. No `mapping_route`, manual teleop or duplicate launch may be running.
Use `headless:=True rviz:=false` for faster automated execution.

## 3. Complete delivery

```bash
ros2 topic echo /delivery/status
```

In terminal 3:

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
```

Observe `NAVIGATING_TO_PICKUP`, pickup reached, `NAVIGATING_TO_CUSTOMER`,
`DELIVERY_COMPLETE`, `RETURNING_TO_DOCK`, then `IDLE` at dock. All motion is
real NavigateToPose. Headless complete deliveries measured **349.943 s** and
**332.553 s**; a complete delivery cannot be shown in real time in a 3-minute
video. An extra fresh GUI-enabled delivery passed in 766.72 s with windows minimized
during its long mission. GUI performance varies; wait for actual results, not
a fixed deadline.

## 4. Queue and rejection behavior

Start a new table 1 request, then publish table 2 while it is busy:

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_2}'
```

The first delivery completes, then CSTAM revisits kitchen and serves table 2,
then returns to dock. Queue acceptance measured 587.653 s, five successful
navigation goals, maximum one active goal, and an empty queue at final IDLE.

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_2}'
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: unknown_table}'
ros2 topic pub --once /delivery/request std_msgs/msg/String "{data: ''}"
```

During the queue run, duplicate table 1/table 2, unknown and empty requests
were rejected without corrupting the active task or queue.

## 5. Manual docking from a non-dock pose

After an idle raw RViz navigation goal arrives at table 1, call:

```bash
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

Service acknowledgement is acceptance of the request, not arrival. Wait for
the real dock action and `IDLE at first-floor dock`. The accepted manual test
completed in 55.908 s with 0.251 m physical station-pose position error.
No precise charger engagement is implemented.

## 6. Separate live mapping demo

Ctrl+C the normal launch, wait for its children to exit, and inspect:

```bash
ps -eo pid,ppid,stat,cmd | grep -E 'gz sim|ros2 launch|mapping_route' | grep -v grep
```

Stop only your own stale test processes if any remain. Do not run two Gazebo
servers or reuse a navigation helper from the previous mode.

```bash
ros2 launch cstam_phase1 phase1.launch.py slam:=true rviz:=true
```

Use one manual teleop terminal or the helper, never both:

```bash
ros2 run cstam_phase1 mapping_route --ros-args \
  -p linear_speed:=0.08 -p angular_speed:=0.15 \
  -p leg_length:=1.0 -p legs:=1 -p safety_distance:=0.55
```

The helper first turns, then physically drives. The tested live map grew from
813 to 19,076 known cells during 1.05 m measured motion. Rendering can reduce
simulation speed; use headless mapping plus RViz for a faster demonstration.
After motion, save a **separate** demonstration map:

```bash
ros2 run nav2_map_server map_saver_cli -f /tmp/cstam_demo \
  --ros-args -p save_map_timeout:=15.0
```

The saved PGM/YAML pair is the expected result. Do not overwrite the accepted
repository navigation map. Mapping mode has no delivery/AMCL/Nav2 stack.

## 7. Regression tests and cleanup

```bash
colcon test --packages-select cstam_phase1 --event-handlers console_direct+
colcon test-result --verbose
git diff --check
```

Stop helpers before stopping the launch. Confirm no own Gazebo/ROS test children
remain before another mode. See [test cases](docs/PHASE1_TESTS.md),
[measured report](PHASE1_REPORT.md) and [video plan](PHASE1_VIDEO_SCRIPT.md).
