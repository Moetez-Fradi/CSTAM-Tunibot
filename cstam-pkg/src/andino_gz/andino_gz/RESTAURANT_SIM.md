# Restaurant simulation

This scene packages the Sweet Home 3D export at
`models/restaurant/meshes/restaurant.obj` as a static, collidable Gazebo
model.  Sweet Home 3D uses centimetres and a Y-up coordinate frame, while
Gazebo uses metres and Z-up; the transform is documented in `model.sdf`.

From the workspace containing this package, build and source it once:

```bash
ros
cd /workspace/src/Autonomous-Delivery-Robot
colcon build --packages-select andino_gz
source install/setup.bash
```

Then launch the scene:

```bash
ros2 launch andino_gz restaurant.launch.py
```

## Drive the robot with the keyboard

Leave the simulation running in its first terminal. Open a second terminal,
enter the ROS container, source this workspace, and run:

```bash
ros
cd /home/golden5ragon/Desktop/Robotics/cstam/Autonomous-Delivery-Robot
source install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Keep focus in that second terminal while driving. Use `i`, `j`, `k`, and `l`
to drive/turn, `,` to reverse, `q` / `z` to change speed, and `CTRL-C` to
stop teleoperation. The node publishes to `cmd_vel`, which the restaurant
launch bridges to the Andino model.

If the container mounts the repository somewhere other than `/workspace`, use
that mount path instead.  The generic launch remains available when you need a
different robot pose:

```bash
ros2 launch andino_gz andino_gz.launch.py \
  world_name:=restaurant.sdf nav2:=False rviz:=False \
  'robots:=andino={x: -8.0, y: -12.0, z: 0.10, yaw: 0.0};'
```

The elevator is a kinematic actor on a 28-second lower-floor / upper-floor
loop.  Three geometric pedestrian actors use staggered 43-46 second loops:
they remain at selected dining-table seats, leave on fixed routes, then return
to those seats.  Change their `<waypoint>` poses and times in
`worlds/restaurant.sdf` to adjust routes; waypoint coordinates are in Gazebo
metres.

The source OBJ names a `test.mtl` file that was not provided with the export.
The scene therefore uses the neutral fallback material in `model.sdf`.  Put a
matching `test.mtl` plus any texture assets next to `restaurant.obj` if you
want to restore the original Sweet Home 3D materials.

The OBJ is used for visuals only.  Sweet Home exports a single, self-
intersecting triangle mesh, which is unsuitable for dynamic collision in ODE.
`models/restaurant_collision/model.sdf` supplies generated primitive collision
boxes for each wall segment, table top, chair seat, and chair back, plus the
world's stable 60 m floor plane. Regenerate it after replacing the OBJ:

```bash
python3 src/andino_gz/andino_gz/tools/generate_restaurant_collisions.py
```

## Moving the elevator

The elevator is currently centred at Gazebo coordinates `x=-3`, `y=-2`.
Change its location by replacing both coordinates consistently in
`worlds/restaurant.sdf`: the `<model name="elevator_shaft">` pose and every
`restaurant_elevator` trajectory waypoint. Gazebo coordinates are metres;
positive X points right in the imported scene and positive Y points toward the
front of the restaurant. Keep the Z values (`0` lower floor, `3` upper floor)
unless the floor heights change.
