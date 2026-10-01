# CSTAM Tunibot — Phase 1

First-floor restaurant service robot using **ROS 2 Jazzy / Gazebo Harmonic**.
Real simulated 3D LiDAR, SLAM Toolbox, AMCL, Nav2, semantic delivery requests,
FIFO queue, and autonomous return to a defined dock pose.

**Measured acceptance:** kitchen 3/3, raw Nav2 4/4, two fresh complete deliveries,
queued table 1 then table 2, invalid/duplicate rejection, and manual dock return
passed. Details and physical arrival errors are in [PHASE1_REPORT.md](PHASE1_REPORT.md).
Docking here means autonomous station-pose arrival, not charger alignment.
Current local engineering changes await review; they have not been committed or pushed.

## Prerequisites and focused build

Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic through ROS Gazebo packages,
colcon, rosdep, and an OpenGL display for GUI use. On a new machine, initialize
rosdep once (`sudo rosdep init`, then `rosdep update`). Install dependencies
for the five-package Phase 1 closure, excluding unrelated legacy applications:

```bash
git clone --branch Youssef https://github.com/Moetez-Fradi/CSTAM-Tunibot.git
cd CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths \
  src/cstam_phase1 src/cstam_robot src/andino_gz/andino_gz \
  src/andino/andino_description src/andino/andino_slam \
  --ignore-src -r -y --rosdistro jazzy
colcon build --symlink-install --packages-up-to cstam_phase1
source install/setup.bash
```

Repeat the two `source` commands in every terminal. Launch children use a
package-local Fast DDS UDP profile. To make separate CLI terminals use it too:

```bash
export FASTDDS_DEFAULT_PROFILES_FILE="$(ros2 pkg prefix --share cstam_phase1)/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_DEFAULT_PROFILES_FILE"
```

## Normal operation: one launch

```bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

The saved map loads, AMCL initializes at the configured dock, and the navigation
and delivery nodes start. In a second sourced terminal, require `FAIL=0`:

```bash
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase1_smoke_test.sh"
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
ros2 topic echo /delivery/status
```

The sequence is kitchen → table 1 → dock → `IDLE`. A complete delivery took
333–350 seconds in headless tests; GUI rendering can make wall time longer: an extra GUI-enabled delivery passed
in 766.72 seconds, with the display windows minimized during the long mission.
While busy, publishing `table_2` queues a second delivery. Duplicates, empty
requests and unknown names are rejected without changing the active task.
The FIFO policy serves queued customers before returning to dock.

```bash
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

Manual return cancels an application-owned active goal, waits for its result,
then sends the real dock goal. Pending queued requests remain queued.
A failed navigation puts the application in `ERROR`; success is never synthesized.
Do not send separate raw goals while a delivery is active.

## Mapping: separate mode

Stop the normal launch and verify its children have exited. Then:

```bash
ros2 launch cstam_phase1 phase1.launch.py slam:=true rviz:=true
```

In a second sourced terminal, drive manually with one teleop publisher:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p speed:=0.10 -p turn:=0.20
```

Or use the bounded helper **instead of teleop**:

```bash
ros2 run cstam_phase1 mapping_route --ros-args \
  -p linear_speed:=0.08 -p angular_speed:=0.15 \
  -p leg_length:=1.0 -p legs:=1 -p safety_distance:=0.55
```

The helper turns first, then drives; it uses real odometry and the navigation
scan and stops for an obstacle. Ctrl+C stops it. SLAM updates `/map` in RViz.
Save to a separate path to preserve the accepted map:

```bash
ros2 run nav2_map_server map_saver_cli -f /tmp/cstam_demo \
  --ros-args -p save_map_timeout:=15.0
```

Mapping launches no AMCL, Nav2, or task manager. The normal-mode smoke checker
is intended for normal mode. Restart normal mode to use the accepted map.

## Navigation, tests and evidence

RViz includes a `Nav2 Goal` tool. A direct kitchen goal is:

```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  '{pose: {header: {frame_id: map}, pose: {position: {x: 0.02, y: 9.27}, orientation: {z: 0.5008, w: 0.8655}}}}' --feedback
colcon test --packages-select cstam_phase1 --event-handlers console_direct+
colcon test-result --verbose
```

Use `headless:=True rviz:=false` for faster server-only execution.
Before changing modes or starting acceptance tests, check that no mapping
helper or old launch remains and inspect `ros2 topic info /cmd_vel -v`.
Normal mode has one physical command publisher, `velocity_smoother`.

- [Architecture and diagram](PHASE1_ARCHITECTURE.md)
- [Measured engineering report](PHASE1_REPORT.md)
- [Reproducible test cases](docs/PHASE1_TESTS.md)
- [Exact demo sequence](PHASE1_DEMO_GUIDE.md)
- [Three-minute video plan](PHASE1_VIDEO_SCRIPT.md)
- [Submission checklist](PHASE1_SUBMISSION_CHECKLIST.md)

## Repository structure

- `cstam-pkg/src/cstam_robot`: robot Xacro, physics, sensors and bridge configuration.
- `cstam-pkg/src/andino_gz/andino_gz`: restaurant assets, collision model, world and GUI launch.
- `cstam-pkg/src/cstam_phase1`: perception, mapping/localization, Nav2, semantic locations, task manager, health checks and tests.
- `docs`: intentional acceptance summaries and architecture exports.

All runtime assets resolve through package-share directories. Build/install/log,
ROS logs and temporary measurements are excluded. A separate workspace source
copy was built for portability; a pristine second machine was not tested.

## Limits

First floor only; no elevator/battery/charger-contact behavior. Static global
map and real rolling local obstacles. Sparse 16-ring sensing and simulated
friction limit real-hardware conclusions. Dock and table 3 are safe at their
configured headings, not at every possible rotation. Physical dock error in
accepted application runs was 0.176–0.292 m. Controller recovery maneuvers still
occur; these trials establish repeatability for the tested routes, not universal
collision avoidance. See the report for quantitative caveats.
