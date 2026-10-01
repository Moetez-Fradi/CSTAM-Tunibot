# First-floor CSTAM restaurant simulation

Phase 1 uses ROS 2 Jazzy and Gazebo Harmonic. Build the focused package closure
from `CSTAM-Tunibot/cstam-pkg`, then launch the integrated system:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to cstam_phase1
source install/setup.bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

Normal mode spawns at the semantic dock's registered world pose, approximately
(7.59, 7.80, -0.522). Mapping mode (`slam:=true`) uses (11.4, 6.95, 0).
The raw `andino_gz restaurant.launch.py` remains a simulation-only utility
with legacy spawn defaults; use `cstam_phase1` for the accepted workflow.

`models/restaurant/meshes/restaurant.obj` provides the authored visual scene.
Sweet Home centimetres/Y-up are converted in its model SDF. The OBJ is visual
only: primitive collision boxes in `models/restaurant_collision/model.sdf`
represent walls, tables, chair seats and backs. The stable world ground plane
provides contact physics. Preserve the authored collision alignment; globally
translating the full multi-floor scene down corrupts first-floor sensor geometry.
Do not regenerate collision assets or the accepted SLAM map merely for a demo.

The Harmonic restaurant GUI configuration uses `gz-gui` tags and a restaurant
camera view, with no GUI velocity publisher. The world retains the required
Sensors and Contact systems. Legacy kinematic actor visuals can emit invalid
`__default__` mesh warnings; elevator/pedestrian behavior is outside Phase 1.
The robot, static restaurant geometry and real sensor pipeline are the tested
first-floor deliverable. Original texture material files were not supplied;
the neutral fallback material is used.

CSTAM lives in `cstam_robot`. Its final Phase 1 interfaces are `/cmd_vel`,
`/odom`, `/tf`, `/joint_states`, `/lidar/points` and RGB-D camera topics. The
Phase 1 filter produces `/lidar/points_filtered`, `/lidar/points_clearing` and
`/scan_navigation`. Normal operation uses the saved map and AMCL; mapping uses
SLAM Toolbox. Never run manual teleop or `mapping_route` during normal Nav2
acceptance or delivery.

See repository-root README, PHASE1_ARCHITECTURE, PHASE1_DEMO_GUIDE and
PHASE1_REPORT for accepted semantics, exact commands and measured limitations.
