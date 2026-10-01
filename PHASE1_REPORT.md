# CSTAM Tunibot — final Phase 1 acceptance report

Date: 2026-10-01 · Branch: **Youssef** · First floor only.

## Result

**Mandatory tested simulation workflows are VERIFIED:** real mapping/localization,
three independent kitchen successes, raw navigation 4/4, two fresh full deliveries,
FIFO queue, invalid/duplicate/empty rejection, autonomous station return and manual
return from table 1. No recorded non-ground contacts in accepted tests.

This supersedes earlier failure reports and the stop-before-delivery checkpoint.
The accepted map and calibrated robot are preserved. No reset, restore, main
modification, commit or push was performed. Detailed evidence is in the intentional
JSON records under `docs/`; runtime logs remain outside Git.

Docking means autonomous arrival at the station pose. It does not mean physical
charger alignment, charging/battery simulation, or physical pickup/unloading.

## 1–42. Acceptance summary

| # | Item | Status | Evidence / limit |
|---|---|---|---|
| 1 | BUILD | VERIFIED | Five focused packages built; independent copied workspace also built. |
| 2 | TESTS | VERIFIED | Eleven tests; zero failures, errors or skips in both workspaces. |
| 3 | SMOKE | VERIFIED | Normal-mode PASS=22 FAIL=0 on fresh delivery and GUI launches. |
| 4 | GAZEBO | VERIFIED | Real robot dynamics, restaurant collision assets and contact streams. |
| 5 | 3D LIDAR | VERIFIED | Real organized PointCloud2, 16 × 360, lidar_3d_link. |
| 6 | FILTERED CLOUD | VERIFIED | Geometric self-filter retains scene returns; separate clearing product. |
| 7 | SCAN_NAVIGATION | VERIFIED | 360-bin real projection; AMCL/SLAM input. |
| 8 | SLAM | VERIFIED | Active SLAM Toolbox, real motion, live grid growth. |
| 9 | FINAL MAP | VERIFIED | Accepted 345 × 486, 0.05 m map used throughout navigation/application trials. |
| 10 | MAP SAVING | VERIFIED | Separate real demo PGM/YAML saved, 322 × 444; accepted map unchanged. |
| 11 | AMCL STARTUP | VERIFIED | Automatic dock initialization acknowledged without manual initial pose. |
| 12 | AMCL STABILITY | VERIFIED | Centred drive reference; three kitchen and application sequences completed. Finite localization errors remain. |
| 13 | TF | VERIFIED | map→odom→base_drive→base_footprint→base_link→lidar_3d_link. |
| 14 | GLOBAL COSTMAP | VERIFIED | Live static + inflation; no transient marking. |
| 15 | LOCAL VOXEL COSTMAP | VERIFIED | Rolling marking/clearing streams; removed physical obstacle cleared 3→0 cells. |
| 16 | FOOTPRINT | VERIFIED | Physical 0.596×0.455 m; configured 0.66×0.54 m, padded 0.68×0.56 m. |
| 17 | PLANNER | VERIFIED | Direct ComputePath status 4/error0; NavFn preserved. Smac comparison recorded separately. |
| 18 | CONTROLLER | VERIFIED | Rotation Shim + DWB, actual full-footprint checks and angular progress. |
| 19 | KITCHEN RELIABILITY RUN 1 | VERIFIED | SUCCEEDED, 172.18 s, four recoveries, 0.118 m / 0.199 rad physical error. |
| 20 | KITCHEN RELIABILITY RUN 2 | VERIFIED | SUCCEEDED, 118.01 s, no recoveries, 0.117 m / 0.181 rad. |
| 21 | KITCHEN RELIABILITY RUN 3 | VERIFIED | SUCCEEDED, 119.81 s, no recoveries, 0.154 m / 0.193 rad. |
| 22 | NAV TEST 1 — SHORT | VERIFIED | SUCCEEDED, 31.45 s, 0 recoveries. |
| 23 | NAV TEST 2 — LONG | VERIFIED | Dock→kitchen, three clean runs above. |
| 24 | NAV TEST 3 — OBSTACLE/TURN | VERIFIED | Short-point→table 1 SUCCEEDED, 161.06 s, one recovery. |
| 25 | NAV TEST 4 — PASSAGE | VERIFIED | table 1→dock SUCCEEDED, 66.60 s, one recovery. |
| 26 | DELIVERY RUN 1 | VERIFIED | 349.943 s, three SUCCEEDED actions, physical dock arrival and IDLE. |
| 27 | DELIVERY RUN 2 | VERIFIED | Independent fresh launch; 332.553 s, three SUCCEEDED actions, IDLE. |
| 28 | QUEUE TEST | VERIFIED | FIFO table 1/table 2, five new successful goals, max active 1, empty queue at IDLE. |
| 29 | INVALID REQUEST TEST | VERIFIED | Unknown, empty and both active/queued duplicates rejected without corruption. |
| 30 | AUTO DOCK | VERIFIED | Physical station returns after both deliveries and queue; 0.176–0.292 m error. |
| 31 | MANUAL DOCK | VERIFIED | From real table 1 arrival: accepted service, SUCCEEDED action, 55.908 s, IDLE. |
| 32 | MAPPING DEMO | VERIFIED | Physical turn/translation and live map growth; save demonstrated. |
| 33 | RVIZ | VERIFIED | Normal/mapping displays launched; normal Global Status OK; Gazebo restaurant GUI corrected. |
| 34 | ARCHITECTURE DIAGRAM | VERIFIED | Mermaid + Graphviz source and inspected SVG export. |
| 35 | TEST DOCUMENTATION | VERIFIED | Commands, purposes, expected/actual results and statuses in docs/PHASE1_TESTS.md. |
| 36 | README | VERIFIED | Focused build, mode switch, requests, docking, smoke, structure and limits. |
| 37 | GAZEBO PACKAGE COMPLETENESS | VERIFIED | Required static restaurant, robot, sensors, bridge/launch/config assets resolve from source copy. |
| 38 | PORTABILITY | PARTIAL | Copied workspace build/tests/runtime and focused rosdep pass on this host; pristine second machine NOT TESTED. |
| 39 | EXACT DEMO COMMANDS | VERIFIED | Reproducible guide and commands below; <=3 minute recording sequence prepared. |
| 40 | REMAINING LIMITATIONS | VERIFIED | Explicit quantitative limits below; video/publication still operator actions. |
| 41 | FILES CHANGED | VERIFIED | Source/config/tests/docs listed in final Git inventory below. |
| 42 | GIT STATUS | VERIFIED | Youssef; changes preserved/uncommitted; generated index cleanup retained; no main change. |

## Physical calibration and localization diagnosis

Gazebo DiffDrive controls left_front, left_rear, right_front and right_rear
wheel joints, radius 0.075 m. Physical track is 0.41 m; effective skid-steer
separation is **0.60 m**, derived from real angular calibration rather than
copying the wheel-centre spacing. Chassis clearance correction is retained.

| Motion | Wheel odometry | Gazebo physical | Discrepancy |
|---|---:|---:|---|
| Straight | 2.011 m | 2.010 m | ~0.05% distance difference |
| 90° turn | 91.02° | 89.29° | 1.73°, ~1.94% relative to physical turn |
| 180° turn | 181.09° | 177.41° | 3.68°, ~2.07% |
| Arc chord / yaw | 0.707 m / 64.03° | 0.676 m / 60.91° | 0.031 m / 3.12° |

The old drive-reference translation -0.18 m was incorrect. The four-wheel
DiffDrive's virtual skid centre is not displaced because front encoders are
selected. Six matched alternating turns gave maximum localization translation
error 0.972 m at the offset reference versus **0.177 m at zero translation**.
A historical failed delivery put AMCL about seven metres away from the actual
robot still near kitchen; its later zero path was a wrong localized start,
not proof of contact trapping. The contact stream recorded no furniture contact.

AMCL alpha1 remains 0.005; other motion alphas 0.10. World/map registration
(11.22,6.95,0) is spawn/diagnostic metadata only. Ground truth is never fed to
AMCL/TF. Approximate dynamic diagnostic samples can lag; settled physical poses
define arrival errors. These calibration measurements are prior preserved
engineering evidence, not new controlled cmd_vel tests in this delivery turn.

## Path, costmap and controller decisions

Global static map + inflation avoids stale sensor marks at old targets. Local
VoxelLayer uses filtered marking heights 0.04–1.27 m; separate free-space clearing
rays cover the floor/no-return measurements. Seven 0.20 m voxel slices cover
1.40 m, above the 1.245 m robot. The physical obstacle experiment recorded
**0→3→0** marked cells before insertion, during insertion and after removal.
No generic close-range scene deletion was substituted for geometric self-filtering.

The padded footprint's inscribed radius is approximately 0.28 m and maximum
circumscribed radius 0.456 m. Inflation is **0.51 m** globally and locally,
scaling 5.0, providing about one 0.05 m map-cell allowance beyond that radius.
Inflation grades proximity; the controller still checks the full rectangle.

Interior dock→kitchen static-map cross-sections were ray-cast normal to a
±0.25 m path tangent, excluding 1 m at either endpoint. The narrowest sampled
section was **1.575 m**, near map
(-5.850,4.089), with 0.625/0.950 m side distances. This exceeds the 0.68 m
padded length and 0.912 m all-heading circumscribed diameter. It is a static
grid measurement, not a complete CAD survey. Real executed route contact
audit is the independent physical check.

DWB maximum linear/angular speeds are 0.15 m/s and 0.30 rad/s; acceleration
0.25 m/s² and 0.40 rad/s²; deceleration -0.30 and -0.40. Samples 10×20,
horizon 1.5 s, linear/angular granularity 0.05 m/0.025 rad. Goal xy/yaw tolerance
0.25 m/0.20 rad. Pose progress counts 0.20 m or 0.50 rad within 15 s.
Rotation Shim engage/disengage 0.785/0.3925 rad; turn 0.25 rad/s.
Critics: RotateToGoal 20, Oscillation, ObstacleFootprint 0.03, BaseObstacle 0.03,
GoalAlign 20, PathAlign 24, PathDist 24, GoalDist 20. Full-footprint critic retained.

Matched kitchen→table 1 comparison at corrected TF, same environment:

| Controller | Actual result | Duration | Recoveries | Non-ground contacts |
|---|---|---:|---:|---:|
| DWB | SUCCEEDED | 192.76 s | 6 | 0 |
| Rotation Shim + DWB | SUCCEEDED | 138.53 s | 3 | 0 |
| RPP | SUCCEEDED | 165.75 s | 4 | 0 |

Initial heading mismatch was 2.60 rad. Shim handles large initial alignment;
angular progress avoids false translation-only timeouts. A hypothesized small
angular-command deadband was disproved by real physical rotation. The final
profile was selected through these measurements and then passed the raw and
application gates. No MPPI or arbitrary waypoint bypass was introduced.

### Planner and smoothing comparison

A* and Dijkstra both previously passed direct planning. Final NavFn Dijkstra
is retained because it passed three clean kitchen starts, raw4/4 and complete
application routes. Smac2D was tested from the same clean dock with the same
map/AMCL/footprint/controller and stock replanning/recovery tree. Its configured
cost multiplier 2.0 follows the documented cost-aware search setting:
[official Nav2 Smac2D documentation](https://ros-navigation.github.io/mkdocs.nav2.org/rolling/configuration_and_development/configuration_guide/planners_plugins/smac/smac_2d/configuring_smac_2d/).
Installed Jazzy plugin availability and loaded parameters were checked locally.

| Direct planner | Path length | Poses | Minimum lethal-cell-centre clearance | Maximum adjacent direction change |
|---|---:|---:|---:|---:|
| NavFn | 13.419 m | 535 | 0.461 m | 0.824 rad |
| Smac2D | 11.805 m | 232 | 0.461 m | 0.118 rad |

Smac execution: **VERIFIED SUCCEEDED**, 123.78 s, zero recoveries,
zero non-ground contacts, physical position/yaw error
0.216 m / 0.039 rad. One
Smac route does not establish its full delivery/queue reliability; no production
switch was made. An initial one-shot-tree pilot is excluded from this comparison
because it omitted the baseline's replanning/recovery.

SimpleSmoother generation succeeded with collision checking: length 13.419→13.358 m,
maximum adjacent heading change 0.824→0.129 rad, minimum centre clearance unchanged
at 0.461 m. **Execution FAILED** in the controlled replanning tree after 3.66 s:
smoother_server rejected a collision at map (-3.604,0.918), heading -1.3855 rad.
Dock fits only selected orientations; changing tangent orientation during
smoothing makes the rectangular collision check relevant. No clearance checks
were disabled. Additional smoothing is not adopted. See the comparison JSON
and [path overlay](docs/phase1_paths.png).

## Semantic location validation

All rows passed exact padded rectangle / whole costmap cell intersection checks
at the configured yaw: zero lethal and unknown intersections. All are in one
NavFn known traversable component. This is not an arbitrary-heading connectivity
proof: dock/table 3 fail the more conservative all-heading circle erosion.

| Location | Map x/y/yaw | OccupancyGrid cost | Nearest lethal cell centre | Footprint blocked cells |
|---|---|---:|---:|---:|
| dock | -3.63 / 0.85 / -0.522 | 39 | 0.461 m | 0 |
| kitchen | 0.02 / 9.27 / 1.049 | 0 | 1.050 m | 0 |
| table 1 | -6.36 / 1.32 / -0.522 | 0 | 0.632 m | 0 |
| table 2 | -5.60 / 1.96 / 0.0 | 0 | 0.600 m | 0 |
| table 3 | -3.55 / 1.02 / 2.619 | 46 | 0.427 m | 0 |

Costs above use the published 0–100 encoding, not raw 0–255 Nav2 costs. Table2
was moved from the old tabletop-overlapping point to a valid serving-side point;
dock was adjusted to its registered footprint-safe station pose. Kitchen was
not moved to hide a bad route. The accepted map remained unchanged in this turn.
Current-profile real delivery acceptance covers table 1/table 2; a new table 3
application delivery was **NOT TESTED**.

## Navigation and application measurements

Full navigation, physical arrival/odometry, path-error, recovery and contact data:
[historical navigation acceptance checkpoint](docs/phase1_navigation_checkpoint.json).
The checkpoint's NOT TESTED application entries describe the earlier pause and
are superseded by [application acceptance](docs/phase1_application_acceptance.json).

| Application test | Duration | Odom travel | New successful Nav2 goals | Dock position/yaw error |
|---|---:|---:|---:|---|
| Fresh delivery 1 | 349.943 s | 27.831 m | 3 | 0.176 m / 0.094 rad |
| Fresh delivery 2 | 332.553 s | 27.733 m | 3 | 0.257 m / 0.081 rad |
| FIFO table 1 then table 2 | 587.653 s | 48.531 m | 5 | 0.187 m / 0.047 rad |
| Extra fresh GUI delivery | 766.719 s | 27.513 m | 3 | 0.292 m / 0.127 rad |
| Manual dock from table 1 | 55.908 s | 2.762 m | 1 | 0.251 m / 0.076 rad |

Each ended IDLE with an empty queue, last real action status 4 and maximum one
active goal. Contact sensors delivered real ground-contact messages; nonground
counts were zero. Separate physical stage snapshots prove kitchen/table/dock
arrival, rather than inferring arrival solely from manager status strings.
Duplicates and malformed requests were rejected while table 1 remained active
and table 2 remained queued. The manager serves all queued customers before its
final automatic station return. Manual return began from an idle real table 1
arrival; cancellation/goal-ack races are covered by regression tests.

## Mapping, visualization and evaluator checks

Fresh SLAM mapping published 255 clouds/scans and 87 grid updates during the
measured 180-second observer window. Known cells 813→19,076, occupied 3→440,
map width 198→322; odometry path 1.047 m. World start (11.4,6.95,0) and settled
end (11.5678,8.28029,1.50292) demonstrate physical translation/turning.
Map saver successfully wrote a separate 322×444 pair. Accepted 345×486 map stays
unchanged. See [mapping acceptance](docs/phase1_mapping_acceptance.json).

Normal and mapping RViz configurations show their appropriate maps, robot,
scan and filtered 3D cloud; normal also includes global/local costmaps and paths.
The Harmonic MinimalScene field of view is configured in degrees, verified
against [the official plugin source](https://raw.githubusercontent.com/gazebosim/gz-gui/gz-gui8/src/plugins/minimal_scene/MinimalScene.cc).
The old inherited ignition-gui tag configuration displayed obsolete giant
panels in Harmonic. A restaurant-specific gz-gui configuration now provides
an in-room camera and clean scene, without a GUI velocity publisher. Original
generic GUI configuration remains available for other launch workflows.

Five-package source closure was copied into a separate empty workspace,
built and tested using only the baseROS installation plus its own overlay.
Its normal GUI launch passed 22 health checks. Assets resolved from that copy,
not from the original workspace. Source runtime path audit found no user-home
or temporary runtime dependencies in the focused launch/config/code/assets.
The initial host rosdep check was unavailable. A temporary source list and
updated user cache enabled the check; it found an invalid `ament_python`
buildtool dependency. The manifest now declares `python3-setuptools`, retaining
`ament_python` solely as the build-type export, consistent with the installed
Jazzy Python-package generator. `rosdep check` reports all system dependencies
satisfied for the focused source closure. No system rosdep source configuration
was changed. A pristine machine dependency installation is still NOT TESTED.
README documents initialization and focused installation for evaluators.

Normal-mode GUI evidence: [Gazebo](docs/phase1_gazebo.png) and
[RViz](docs/phase1_rviz.png), captured from only the test application windows.
These are startup/short-test views, not fabricated mission-completion footage.

The final bounded one-leg GUI mapping command also completed normally: 71 map
updates, known cells 813→18,851, 1.007 m odometry path, physical world end
(11.5419,7.8759,1.50105), and a saved 323×423 map. Production helper stopped
after its turn/1m leg, with zero non-ground contacts. The temporary observer
captured final metrics before a redundant SIGINT shutdown error; the production
helper and map saver exited normally.

Final original and copied workspace build: 5 packages. Tests: 11 passed,
zero failures/errors/skips. Fresh final copied-workspace normal startup:
PASS=22 FAIL=0. All owned test processes were shut down before final inventory.

## Exact operator commands

```bash
cd /home/youssef/Desktop/CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to cstam_phase1
source install/setup.bash
export FASTDDS_DEFAULT_PROFILES_FILE="$(ros2 pkg prefix --share cstam_phase1)/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_DEFAULT_PROFILES_FILE"
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

In a second similarly sourced terminal:

```bash
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase1_smoke_test.sh"
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
ros2 topic echo /delivery/status
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
# Publish while busy to queue another request:
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_2}'
# Separately, for a deliberate manual station return:
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

Separate mode, after stopping normal processes and all helpers:

```bash
ros2 launch cstam_phase1 phase1.launch.py slam:=true rviz:=true
# Second sourced terminal, sole mapping command publisher:
ros2 run cstam_phase1 mapping_route --ros-args \
  -p linear_speed:=0.08 -p angular_speed:=0.15 \
  -p leg_length:=1.0 -p legs:=1 -p safety_distance:=0.55
ros2 run nav2_map_server map_saver_cli -f /tmp/cstam_demo \
  --ros-args -p save_map_timeout:=15.0
```

## Remaining limits / submission actions

- No precise charger connector alignment, battery behavior, elevator, second
  floor or physical food loading/unloading; those are outside this Phase1.
- Simulation-only acceptance. Sparse 16-ring sensing, skid slip, map discretization
  and finite localization errors limit generalization to hardware/arbitrary routes.
- Dock/table 3 are orientation-constrained. Do not force arbitrary spins there.
  Kitchen run 1 had one sampled static-global lethal cell centre under the padded
  footprint while departing; local footprint samples and physical contacts were clear.
- Recoveries remain in some accepted routes. Finite successful trials are not a
  universal collision-avoidance guarantee. Physical pose tolerances are roughly
  decimetres, not charger precision; dock error reached 0.292 m in the extra GUI run.
- GUI rendering can reduce simulation speed. Two full deliveries were accepted in
  headless mode, and an extra fresh GUI-enabled delivery succeeded in 766.719 s.
  Gazebo/RViz windows were minimized during that longer mission to reduce rendering
  load; visible startup and a separate 10.55 s short navigation were verified.
  Headless mode uses the same autonomy profile.
- Legacy actor visuals emit invalid `__default__` mesh warnings; original texture
  materials are missing. Static restaurant/robot/sensors load. Actors/elevator are
  outside the accepted first-floor workflow.
- Pristine second machine dependency installation NOT TESTED. Publication access,
  final source commit/push, video recording/upload and submission form remain
  operator actions. No current visibility or submission deadline is inferred
  from historical reports.

An extra GUI restart was blocked by health (PASS=10 FAIL=12, missing robot
odometry/cloud/TF) after the preceding simulator shutdown overlapped the new
spawn acknowledgement. No delivery request was sent in that invalid startup.
The test was stopped and retried after an empty process inventory; this is
why full process cleanup is required between modes.

## Files and Git inventory

Core prior changes remain preserved: point-cloud filtering/clearing, health
checker, task manager, Nav2 launch/remaps/config, centred TF/spawn metadata,
semantic locations, robot drivetrain/contact/joint-state changes, manifests,
RViz and regression tests. This final delivery continuation added acceptance
records, planner/smoother comparison, aisle/path artifacts, corrected restaurant
GUI configuration, and updated architecture, report, tests, README/demo/video/
submission/handoff documentation. The generated root build/install/log index
cleanup is retained without removing physical ignored build outputs.

The exact final Git commands and outputs are appended after validation below.

### Final Git command output

Captured after validation. Embedding this snapshot changes only this report's
line count. The generated root artifacts were removed from the index in the
prior cleanup; their ignored physical files were preserved.

```text
$ git branch --show-current
Youssef
```

```text
$ git status
On branch Youssef
Your branch is up to date with 'origin/Youssef'.

Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
	deleted:    build/.built_by
	deleted:    build/COLCON_IGNORE
	deleted:    build/andino_gz/colcon_build.rc
	deleted:    install/.colcon_install_layout
	deleted:    install/COLCON_IGNORE
	deleted:    install/_local_setup_util_ps1.py
	deleted:    install/_local_setup_util_sh.py
	deleted:    install/andino_gz/share/andino_gz/package.bash
	deleted:    install/andino_gz/share/andino_gz/package.dsv
	deleted:    install/andino_gz/share/andino_gz/package.ps1
	deleted:    install/andino_gz/share/andino_gz/package.sh
	deleted:    install/andino_gz/share/andino_gz/package.zsh
	deleted:    install/andino_gz/share/colcon-core/packages/andino_gz
	deleted:    install/local_setup.bash
	deleted:    install/local_setup.ps1
	deleted:    install/local_setup.sh
	deleted:    install/local_setup.zsh
	deleted:    install/setup.bash
	deleted:    install/setup.ps1
	deleted:    install/setup.sh
	deleted:    install/setup.zsh
	deleted:    log/COLCON_IGNORE
	deleted:    log/build_2026-09-18_10-15-05/events.log
	deleted:    log/build_2026-09-18_10-15-05/logger_all.log
	deleted:    log/latest
	deleted:    log/latest_build

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   .gitignore
	modified:   PHASE1_ARCHITECTURE.md
	modified:   PHASE1_DEMO_GUIDE.md
	modified:   PHASE1_REPORT.md
	modified:   cstam-pkg/src/andino_gz/andino_gz/RESTAURANT_SIM.md
	modified:   cstam-pkg/src/andino_gz/andino_gz/launch/restaurant.launch.py
	modified:   cstam-pkg/src/andino_gz/andino_gz/package.xml
	modified:   cstam-pkg/src/cstam_phase1/config/nav2_params.yaml
	modified:   cstam-pkg/src/cstam_phase1/cstam_phase1/delivery_task_manager.py
	modified:   cstam-pkg/src/cstam_phase1/cstam_phase1/pointcloud_navigation_filter.py
	modified:   cstam-pkg/src/cstam_phase1/cstam_phase1/startup_health_check.py
	modified:   cstam-pkg/src/cstam_phase1/launch/nav2_phase1.launch.py
	modified:   cstam-pkg/src/cstam_phase1/launch/phase1.launch.py
	modified:   cstam-pkg/src/cstam_phase1/maps/restaurant/locations.yaml
	modified:   cstam-pkg/src/cstam_phase1/package.xml
	modified:   cstam-pkg/src/cstam_phase1/rviz/cstam_phase1.rviz
	modified:   cstam-pkg/src/cstam_robot/config/environment_bridge.yaml
	modified:   cstam-pkg/src/cstam_robot/urdf/cstam_robot.urdf.xacro
	modified:   cstam-pkg/src/cstam_robot/urdf/cstam_robot_gazebo.xacro
	modified:   cstam-pkg/src/cstam_robot/urdf/cstam_robot_sensors.xacro

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	PHASE1_HANDOFF.md
	PHASE1_SUBMISSION_CHECKLIST.md
	PHASE1_VIDEO_SCRIPT.md
	README.md
	cstam-pkg/src/andino_gz/andino_gz/config_gui/restaurant.config
	cstam-pkg/src/cstam_phase1/maps/restaurant/world_alignment.yaml
	cstam-pkg/src/cstam_phase1/rviz/cstam_mapping.rviz
	cstam-pkg/src/cstam_phase1/test/test_clearing_projection.py
	cstam-pkg/src/cstam_phase1/test/test_controller_contract.py
	cstam-pkg/src/cstam_phase1/test/test_delivery_control.py
	cstam-pkg/src/cstam_phase1/test/test_geometry.py
	cstam-pkg/src/cstam_phase1/test/test_restaurant_gui.py
	docs/

```

```text
$ git diff --stat
 .gitignore                                         |  18 +-
 PHASE1_ARCHITECTURE.md                             | 178 +++---
 PHASE1_DEMO_GUIDE.md                               | 138 +++--
 PHASE1_REPORT.md                                   | 688 ++++++++++-----------
 .../src/andino_gz/andino_gz/RESTAURANT_SIM.md      | 126 ++--
 .../andino_gz/launch/restaurant.launch.py          |   1 +
 cstam-pkg/src/andino_gz/andino_gz/package.xml      |   2 +-
 cstam-pkg/src/cstam_phase1/config/nav2_params.yaml | 111 ++--
 .../cstam_phase1/delivery_task_manager.py          |  31 +-
 .../cstam_phase1/pointcloud_navigation_filter.py   |  55 +-
 .../cstam_phase1/startup_health_check.py           |  23 +-
 .../src/cstam_phase1/launch/nav2_phase1.launch.py  |  12 +-
 cstam-pkg/src/cstam_phase1/launch/phase1.launch.py |  57 +-
 .../cstam_phase1/maps/restaurant/locations.yaml    |  10 +-
 cstam-pkg/src/cstam_phase1/package.xml             |  14 +-
 cstam-pkg/src/cstam_phase1/rviz/cstam_phase1.rviz  |  53 +-
 .../src/cstam_robot/config/environment_bridge.yaml |   6 +
 .../src/cstam_robot/urdf/cstam_robot.urdf.xacro    |   5 +-
 .../src/cstam_robot/urdf/cstam_robot_gazebo.xacro  |  41 +-
 .../src/cstam_robot/urdf/cstam_robot_sensors.xacro |   4 +-
 20 files changed, 876 insertions(+), 697 deletions(-)
```

```text
$ git diff --check
(no output; exit 0)
```

```text
$ git diff --cached --check
(no output; exit 0)
```

```text
$ git diff --cached --stat
 build/.built_by                                    |    1 -
 build/COLCON_IGNORE                                |    0
 build/andino_gz/colcon_build.rc                    |    1 -
 install/.colcon_install_layout                     |    1 -
 install/COLCON_IGNORE                              |    0
 install/_local_setup_util_ps1.py                   |  406 --
 install/_local_setup_util_sh.py                    |  406 --
 install/andino_gz/share/andino_gz/package.bash     |   31 -
 install/andino_gz/share/andino_gz/package.dsv      |    0
 install/andino_gz/share/andino_gz/package.ps1      |  108 -
 install/andino_gz/share/andino_gz/package.sh       |   52 -
 install/andino_gz/share/andino_gz/package.zsh      |   42 -
 .../andino_gz/share/colcon-core/packages/andino_gz |    1 -
 install/local_setup.bash                           |  121 -
 install/local_setup.ps1                            |   55 -
 install/local_setup.sh                             |  137 -
 install/local_setup.zsh                            |  134 -
 install/setup.bash                                 |   31 -
 install/setup.ps1                                  |   30 -
 install/setup.sh                                   |   45 -
 install/setup.zsh                                  |   31 -
 log/COLCON_IGNORE                                  |    0
 log/build_2026-09-18_10-15-05/events.log           |   49 -
 log/build_2026-09-18_10-15-05/logger_all.log       | 3878 --------------------
 log/latest                                         |    1 -
 log/latest_build                                   |    1 -
 26 files changed, 5562 deletions(-)
```

```text
$ git ls-files --others --exclude-standard
PHASE1_HANDOFF.md
PHASE1_SUBMISSION_CHECKLIST.md
PHASE1_VIDEO_SCRIPT.md
README.md
cstam-pkg/src/andino_gz/andino_gz/config_gui/restaurant.config
cstam-pkg/src/cstam_phase1/maps/restaurant/world_alignment.yaml
cstam-pkg/src/cstam_phase1/rviz/cstam_mapping.rviz
cstam-pkg/src/cstam_phase1/test/test_clearing_projection.py
cstam-pkg/src/cstam_phase1/test/test_controller_contract.py
cstam-pkg/src/cstam_phase1/test/test_delivery_control.py
cstam-pkg/src/cstam_phase1/test/test_geometry.py
cstam-pkg/src/cstam_phase1/test/test_restaurant_gui.py
docs/PHASE1_TESTS.md
docs/phase1_aisle_measurement.json
docs/phase1_application_acceptance.json
docs/phase1_architecture.dot
docs/phase1_architecture.mmd
docs/phase1_architecture.png
docs/phase1_architecture.svg
docs/phase1_final_validation.json
docs/phase1_gazebo.png
docs/phase1_gui_acceptance.json
docs/phase1_mapping_acceptance.json
docs/phase1_navigation_checkpoint.json
docs/phase1_paths.png
docs/phase1_planner_comparison.json
docs/phase1_rviz.png
```

```text
$ git rev-parse HEAD main
b5b6ea97a8b23c49213ad4a354850044af2bcd13
7eab72647befaad3d221d5f03d7228e7e67a871c
```
