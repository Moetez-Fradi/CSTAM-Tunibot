# CSTAM Robot

Standalone ROS 2 Jazzy and Gazebo Harmonic robot package for a compact CSTAM autonomous service/delivery robot.

This project is intentionally independent of the original `Delivery-Robot-ROS` repository and of any CSTAM environment/world package. It contains a portable four-wheel robot description, a small isolated Gazebo test world, sensor bridges, and RViz configuration.

## Current robot

- Four-wheel skid-steer drivetrain: two continuous wheels per side, commanded by Gazebo Harmonic DiffDrive.
- Primitive visual and collision geometry; no dependency on the original SolidWorks mesh assembly.
- Approximate footprint: 0.52 m long by 0.46 m wide.
- Approximate total modeled mass: 15.2 kg before payload; this is a simulation assumption, not a measured mechanical value.
- Overall height: approximately 1.15 m including the sensor mast and camera.
- Wheel radius: 0.075 m; wheel width: 0.045 m; wheel separation: 0.41 m.
- Three supported shelves, ordered top-to-bottom as Shelf 1 at 0.74 m, Shelf 2 at 0.54 m, and Shelf 3 at 0.34 m above the `base_link` origin.
- LiDAR height: 0.27 m above the floor, front-mounted below the shelves.
- RGB-D camera height: 1.12 m above the floor, facing forward above the display.
- IMU frame height: 0.72 m above the floor.

The chassis uses a simple box collision volume and each wheel uses a cylinder collision volume. The three shelves, rear panel, mast, display, and sensor housings also use primitive collision shapes so the robot remains suitable for later Nav2 footprint tuning.

## Package layout

```text
cstam_robot/
├── CMakeLists.txt
├── package.xml
├── README.md
├── config/
├── launch/
│   ├── display.launch.py
│   └── gazebo_test.launch.py
├── meshes/
├── rviz/
│   └── cstam_robot.rviz
├── urdf/
│   ├── cstam_robot.urdf.xacro
│   ├── cstam_robot_body.xacro
│   ├── cstam_robot_core.xacro
│   ├── cstam_robot_drivetrain.xacro
│   ├── cstam_robot_gazebo.xacro
│   ├── cstam_robot_sensors.xacro
│   ├── inertial_macros.xacro
│   └── materials.xacro
└── worlds/
    └── test_world.sdf
```

## Build and run

From a ROS 2 workspace containing this package:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select cstam_robot
source install/setup.bash
ros2 launch cstam_robot gazebo_test.launch.py
```

For headless Gazebo rendering (useful on machines without a desktop display):

```bash
ros2 launch cstam_robot gazebo_test.launch.py headless:=true
```

To start the isolated test world with RViz:

```bash
ros2 launch cstam_robot gazebo_test.launch.py rviz:=true
```

To view the model without Gazebo:

```bash
ros2 launch cstam_robot display.launch.py
```

## Interfaces

The test launch exposes these standard ROS interfaces:

| Interface | Type | Direction |
|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | ROS to Gazebo |
| `/odom` | `nav_msgs/msg/Odometry` | Gazebo to ROS |
| `/scan` | `sensor_msgs/msg/LaserScan` | Gazebo to ROS |
| `/tf` | `tf2_msgs/msg/TFMessage` | Gazebo and robot_state_publisher to ROS |
| `/camera/rgbd/image` | `sensor_msgs/msg/Image` | Gazebo to ROS |
| `/camera/rgbd/depth_image` | `sensor_msgs/msg/Image` | Gazebo to ROS |
| `/camera/rgbd/camera_info` | `sensor_msgs/msg/CameraInfo` | Gazebo to ROS |

The six ultrasonic elements are mounting points and TF frames only. They intentionally do not publish synthetic range data.

## TF tree

```text
odom
└── base_footprint
    └── base_link
        ├── rear_panel_link
        │   ├── shelf_1_link
        │   ├── shelf_2_link
        │   └── shelf_3_link
        ├── left_shelf_support_link
        ├── right_shelf_support_link
        ├── left_front_wheel_link
        ├── left_rear_wheel_link
        ├── right_front_wheel_link
        ├── right_rear_wheel_link
        ├── lidar_link
        ├── sensor_mast_link
        │   ├── display_link
        │   └── camera_link
        │       └── camera_optical_frame
        ├── imu_link
        └── ultrasonic mounting frames
```

The `base_link` origin is at the chassis center. `base_footprint` is on the ground below it. The camera optical frame follows the usual ROS optical-frame convention.

## Xacro parameters

The main file accepts these arguments without requiring changes to the supporting Xacros:

```bash
xacro urdf/cstam_robot.urdf.xacro \
  robot_length:=0.55 robot_width:=0.48 \
  wheel_radius:=0.08 wheel_separation:=0.42 \
  lidar_height:=0.27 camera_height:=1.12
```

The current launch files use the defaults. The supporting files separate the base, drivetrain, body, sensors, and Gazebo configuration so each part can be adjusted independently later.

## Integration into another ROS 2 workspace

1. Copy the complete `cstam_robot` directory into the other workspace's `src/` directory. No files from the original `Delivery-Robot-ROS` repository are required.
2. Install or provide the package dependencies: ROS 2 Jazzy, `xacro`, `robot_state_publisher`, `ros_gz_sim`, `ros_gz_bridge`, `rviz2`, `geometry_msgs`, `nav_msgs`, `sensor_msgs`, `tf2_msgs`, and `joint_state_publisher_gui`.
3. Build and source the workspace:

   ```bash
   source /opt/ros/jazzy/setup.bash
   colcon build --symlink-install --packages-select cstam_robot
   source install/setup.bash
   ```

4. For isolated verification, run `ros2 launch cstam_robot gazebo_test.launch.py`.
5. To spawn into an existing Gazebo world, start that world with its normal `ros_gz_sim` launch, start a `robot_state_publisher` using `urdf/cstam_robot.urdf.xacro`, and use `ros_gz_sim create` with the `robot_description` topic:

   ```bash
   ros2 run ros_gz_sim create \
     -name cstam_service_robot \
     -topic robot_description \
     -x 0 -y 0 -z 0.02
   ```

   The external environment must provide Gazebo physics, scene broadcasting, and a ground/collision world. It does not need to provide any CSTAM-specific package, map, Nav2, SLAM, namespace, or launch file.

6. Bridge the robot's Gazebo topics in the external launch. At minimum, use the same mappings as `launch/gazebo_test.launch.py` for `/cmd_vel`, `/odom`, `/tf`, `/scan`, and the RGB-D camera topics.

The package does not assume a namespace. If a team uses a namespace, apply it consistently to the robot description topic, bridge topics, and any later Nav2/SLAM configuration.

## Test scope and limitations

The package deliberately does not implement Nav2, SLAM Toolbox, delivery task management, docking, battery simulation, dynamic obstacle behavior, or visual recognition. The test world is only a bring-up fixture and is not the CSTAM competition environment.

The RGB-D camera is a real Gazebo Harmonic sensor and is bridged to ROS image/camera-info topics. `imu_link` is present in the TF structure, but IMU data is intentionally not enabled yet because it needs a follow-up validation across the target Gazebo/bridge versions. Ultrasonic data is not implemented. Payload distribution, wheel slip, suspension, motor controllers, and measured CAD inertias are approximations that should be refined when mechanical data is available.
