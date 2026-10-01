# CSTAM Phase 1 architecture

First-floor scope. [Standalone SVG](docs/phase1_architecture.svg),
[PNG](docs/phase1_architecture.png), [Mermaid source](docs/phase1_architecture.mmd), and
[Graphviz source](docs/phase1_architecture.dot).

## Simulation and perception

Gazebo Harmonic simulates the restaurant, full CSTAM collision geometry, four
wheel joints, ground/furniture contact sensors, and one GPU 3D LiDAR.
`ros_gz_bridge` provides real `/clock`, `/odom`, `/tf`, `/joint_states` and
`/lidar/points`. The cloud has **16 × 360** samples; the LiDAR sits at
`(0.24, 0, 0.92)` relative to the ground-projected body centre.

`pointcloud_navigation_filter` provides three separate products:

- `/lidar/points_filtered`: real scene returns in robot collision heights
  0.04–1.27 m, with geometric body self-points removed, for local obstacle marking.
- `/scan_navigation`: nearest real return per horizontal bin, ceiling 1.18 m,
  for AMCL and SLAM, consistent with the accepted map's projection.
- `/lidar/points_clearing`: finite scene/floor endpoints and valid organized
  no-return free rays, exclusively for voxel ray clearing. Gazebo +Inf no-return
  bins are reconstructed from sensor ring geometry at 15 m. NaN is unknown and
  is not treated as free. These endpoints never mark obstacles or enter SLAM.

The old 2D sensor/self-filter files remain as historical utilities; final bringup
uses the 3D pipeline above.

## Modes and TF ownership

Normal mode: saved map → map_server + AMCL → Nav2 + task manager.
Mapping mode: projected scan + wheel odometry → SLAM Toolbox → live map.
Only one of AMCL and SLAM publishes `map -> odom`.

```text
map -> odom -> base_drive -> base_footprint -> base_link -> lidar_3d_link
```

Gazebo DiffDrive owns `odom -> base_drive`; a zero-translation static transform
connects its virtual skid centre to `base_footprint`; robot_state_publisher owns
the robot links. Wheel state comes from the real Gazebo joint-state plugin.
World/map registration in `world_alignment.yaml` determines a consistent spawn
and enables diagnostic comparisons; it does not inject ground-truth localization.

The initial-pose helper waits for map, odometry and the AMCL subscriber, publishes
the configured dock, then waits for matching AMCL acknowledgement. The health
checker verifies 22 normal-mode conditions. A project-local Fast DDS UDP profile
reduces problems observed with interrupted shared-memory participants.

## Navigation

Global costmap: **static map + inflation**, no transient scan marking.
Local costmap: **rolling 4 × 4 m VoxelLayer + inflation** in odom; one marking
source and a separate clearing-only source. Seven 0.20 m vertical cells cover
1.40 m, above the full 1.245 m robot. Physical stale-voxel experiment cleared
three marked cells back to zero when the obstacle was removed.

NavFn Dijkstra plans the route. Rotation Shim aligns large initial/final heading
changes; DWB evaluates trajectories with the complete rectangular footprint.
PoseProgressChecker counts deliberate angular progress, avoiding translation-only
timeouts during valid service-speed rotations. A failed action remains a failure.
The velocity smoother is the sole physical command publisher:

```text
controller / recovery -> /cmd_vel_nav -> velocity_smoother -> /cmd_vel -> Gazebo
```

Robot collision envelope: 0.596 × 0.455 m. Configured footprint: 0.66 × 0.54 m;
0.01 m padding each side gives 0.68 × 0.56 m. Both costmaps use 0.51 m inflation,
scaling 5.0. Full footprint checking is retained; inflation is a cost field,
not proof of arbitrary-heading passage safety.

## Application

`/delivery/request` names resolve through `locations.yaml`. The task manager
owns a FIFO queue and one real NavigateToPose goal at a time:

```text
IDLE -> NAVIGATING_TO_PICKUP
     -> pickup reached acknowledgement -> NAVIGATING_TO_CUSTOMER
     -> DELIVERY_COMPLETE
     -> next queued customer's pickup, or RETURNING_TO_DOCK
     -> dock reached -> IDLE
```

Pickup acknowledgement is emitted immediately before the customer goal; there
is no physical load/unload mechanism or operator wait state in Phase 1.
Invalid, empty and duplicate requests preserve the active request/queue.
A rejected/aborted goal produces `ERROR`. Manual dock handles a pending goal
acknowledgement or active cancellation before starting the dock goal; a failed
dock stops in ERROR instead of retrying forever. Queued deliveries remain queued.

Auto-docking means autonomous return to the defined station pose, not connector
engagement. The delivered/queued/manual flows passed real simulation acceptance.

## Assets and exports

Restaurant visual meshes, authored first-floor collision alignment, robot
Xacro, launch/configuration, saved 345 × 486 map, semantic locations and
DDS profile are repository assets. Resolve them through package-share paths.
Build outputs and temporary runtime logs are not source deliverables.

Render the diagram with:

```bash
dot -Tsvg docs/phase1_architecture.dot -o docs/phase1_architecture.svg
```
