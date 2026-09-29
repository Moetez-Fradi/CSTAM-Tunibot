# CSTAM Phase 1 Demo Guide

This is the short recording script. It uses the first floor only.

## 1. Build

```bash
cd /home/youssef/Desktop/CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-up-to cstam_phase1
source install/setup.bash
```

## 2. Start the normal runtime

```bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

Show Gazebo with CSTAM and RViz with the saved map, TF, 3D point cloud,
projected navigation scan, and Nav2
costmaps. Lifecycle state alone is not the readiness signal. Continue only
after the smoke test below confirms `/amcl_pose`, `map -> odom`,
`map -> base_footprint`, both costmaps, and both Nav2 action servers.

## 3. Show health checks

In another terminal:

```bash
cd /home/youssef/Desktop/CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
source install/setup.bash
bash install/cstam_phase1/share/cstam_phase1/scripts/phase1_smoke_test.sh
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
ros2 topic info /lidar/points -v
ros2 topic echo /scan_navigation --once
```

The smoke test must report all critical checks as PASS. If the map has not
been regenerated and validated for the current restaurant geometry, stop the
recording at this point and label the demonstration as infrastructure-only.

The expected successful summary is `PASS=21 FAIL=0`. The script has bounded
timeouts and fails if automatic localization does not complete; a manual RViz
2D Pose Estimate is not part of the normal startup procedure.

## 4. Submit a delivery

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String "{data: table_1}"
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
```

Show the task manager status changing through pickup, customer, delivery
complete, return-to-dock, and finally `IDLE`. Show the Nav2 path and CSTAM's
physical motion in Gazebo. The request must be accepted and the robot must
actually move; do not use a manually dragged pose.

## 5. Manual return-to-dock demonstration

```bash
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

Then check:

```bash
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
```

## Mapping demonstration

Start mapping instead of normal operation:

```bash
ros2 launch cstam_phase1 phase1.launch.py slam:=true rviz:=true
```

In another terminal, run the real-physics helper:

```bash
ros2 run cstam_phase1 mapping_route --ros-args \
  -p linear_speed:=0.15 -p angular_speed:=0.18 \
  -p leg_length:=8.0 -p legs:=8 \
  -p safety_distance:=0.55 -p auto_avoid:=true
```

Stop the helper with `Ctrl+C`; it commands zero velocity on shutdown. Save a
map only after visually confirming that walls and free space correlate with
Gazebo:

```bash
ros2 run nav2_map_server map_saver_cli -f /tmp/restaurant_phase1_3d
```

The checked-in map is a real 3-D-derived SLAM candidate. It has been inspected
quantitatively and visually, but raw long-route Nav2 acceptance is still
pending; do not present delivery or docking as verified until the dining-area
controller failure is resolved.
