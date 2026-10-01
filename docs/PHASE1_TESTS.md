# Phase 1 acceptance tests — 2026-10-01

Use the focused build, sourced overlay and project DDS exports in
[the demo guide](../PHASE1_DEMO_GUIDE.md). Run one Gazebo/Phase 1 launch at a time.
The normal-mode smoke checker must pass before navigation or application tests.
Use `headless:=True rviz:=false` for faster automated tests; `rviz:=true` enables
visual inspection. No manual dragging, teleportation or injected action results.

## Common commands

```bash
ros2 launch cstam_phase1 phase1.launch.py headless:=True rviz:=false
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase1_smoke_test.sh"
ros2 topic info /cmd_vel -v
ros2 topic echo /delivery/status
```

Before each acceptance test: process inventory shows one intended launch/server,
no mapping helper, and no manual velocity publisher. Normal physical `/cmd_vel`
publisher is `velocity_smoother`. Controller/recovery publishers use
`/cmd_vel_nav`. Record actual action results, odometry, AMCL/TF and contacts.
Do not equate an accepted goal/service request with successful completion.

Direct kitchen planning:

```bash
ros2 action send_goal /compute_path_to_pose nav2_msgs/action/ComputePathToPose \
  '{goal: {header: {frame_id: map}, pose: {position: {x: 0.02, y: 9.27}, orientation: {z: 0.5008, w: 0.8655}}}, planner_id: GridBased}'
```

Navigation goal template; substitute one row's x/y/quaternion:

```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  '{pose: {header: {frame_id: map}, pose: {position: {x: 0.02, y: 9.27}, orientation: {z: 0.5008, w: 0.8655}}}}' --feedback
```

| Name | x | y | yaw | quaternion z | quaternion w |
|---|---:|---:|---:|---:|---:|
| kitchen | 0.02 | 9.27 | 1.049 | 0.5008 | 0.8655 |
| short point | -0.80 | 8.70 | 0.0 | 0.0 | 1.0 |
| table 1 | -6.36 | 1.32 | -0.522 | -0.2581 | 0.9661 |
| table 2 | -5.60 | 1.96 | 0.0 | 0.0 | 1.0 |
| dock | -3.63 | 0.85 | -0.522 | -0.2581 | 0.9661 |

A route's initial direct path and execution are separate checks. Saved costmap
costs in JSON are the OccupancyGrid encoding (0–100), not raw 0–255 Nav2 costs.

## Mapping test — VERIFIED

Purpose: prove the live map comes from real physical movement and scan data.

```bash
ros2 launch cstam_phase1 phase1.launch.py slam:=true rviz:=true
ros2 run cstam_phase1 mapping_route --ros-args \
  -p linear_speed:=0.08 -p angular_speed:=0.15 \
  -p leg_length:=1.0 -p legs:=1 -p safety_distance:=0.55
ros2 run nav2_map_server map_saver_cli -f /tmp/cstam_demo \
  --ros-args -p save_map_timeout:=15.0
```

Expected: real yaw/translation, scan/cloud messages, active SLAM, map growth,
PGM/YAML saved. Actual: 87 map messages; known cells 813 → 19,076, map width
198 → 322, 1.047 m odometry path, physical world start (11.4,6.95,0) to
(11.5678,8.28029,1.50292), zero non-ground contacts. Saved map 322 × 444 at
0.05 m. The measured run used a longer four-leg helper that was safely stopped
after the observed motion; the one-leg command above is the bounded demo.
The accepted navigation map was not overwritten. A final repetition of the
exact bounded one-leg GUI helper also completed: 71 map updates, known 813→18,851
cells, odometry 1.007 m, zero non-ground contacts, and a separate 323×423 saved map.
The temporary observer double-shutdown error occurred after final metrics were
captured; the production mapping helper and map saver exited normally.

## Localization / TF test — VERIFIED

Purpose: automatic AMCL and stable robot/sensor transforms.

```bash
ros2 topic echo --once /amcl_pose
ros2 run tf2_ros tf2_echo map odom
ros2 run tf2_ros tf2_echo map base_footprint
ros2 run tf2_ros tf2_echo base_footprint lidar_3d_link
```

Expected: automatic dock initialization, nontrivial map/odom registration,
continuous transforms during physical movement. Actual: normal health PASS=22
FAIL=0; corrected zero skid-centre reference had max 0.177 m error across six
matched turns versus 0.972 m with the earlier -0.18 m reference. Navigation
samples had approximate maximum translation discrepancies 0.22–0.30 m; samples
are not time-synchronized truth, so settled Gazebo poses define arrival errors.

## Raw navigation and kitchen reliability — VERIFIED

Purpose: separate direct planning, controller tracking, obstacle turns and a
physically valid passage. Expected: direct plan status 4/error 0, nonempty path,
NavigateToPose status 4/error 0, real odometry movement, no furniture contacts.

Start fresh at dock for each kitchen run. After the third kitchen arrival,
execute short point → table 1 → dock sequentially using the template above.
Do not reset/teleport between sequential goals.

| Test / actual route | Result | Time (s) | Recoveries | Physical position/yaw error | Actual status |
|---|---|---:|---:|---|---|
| Kitchen clean run 1 | SUCCEEDED | 172.18 | 4 | 0.118 m / 0.199 rad | VERIFIED |
| Kitchen clean run 2 | SUCCEEDED | 118.01 | 0 | 0.117 m / 0.181 rad | VERIFIED |
| Kitchen clean run 3 | SUCCEEDED | 119.81 | 0 | 0.154 m / 0.193 rad | VERIFIED |
| Nav 1: kitchen vicinity → short point | SUCCEEDED | 31.45 | 0 | 0.248 m / 0.203 rad | VERIFIED |
| Nav 2: dock → kitchen | SUCCEEDED | above | above | above | VERIFIED |
| Nav 3: short point → table 1 | SUCCEEDED | 161.06 | 1 | 0.073 m / 0.154 rad | VERIFIED |
| Nav 4: table 1 → dock passage | SUCCEEDED | 66.60 | 1 | 0.284 m / 0.118 rad | VERIFIED |

All initial direct paths succeeded; all recorded local-footprint lethal cell
centre counts and non-ground contacts were zero. Kitchen run 1 had one sampled
static-global lethal cell centre in the padded footprint when departing dock;
physical/local-contact evidence stayed clear. Dock/table 3 are safe at configured
headings, not under every arbitrary spin.

## Delivery runs 1 and 2 — VERIFIED

Purpose: task manager advances only on real action results; repeat fresh starts.

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
```

Expected: IDLE → pickup → customer → DELIVERY_COMPLETE → return → IDLE, three
successful Nav2 goals, physical kitchen/table/dock arrival. Actual:

| Fresh run | Time | Odom distance | New goals | Max active | Dock position / yaw error | Contacts |
|---|---:|---:|---|---:|---|---:|
| 1 | 349.943 s | 27.831 m | 3 × SUCCEEDED | 1 | 0.176 m / 0.094 rad | 0 non-ground |
| 2 | 332.553 s | 27.733 m | 3 × SUCCEEDED | 1 | 0.257 m / 0.081 rad | 0 non-ground |

An extra fresh GUI-enabled delivery also passed: 766.719 s, three SUCCEEDED
goals, max active 1, physical dock error 0.292 m / 0.127 rad, no non-ground contacts.
Display windows were minimized during that long mission to reduce rendering load;
visible startup and a separate 10.55 s short GUI navigation also passed.

The pickup acknowledgement is immediate; there is no physical food-loading
mechanism. Stage-specific real Gazebo pose snapshots are saved in application
acceptance JSON. Two independent launches passed health before their requests.

## Queue — VERIFIED

Purpose: deterministic FIFO, one active goal, no task corruption.

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
# While NAVIGATING_TO_PICKUP for table_1:
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_2}'
```

Expected: serve table 1, then kitchen/table 2, then dock; final empty queue/IDLE.
Actual: 587.653 s, 48.531 m odometry path, five new SUCCEEDED goals, maximum one
active, dock error 0.187 m / 0.047 rad, zero non-ground contacts. Requests arrived
at 4.049 s and 4.563 s; table 2 was queued during table 1 execution.

## Invalid / duplicate / empty request — VERIFIED

Purpose: reject malformed/repeated tasks without modifying active work.

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_2}'
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: unknown_table}'
ros2 topic pub --once /delivery/request std_msgs/msg/String "{data: ''}"
```

Send these while table 1 is active and table 2 already queued. Expected/actual:
all four reject messages preserved active table 1 and queued table 2; queue run
completed normally. Rejection text and status payloads are saved in JSON.

## Automatic dock return — VERIFIED

Purpose: last customer completion initiates a real dock goal. Command: delivery
request above. Expected: RETURNING_TO_DOCK → physical dock → IDLE. Actual: both
fresh deliveries and the queue run returned with real SUCCEEDED action results,
settled physical errors listed above, no furniture contacts.

## Manual return — VERIFIED

Purpose: station return from a real non-dock arrival. First use an idle raw
NavigateToPose to table 1; expected/actual approach SUCCEEDED (67.81 s).

```bash
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

Expected: accepted → one real dock goal → physical arrival → IDLE. Actual:
55.908 s, one new SUCCEEDED goal, 2.762 m odometry motion, dock error
0.251 m / 0.076 rad, no non-ground contacts. Active-goal cancellation races
are regression-tested; this real service test began from idle at table 1.

## Build / regression / smoke / portability

```bash
colcon build --symlink-install --packages-up-to cstam_phase1
colcon test --packages-select cstam_phase1 --event-handlers console_direct+
colcon test-result --verbose
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase1_smoke_test.sh"
git diff --check
```

Expected: five packages build, eleven tests pass, health FAIL=0, no whitespace errors.
Test suite covers location semantics, collision envelope/registration, self-filter
and clearing projection, controller/progress contract, and delivery cancellation/
queue/error handling. A separate source copy builds without the original overlay.
A pristine second OS/dependency installation remains NOT TESTED; the final focused rosdep check passed after using a temporary source list and
correcting the Python build dependency. No system rosdep configuration changed.

## Evidence files

- [Navigation checkpoint](phase1_navigation_checkpoint.json): historical pause
  checkpoint, core source hashes, six real Nav2 acceptance routes, three-controller
  and drive-reference comparisons, live semantic footprint/component audit.
- [Application acceptance](phase1_application_acceptance.json): two fresh deliveries,
  FIFO, rejection, manual docking, stage poses, action counts and contact results.
- [Mapping acceptance](phase1_mapping_acceptance.json): live map growth, real sensor
  counts, odometry and saved map dimensions.
- [Final report](../PHASE1_REPORT.md): final configuration, comparisons and caveats.

Detailed runtime logs remain outside the source repository. Acceptance JSONs are
intentional compact engineering records, not ROS runtime caches.
