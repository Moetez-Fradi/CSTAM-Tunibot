# CSTAM Phase 1 Architecture

This document describes the implementation currently in the repository. The
scope is deliberately limited to the first floor.

```mermaid
flowchart LR
    U[User / terminal] -->|std_msgs/String: location name| T[Delivery Task Manager]
    L[locations.yaml] --> T
    T -->|NavigateToPose action| N[Nav2]
    N --> P[NavFn planner]
    N --> C[DWB controller]
    C -->|geometry_msgs/Twist| V[/cmd_vel]
    V --> B[CSTAM differential drive]
    B --> G[Gazebo physics]
    G --> O[/odom]
    G --> PC[/lidar/points PointCloud2]
    PC --> F[3D self-filter + height projection]
    F --> S[/scan_navigation LaserScan]
    F --> V3[/lidar/points_filtered PointCloud2]
    O --> TF[TF tree]
    S --> TF
    M[restaurant.yaml + restaurant.pgm] --> MS[map_server]
    MS --> A[AMCL]
    S --> A
    O --> A
    A -->|map -> odom| TF
    TF --> N
    V3 --> CM[Nav2 local voxel costmap]
    CM --> C
```

## Runtime modes

`phase1.launch.py slam:=false` starts the restaurant, CSTAM, real Gazebo
bridges, the saved-map map server, AMCL, Nav2, the initial-pose helper, and the
delivery task manager.

`phase1.launch.py slam:=true` starts the restaurant, CSTAM, bridges, and
SLAM Toolbox. The mapping route helper can then drive CSTAM with real
`/cmd_vel`; map saving remains an explicit operator step.

## Normal-mode startup handshake

Normal mode uses this readiness chain:

```text
Gazebo clock + sensors + odometry
  -> map_server and AMCL active
  -> valid /map and /odom plus AMCL /initialpose subscriber
  -> publish configured dock pose on /initialpose
  -> observe AMCL pose near that dock pose
  -> map -> odom and map -> base_footprint become available
  -> planner and controller have a current robot pose
```

`startup_health_check` tests this chain with one bounded ROS participant rather
than a sequence of unrelated CLI processes. The smoke wrapper has a hard
timeout and prints explicit `PASS=<n> FAIL=<n>` totals.

The launch also sets a package-local Fast DDS UDP profile for every child
process. This avoids the shared-memory lock failures that were observed with a
stale DDS participant while preserving the host's global ROS configuration.

## Frame ownership

```text
map -> odom -> base_footprint -> base_link -> lidar_3d_link
```

- `map -> odom`: AMCL in normal operation, or SLAM Toolbox in mapping mode.
- `odom -> base_footprint`: the Gazebo differential-drive odometry bridge.
- `base_footprint -> base_link`: CSTAM `robot_state_publisher`.
- `base_link -> lidar_3d_link`: CSTAM URDF fixed joint through
  `robot_state_publisher`.

## 3D LiDAR perception

The accepted runtime has one simulated Gazebo GPU LiDAR at approximately
`(x=0.24, y=0, z=0.92)` in `base_link`, with 360 horizontal samples and 16
vertical channels covering roughly -60 to +20 degrees. Gazebo and
`ros_gz_bridge` publish the real cloud as `/lidar/points` (`PointCloud2`).
`pointcloud_navigation_filter` removes only points inside the known CSTAM
self-volume and keeps world heights about 0.04--1.18 m. It publishes the
filtered cloud to `/lidar/points_filtered` for the local `VoxelLayer`, and a
nearest-return 2-D projection to `/scan_navigation` for SLAM Toolbox, AMCL,
and the mapping helper. The old low/upper 2-D sensor links and
`scan_self_filter` source remain for debugging, but they are not started by
the final Phase 1 launch.

The navigation configuration uses `base_footprint`, not Andino's smaller
`base_link`-based footprint.

## Delivery flow

The task manager accepts a semantic name such as `table_1`. It loads the name
from `maps/restaurant/locations.yaml`, rejects unknown or non-first-floor
locations, and sends three real Nav2 goals when the queue is empty:

```text
IDLE
  -> NAVIGATING_TO_PICKUP
  -> NAVIGATING_TO_CUSTOMER
  -> DELIVERY_COMPLETE
  -> RETURNING_TO_DOCK
  -> IDLE
```

If another request arrives while busy, it is queued. A failed Nav2 action puts
the task manager in `ERROR`; it does not pretend that delivery succeeded.

## Important current limitation

The original generated restaurant collision primitives were centered around
`z=3 m`, above CSTAM's old 2-D LiDAR. Their vertical placement was corrected in
`restaurant_collision/model.sdf`; the real 3-D scan now observes close
geometry. A 345 x 486 candidate map was regenerated from that sensor chain and
validated for static connectivity. Long-route controller acceptance remains
open because DWB and RPP both have trouble tracking the dining-area approach.
