# CSTAM Phase 1 Engineering Report

Date: 2026-09-29
Branch: `Youssef`
Scope: first floor only

## Executive status

This iteration implements and builds the Phase 1 integration, but it does not
honestly qualify as a complete end-to-end MVP yet.

| Area | Status | Evidence |
|---|---|---|
| Mapping and localization | PARTIAL | Real `/scan`, `/odom`, TF, SLAM Toolbox, map saving, map server, and AMCL were exercised. The current map candidate is not sufficiently complete for acceptance. |
| Autonomous navigation | PARTIAL | Nav2 lifecycle startup and a short real `NavigateToPose` goal succeeded. A longer goal failed to plan because the candidate map does not represent the restaurant reliably. |
| Delivery task management | PARTIAL | Real action-based state machine, queue, semantic locations, status service, and request topic are implemented. Full dock-kitchen-table-dock execution was not verified. |
| Auto-docking | PARTIAL | Real return-to-dock action path is implemented, but it depends on a validated map and was not accepted as a completed physical test. |
| First-floor-only scope | VERIFIED in code | `locations.yaml` declares floor 1 and the task manager rejects non-floor-1 locations. No elevator is required. |

The correct next engineering step is a fresh, sufficiently complete first-floor
SLAM coverage run after the collision-height correction, followed by four
navigation tests and the delivery test. The implementation does not fake any
of those results.

## Latest recovery and 3-D map diagnostic (2026-09-29)

After a PC shutdown, the `Youssef` branch was rebuilt without resetting or
discarding existing work. A fresh SLAM run used the real 16 x 360 point cloud,
`/scan_navigation`, real odometry, and real TF. The patrol exposed elevated
restaurant geometry at about 0.5 m in front of CSTAM; the helper now supports a
bounded side-avoidance turn and still hard-stops before collision.

The resulting candidate map is 345 x 486 cells at 0.05 m/cell. Dock, kitchen,
and all three tables are in one static free-space component. Live global-costmap
inspection found the original dock and table_2 semantic poses had lethal cells
inside the configured footprint after inflation, although their raw PGM cells
were free. The checked-in semantic poses were moved to the nearest measured
footprint-safe points: dock `(-3.63, 1.08)` and table_2 `(-3.96, 1.96)`.

Direct `ComputePathToPose` from the corrected dock to kitchen succeeds with
479 poses. Real DWB navigation still fails in the dining approach: the robot
departs the valid global path, the local controller reports failed progress,
and replanning from the displaced pose returns error 208. Regulated Pure
Pursuit was available and was compared on the same route; it oscillated at the
lower obstacle and did not complete. Therefore raw Nav2 remains PARTIAL and
delivery/docking/queue acceptance was not started.

## Automatic localization startup recovery (2026-09-29)

The intermittent state where lifecycle nodes were active but `/amcl_pose` and
`map -> odom` were absent had two observed causes. First, an orphaned Phase 1
static-transform process created a duplicate node and DDS participant. Second,
Fast DDS shared-memory initialization failures coincided with incomplete graph
discovery and a lost AMCL lifecycle response. The stale process was removed for
the clean test, and the Phase 1 launch now loads a project-local UDP transport
profile. No system-wide DDS configuration was changed.

The initial-pose helper now waits for a valid map, odometry, and an AMCL
`/initialpose` subscriber before publishing the configured dock pose. It waits
for an AMCL pose near that configured pose before declaring acknowledgement.
The helper no longer depends on an arbitrary delay or accepts AMCL's old
default pose as success.

A single-process startup health checker now verifies the advancing clock, map,
3-D cloud pipeline, projected scan, odometry, AMCL pose, both costmaps, the
complete TF chain, required lifecycle states, both Nav2 actions, and duplicate
node names. The final clean launch passed `PASS=21 FAIL=0` in 3.49 seconds.
From that automatic pose, dock-to-kitchen `ComputePathToPose` returned in 1.82
seconds with 479 poses and status `SUCCEEDED`. A short real NavigateToPose goal
also succeeded: Gazebo displacement was 0.758 m and odometry displacement was
0.760 m while AMCL remained available. The long dining-area controller issue
described above remains separate and unresolved.

## Perception architecture update

The runtime now uses one real simulated 3-D GPU LiDAR rather than two runtime
2-D height slices. It is mounted at approximately `(0.24, 0, 0.92)` in
`base_link`, produces a 360 x 16 multi-channel scan at 8 Hz, and reaches ROS as
`/lidar/points` (`sensor_msgs/msg/PointCloud2`, frame `lidar_3d_link`). The
project-local `pointcloud_navigation_filter` removes the known CSTAM self
volume, keeps the robot collision-height interval (world z about 0.04--1.18 m),
and publishes `/lidar/points_filtered` plus `/scan_navigation`.

`/scan_navigation` is the configured SLAM Toolbox and AMCL input. The local
Nav2 costmap uses a `VoxelLayer` on `/lidar/points_filtered`; the global map
remains static-map plus inflation. This preserves a 2-D map and AMCL while
retaining elevated chair/table/counter returns locally. The previous checked-in
map was generated before this sensor change and is therefore not accepted as
the final map until a new real-physics SLAM coverage run is completed.

## What the system means in beginner terms

- **Gazebo** is the physics and sensor simulator. It applies wheel commands and
  produces simulated odometry and sensor data.
- **URDF/Xacro** describes CSTAM's links, joints, dimensions, and sensor frames.
- A **ROS node** is a running program with a focused responsibility.
- A **topic** is a stream of messages. `/lidar/points` is the real 3-D LiDAR
  cloud; `/scan_navigation` is its 2-D projection;
  `/odom` is a stream of wheel-based motion estimates; `/cmd_vel` is the
  velocity command stream.
- A **service** is a short request/response operation. The task manager uses
  services for status and manual return-to-dock.
- An **action** is a long-running operation with feedback and a result.
  Nav2's `NavigateToPose` action is the real navigation interface used here.
- **TF** is the time-stamped coordinate transform tree. It tells each node
  where the robot and sensors are relative to one another.
- An **occupancy grid** is a 2-D map whose cells represent free, occupied, or
  unknown space. It is intentionally much simpler than Gazebo's textured
  visual scene.
- **SLAM Toolbox** builds that grid while estimating the robot pose.
- **AMCL** localizes against a saved grid; it does not build a new map.
- **Nav2** plans and executes safe motion on the saved map.
- A **costmap** is Nav2's planning view. The global costmap covers the saved
  floor, and the local costmap rolls around the robot using the 3-D cloud
  through a `VoxelLayer`.
- The **footprint** is the 2-D outline Nav2 protects. CSTAM uses a rectangle
  larger than Andino's footprint to include the shelves and a safety margin.
- **Inflation** expands obstacle costs around walls so the controller does not
  drive the body too close to them.
- A **semantic location** is a name such as `table_1`; the manager resolves it
  through `locations.yaml` instead of scattering coordinates through Python.
- The **dock** is the first-floor pose used as the return destination. Phase 1
  docking means reaching that pose with Nav2, not charging alignment.

## Final frame chain

```text
map
  -> odom
    -> base_footprint
      -> base_link
        -> lidar_3d_link
```

`map` is the saved restaurant coordinate system. `odom` is the continuous
short-term motion coordinate system. `base_footprint` is the planar robot
reference used by Nav2. `base_link` is CSTAM's body frame. `lidar_3d_link` is
the primary LiDAR sensor frame.

In normal operation AMCL publishes `map -> odom`. In mapping mode SLAM Toolbox
publishes it. The Gazebo odometry bridge publishes `odom -> base_footprint`.
`robot_state_publisher` publishes the two fixed robot transforms from the
URDF.

## SLAM diagnosis and changes

The real chain is:

```text
restaurant collision geometry -> Gazebo GPU LiDAR -> ros_gz_bridge
-> /lidar/points -> pointcloud_navigation_filter -> /scan_navigation
-> TF + /odom -> SLAM Toolbox -> /map
```

Observed real values:

- `/lidar/points` type: `sensor_msgs/msg/PointCloud2`
- cloud frame: `lidar_3d_link`
- cloud shape: 16 vertical channels by 360 horizontal samples
- `/scan_navigation` type: `sensor_msgs/msg/LaserScan`
- scan angles: approximately `-pi` to `+pi`
- range limits: approximately `0.10` to `15.0 m`
- observed GUI rate: roughly 2.8--6 Hz depending on rendering load
- `/odom`: `frame_id=odom`, `child_frame_id=base_footprint`
- fixed LiDAR transform: approximately `base_link -> lidar_3d_link = (0.240, 0, 0.795)`;
  the resulting world sensor height is about 0.92 m.

Two implementation problems were found:

1. The old Andino SLAM configuration used `base_link` instead of CSTAM's
   planar `base_footprint`.
2. The generated restaurant collision primitives were centered around world
   `z=3 m`, above CSTAM's roughly `z=0.27 m` LiDAR. They could be visible in a
   high-level visual scene but not contribute useful 2-D obstacle returns.

The CSTAM config now uses `base_footprint`, `/scan`, `/odom`, and simulation
time. The collision model was moved to the first-floor scanning height. A
post-fix scan probe observed a finite minimum range of about `0.154 m`, proving
that real close geometry is now reaching the sensor. This also means the old
candidate map must be regenerated; it was made before the geometry fix.

The first candidate map was generated by real SLAM Toolbox from Gazebo scans
and odometry and saved under:

```text
cstam-pkg/src/cstam_phase1/maps/restaurant/restaurant.yaml
cstam-pkg/src/cstam_phase1/maps/restaurant/restaurant.pgm
```

Map server loaded it successfully at 476 x 427 cells and 0.05 m/cell. It is
kept as a candidate, not certified as a complete first-floor map, because the
coverage run did not produce recognizable enough walls and free-space
boundaries for reliable restaurant navigation.

## Localization

SLAM answers: “the map is unknown; build it while estimating pose.” AMCL
answers: “the map is already saved; estimate pose inside it.” Normal operation
uses the saved YAML/PGM plus `/scan`, `/odom`, and TF. The initial-pose helper
publishes a configurable pose until AMCL responds; it does not modify the
robot pose or teleport CSTAM.

AMCL and map server were both configured and activated in a clean launch, and
`map -> odom` was observed. Repeatable localization across the full first-floor
map remains pending the regenerated acceptance map.

## Nav2 implementation

`cstam_phase1/config/nav2_params.yaml` configures map server, AMCL, planner,
controller, behavior server, BT navigator, costmaps, waypoint follower, and
velocity smoother. The planner is NavFn and the controller is DWB. The CSTAM
footprint is:

```text
[[0.31, 0.27], [0.31, -0.27], [-0.31, -0.27], [-0.31, 0.27]]
```

This is a conservative rectangle around the approximately 0.52 m by 0.46 m
body and shelves. Both costmaps use it and `base_footprint`; the local costmap
marks live cloud returns through `VoxelLayer`, while the global costmap is the
static map plus inflation.

Nav2 startup was fixed for ROS 2 Jazzy by using the current double-colon
behavior plugin names and by removing the old explicit BT library list that
double-loaded Jazzy built-ins. Clean startup reached `Managed nodes are
active`. A short real goal to `(0.0,-0.5)` succeeded. A longer goal to
`(3.0,-3.0)` was accepted but repeatedly failed to plan; logs showed:
`GridBased plugin failed to plan ... Failed to create plan with tolerance`.
That is evidence against claiming broad navigation is complete.

## Task manager

The node is `cstam_delivery_task_manager`. It accepts:

```text
/delivery/request          std_msgs/msg/String
/delivery/status           std_msgs/msg/String and Trigger service
/delivery/return_to_dock   Trigger service
```

It resolves names from `locations.yaml`, rejects unknown names, rejects floors
other than 1, rejects duplicates, queues requests, sends real
`NavigateToPose` goals, and advances only on real Nav2 action results.

The intended state machine is:

```text
IDLE -> NAVIGATING_TO_PICKUP -> NAVIGATING_TO_CUSTOMER
     -> DELIVERY_COMPLETE -> RETURNING_TO_DOCK -> IDLE
```

The code exists and builds. The full physical state progression is not claimed
until the map and semantic poses are revalidated.

## Exact command cheat sheet

### 3D perception inspection

```bash
ros2 topic info /lidar/points -v
ros2 topic echo /lidar/points --once
ros2 topic echo /lidar/points_filtered --once
ros2 topic echo /scan_navigation --once
ros2 run tf2_ros tf2_echo base_link lidar_3d_link
```

### Build

```bash
cd /home/youssef/Desktop/CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to cstam_phase1
source install/setup.bash
```

The repository-wide build was attempted. It is blocked by the unrelated
`llama_cpp_vendor` package because this machine has no CUDA Toolkit
(`CUDA Toolkit not found`). The selected Phase 1 dependency build succeeds.

### Mapping

```bash
ros2 launch cstam_phase1 phase1.launch.py slam:=true rviz:=true
ros2 run cstam_phase1 mapping_route --ros-args -p linear_speed:=0.10 -p angular_speed:=0.18
ros2 run nav2_map_server map_saver_cli -f /tmp/restaurant_phase1
```

Only replace the checked-in map after visual validation against Gazebo.

### Normal Phase 1 launch

```bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

### Requests and status

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String "{data: table_1}"
ros2 topic pub --once /delivery/request std_msgs/msg/String "{data: table_2}"
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

### Navigation/localization checks

```bash
ros2 action list | rg navigate
ros2 lifecycle get /map_server
ros2 lifecycle get /amcl
ros2 lifecycle get /planner_server
ros2 lifecycle get /controller_server
ros2 lifecycle get /bt_navigator
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 topic echo /odom --once
ros2 run tf2_ros tf2_echo map odom
ros2 run tf2_ros tf2_echo odom base_footprint
ros2 run tf2_ros tf2_echo base_link lidar_link
```

### Smoke test

```bash
cd /home/youssef/Desktop/CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
source install/setup.bash
bash install/cstam_phase1/share/cstam_phase1/scripts/phase1_smoke_test.sh
```

### Stop safely

Press `Ctrl+C` in the launch terminal. The launch system shuts down Gazebo and
ROS nodes. If a separately started mapping helper is running, press `Ctrl+C`
there first so it publishes zero velocity, then stop the launch.

## Troubleshooting

1. **`/scan` missing:** check `ros2 topic list`, then inspect the restaurant
   launch bridge and Gazebo log. Confirm the Sensors plugin remains in
   `restaurant.sdf`.
2. **`/scan` exists but no data:** run `ros2 topic echo /scan --once`; check
   Gazebo sensors, bridge type, `use_sim_time`, and the `lidar_link` TF.
3. **`/map` missing:** in mapping mode check the SLAM Toolbox lifecycle state
   and run `ros2 lifecycle get /slam_toolbox`.
4. **SLAM map does not grow:** verify `/scan`, `/odom`, and
   `tf2_echo odom base_footprint`; move slowly with the real mapping helper.
5. **`map -> odom` missing:** AMCL needs a map and an initial pose; SLAM needs
   its lifecycle node configured and activated.
6. **AMCL not localizing:** verify the map path, initial pose, scan frame, and
   `ros2 topic echo /amcl_pose --once`.
7. **Nav2 inactive:** inspect each lifecycle state and launch output; a single
   parameter/plugin failure prevents the navigation lifecycle manager from
   activating the stack.
8. **Global costmap empty:** check `/map`, `map -> base_footprint`, and the
   global costmap topic; confirm map server is active.
9. **Local costmap empty:** check `/scan`, `odom -> base_footprint`, and the
   obstacle-layer scan source.
10. **Robot does not move:** inspect `ros2 topic info /cmd_vel -v`; confirm the
    controller publishes and the Gazebo bridge subscribes.
11. **Wrong direction:** compare `/cmd_vel` and `/odom`; check the diff-drive
    wheel joints and signs in the CSTAM URDF.
12. **Robot spins:** inspect yaw in `/odom`, the goal yaw, AMCL pose, and the
    controller goal tolerances.
13. **Collision:** stop immediately, check the LiDAR ranges and footprint,
    then inspect the collision model at LiDAR height.
14. **No path:** check whether start and goal are free in the saved map; a
    goal outside the mapped first-floor region is invalid.
15. **Controller aborts:** inspect controller log output, local costmap, and
    progress checker; do not increase speed to hide the issue.
16. **Goal rejected:** run `ros2 action list`, inspect the goal frame, and
    confirm Nav2 lifecycle nodes are active.
17. **Stuck:** inspect `/cmd_vel`, `/odom`, local costmap, and recovery logs.
18. **Delivery pending:** call the status service and inspect the task-manager
    log; it may be waiting for Nav2 or may have entered `ERROR`.
19. **Auto-dock fails:** verify `dock` in `locations.yaml`, test that pose
    directly with NavigateToPose, and check the map/footprint before retrying.

## Deferred Phase 2 work

Elevator control, floor switching, second-floor maps, battery/low-battery
docking, charging alignment, advanced dynamic-obstacle behavior, full mobile
UI polish, voice, VIP recognition, and multi-robot coordination remain out of
Phase 1.
