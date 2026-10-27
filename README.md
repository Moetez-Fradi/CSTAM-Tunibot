# CSTAM Tunibot — autonomous restaurant delivery robot

First-floor restaurant service robot using **ROS 2 Jazzy / Gazebo Harmonic**.
Real simulated 3D LiDAR, SLAM Toolbox, AMCL, Nav2, semantic delivery requests,
FIFO queue, and autonomous return to a defined dock pose.

Phase 2 adds [battery simulation](#battery-simulation) with return to dock
before the battery dies, [people as dynamic obstacles](#dynamic-obstacles-people-in-the-restaurant),
and a [complex layout with failure recovery](#complex-layout-terrace-doors-and-failure-recovery):
deliveries to the terrace through 0.92 m doorways, rerouting around a
blocked door and giving up gracefully when no route exists.

Phase 3 adds [orders and a web UI backend](#orders-and-the-web-ui): menu
orders with IDs, cancellation, a customer confirmation at the table, ETAs,
an order history log, and a dependency-free HTTP/Server-Sent Events API for
the customer and admin pages.

The robot lives in its [home corridor](#robot-home-corridor): it charges
there and is loaded through the kitchen service hatch at the corridor's end.

**Measured acceptance:** kitchen 3/3, raw Nav2 4/4, two fresh complete deliveries,
queued table 1 then table 2, invalid/duplicate rejection, and manual dock return
passed. Physical arrival errors and recorded results are in the
[application acceptance data](docs/phase1_application_acceptance.json).
Docking here means autonomous station-pose arrival, not charger alignment.

## Prerequisites and focused build

Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic through ROS Gazebo packages,
colcon, rosdep, and an OpenGL display for GUI use. On a new machine, initialize
rosdep once (`sudo rosdep init`, then `rosdep update`). Install dependencies
for the six-package closure, excluding the legacy applications in `App/`:

```bash
git clone --branch main https://github.com/Moetez-Fradi/CSTAM-Tunibot.git
cd CSTAM-Tunibot/cstam-pkg
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths \
  src/cstam_phase1 src/cstam_robot src/andino_gz/andino_gz \
  src/andino/andino_description src/andino/andino_slam src/cstam_ui \
  --ignore-src -r -y --rosdistro jazzy
colcon build --symlink-install --packages-up-to cstam_ui
source install/setup.bash
```

Repeat the two `source` commands in every terminal. Launch children use a
package-local Fast DDS UDP profile. To make separate CLI terminals use it too:

```bash
export FASTDDS_DEFAULT_PROFILES_FILE="$(ros2 pkg prefix --share cstam_phase1)/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="$FASTDDS_DEFAULT_PROFILES_FILE"
```

## Robot home corridor

The restaurant model has a 1.86 m wide, 7.5 m long service corridor north of
the dining room (map x 4.85–6.71, y 10.44–17.98), opening into the room
through a 1.56 m doorway. It is the robot's home:

- **dock** (5.78, 15.50), facing the end wall: the robot spawns, waits and
  charges here;
- **kitchen** pickup (5.78, 17.25) at the service hatch in the end wall,
  where the robot is loaded.

An order starts with a short drive forward to the hatch, one turn, and the
trip out through the doorway; a delivery ends driving straight back in to the
dock. SLAM only saw the corridor's mouth, so
`cstam_phase1/scripts/build_home.py` draws it into the saved map from the
mesh geometry (walls, interior, doorway between the frame jambs). The
dining-room north wall's collision boxes are split at the doorway, as the
west wall is at the terrace doors.

The robot cruises at up to 0.45 m/s and turns at up to 0.9 rad/s; near
people the collision monitor still limits it to 0.07 m/s or stops it.

## Normal operation: one launch

```bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
```

The saved map loads, AMCL initializes at the configured dock, and the navigation
and delivery nodes start. In a second sourced terminal, require `FAIL=0`:

```bash
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase1_smoke_test.sh"
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
ros2 topic echo /delivery/status std_msgs/msg/String
```

The web UI is served on <http://localhost:8080> (`ui:=false` disables it,
`ui_port:=` moves it). The sequence is kitchen → table 1 → wait at the table
for the customer (`AWAITING_CONFIRMATION`, up to `confirmation_timeout:=20`
s; `0` completes on arrival) → dock → `IDLE`. From the home corridor,
with the five simulated people walking, a complete headless delivery took
163 s to table 1 and 133 s to terrace 1 (out through door B and back), with
no contacts. GUI rendering can make wall time longer.
While busy, publishing `table_2` queues a second delivery. Duplicates, empty
requests and unknown names are rejected without changing the active task.
The FIFO policy serves queued customers before returning to dock.

```bash
ros2 service call /delivery/status std_srvs/srv/Trigger '{}'
ros2 service call /delivery/return_to_dock std_srvs/srv/Trigger '{}'
```

Manual return cancels an application-owned active goal, waits for its result,
then sends the real dock goal. Pending queued requests remain queued, and an
interrupted order is requeued at the front.
A failed navigation puts the application in `ERROR`; success is never synthesized.
Do not send separate raw goals while a delivery is active.

## Battery simulation

`battery_simulator` publishes `sensor_msgs/BatteryState` on `/battery/state`.
It integrates a 10 Wh Li-ion model on simulated time: a fixed 4 W electronics
load, plus extra power proportional to the real `/odom` linear and angular
speed. One delivery uses about 10% of the charge. The robot charges at 60 W,
tapering above 80%, but only while it is stationary within 0.5 m of the dock
(AMCL pose). The task manager reads the battery and decides:

| Battery | Behavior |
|---|---|
| < 35% when a delivery would start | does not start; returns to dock, `CHARGING` |
| ≤ 20% during a delivery | cancels, requeues the order at the front, returns to dock, `CHARGING` |
| ≥ 80% while `CHARGING` | `IDLE`, then serves the queue |
| 0% | cancels navigation, keeps the order, `BATTERY_DEPLETED` |

`/delivery/status` includes `battery_percentage` and `battery_charging`.
Start low or accelerate the model, and override the level live (use a float):

```bash
ros2 launch cstam_phase1 phase1.launch.py battery_percentage:=40 battery_time_scale:=20
ros2 param set /cstam_battery_simulator percentage 19.0
ros2 topic echo /battery/state
```

Verified headless: a delivery to table 1 was driving to pickup at 99%; forcing
19% switched it to `RETURNING_TO_DOCK` with `table_1` requeued, it docked and
reported `CHARGING` (charger current positive), and at 80% it resumed table 1.

## Dynamic obstacles: people in the restaurant

Normal mode spawns five scenario-driven pedestrians
(`cstam-pkg/src/cstam_phase1/config/pedestrians.yaml`, routes in the map
frame). Each targets one encounter on the real delivery routes:

| Person | Behavior | Encounter |
|---|---|---|
| `waiter_ali` | polite, 0.9 m/s | head-on in the 1.6 m west aisle |
| `guest_sara` | oblivious, 1.0 m/s | fast crossing of both robot routes |
| `chef_omar` | polite, 0.6 m/s | walks across the mouth of the home corridor, where every trip starts and ends |
| `guest_lina` | oblivious, 0.5 m/s | passes in front of the dock and tables |
| `guest_youssef` | polite, 0.7 m/s | stands 30 s on the east route, then moves |

Polite people slow down, step aside and stop for the robot. Oblivious people
keep walking and stop only when the next step would touch the robot, so the
robot alone must keep its distance. Nobody waits forever: after 4 s held up
by the robot or another person, they walk around on a free side, keeping
0.25 m of personal space from the robot. People are light visual-only models moved
through `set_pose`; Gazebo memory is unchanged, and the extra nodes cost about
260 MB in total. Disable them with `pedestrians:=false`.

How the robot reacts, using only its own sensors and AMCL:

1. `dynamic_obstacle_tracker` removes returns near the static map, clusters
   the rest, and tracks each person with a constant-velocity Kalman filter
   (8 Hz). It fuses the front-mounted 3D LiDAR with a short-range rear sensor
   (`/rear_range/scan`, emulating the three rear ultrasonic mounts: 55 rays,
   +-135 deg, 2.5 m, 10 Hz), because the mast hides the area beside and behind
   the robot from the LiDAR. A person last seen entering what is still blind is kept,
   standing still, for up to 10 s instead of being forgotten.
2. People never enter the voxel layer: the tracker republishes the 3D cloud
   without confirmed people as `/lidar/points_static`. In the voxel layer a
   passer-by left lethal trails inside the LiDAR's near-field blind cone (it
   cannot see the floor within ~0.5 m), where no ray ever clears them.
   Untracked people still reach the voxel layer, so a tracking miss stays
   safe. Hit rays now also clear voxels (`clearing: true`).
3. The local costmap `people_layer` marks each person and their predicted
   path for the next 2 s, so the controller avoids where someone is about to
   walk, not only where they are.
4. The global costmap `people_layer` marks people's current positions, so
   NavFn replans around someone standing in an aisle. Raw scans still never
   enter the global costmap.
5. `collision_monitor` sits between the velocity smoother and Gazebo and
   watches people only (tables are handled by the costmaps): it stops for a
   person in the zone the robot is about to sweep, caps forward speed at
   0.07 m/s for a person within 1.4 m ahead, and caps speed so the footprint
   cannot reach a person within 1.5 s. Turning in place is never slowed.
   If the people stream goes stale it stops the robot. Every action is an
   absolute cap: a percentage slowdown compounds with the controllers'
   acceleration ramp and was measured to pin the robot at about 1.7 cm/s.

RViz shows tracked people (orange = moving, with a red prediction line),
ground truth (green discs) and the stop/slowdown zones.

Safety is measured from ground truth, independently of the robot's
perception: `/pedestrians/metrics` reports the minimum clearance between the
real robot footprint and each person, contacts, and close passes. People
never step closer than 3 cm, so a contact is the robot's fault whenever the
person stood still as it began (the robot drove or turned into them).

One command runs a recorded acceptance run (headless, own process group,
health check, deliveries, clean shutdown), and one turns runs into a report
that reconstructs every contact in the robot frame:

```bash
bash "$(ros2 pkg prefix --share cstam_phase1)/scripts/phase2_acceptance.sh" ~/runs/r1
ros2 run cstam_phase1 phase2_report ~/runs/r1 --json ~/runs/r1/report.json
```

### Dynamic-obstacle test cases

Each case was found by a recorded run, reconstructed from the trace, fixed,
and re-run. "Found" names what failed before the fix.

| # | Edge case | Found | Handling |
|---|---|---|---|
| 1 | Head-on in the 1.6 m west aisle | robot and waiter waited for each other | Waiter squeezes past along the wall (graded detour lanes); with no way past he turns back; the robot may always back away (reverse zone checks only behind it) |
| 2 | Fast perpendicular crossing (1 m/s, oblivious) | — | 2 s predicted path in the local costmap; robot yields before the line |
| 3 | Person standing on the route for 30 s | — | Global people layer; NavFn replans around them |
| 4 | Person walks up to the robot's side or rear, then the robot turns | 4 contacts across runs | Rear and side range sensors give 360° people sensing (measured: 16/16 bearings at 0.15 m); turning uses a stop zone covering the swept corners plus 0.15 m for tracking latency |
| 5 | Person disappears into a remaining blind spot | memory parked ~0.8 m from the person | Track kept standing still at its last *measured* position for 10 s |
| 6 | Passer-by leaves voxel trails in the LiDAR's near-field blind cone | robot stalled at phantom obstacles | Tracked people removed from the voxel cloud; hit rays clear voxels |
| 7 | Collision monitor slowdown vs controller ramp | robot pinned at 1.7 cm/s, progress failures | Absolute speed caps only; turning in place never limited |
| 8 | Tracker output stalls | controller aborted on a stale costmap | People layers never abort navigation; the monitor stops the robot instead |
| 9 | People blocking each other / waiting on the robot forever | gridlocks in the simulator | Patience detours with staggered retries; lanes checked against the map, the robot and other people |
| 10 | First planner request after startup | goal unacknowledged within 20 ms | BT server timeout 200 ms; smaller people-layer update area |

Measured on the final configuration, two consecutive recorded runs (tables 1,
2 and 3 each): **6/6 deliveries, 0 contacts, 140 encounters within 1 m**,
closest pass while the robot moved 0.02 m (people walking up to a slow or
stopped robot), deliveries 289-379 s, longest stall 17.5 s after the
narrow-aisle fix (103.5 s before it), peak system RAM 6.1 GB.
People-sensing coverage was measured with a probe at 16 bearings around the
robot: all detected at 0.15 m and 0.5 m from the footprint.

- [Dynamic-obstacle acceptance data](docs/phase2_dynamic_obstacles_acceptance.json)
- [Sensor coverage data](docs/phase2_sensor_coverage.json)

### Recording the dynamic-obstacle demo

```bash
ros2 launch cstam_phase1 phase1.launch.py rviz:=true
# second terminal, once the smoke test passes:
ros2 topic pub --once /delivery/request std_msgs/msg/String '{data: table_1}'
ros2 topic echo /pedestrians/metrics   # live clearance / contact counter
```

Put Gazebo and RViz side by side. The table 1 delivery covers every
encounter in about six minutes: the slow walker crossing in front of the dock
on departure, the waiter meeting the robot head-on in the west aisle (watch the
robot stop, the waiter wait and squeeze past along the wall, then the robot
continue), the fast guest cutting across the kitchen approach (orange track
with its red prediction line; the robot yields before the line), and the chef
crossing just short of the pickup pose. GUI rendering slows the simulation;
let it run rather than speeding the clip up in the recording.

## Complex layout: terrace doors and failure recovery

The restaurant's outdoor terrace is reachable through two of the west French
doors, with one leaf open each: a **0.92 m** clear opening for the 0.54 m
robot. `terrace_1` and `terrace_2` are delivery locations beside two terrace
tables; between the table blocks and the facade runs a ~1.6 m lane.

The Sweet Home 3D terrace was visual only, so
`cstam_phase1/scripts/build_terrace.py` builds it from the mesh:

- cuts the open leaves out of the west collision wall and the visual mesh
  (the LiDAR renders visuals, so a glass leaf would read as a closed door);
- removes the visual terrace deck (its 0.10 m surface sat above the LiDAR
  floor filter and read as one large obstacle) and the 4 cm door sills
  (right at the filter threshold, they flickered as obstacles and "people");
- generates `andino_gz/models/terrace_collision` (111 furniture boxes);
- extends the saved map 6 m west: the terrace operating area is drawn free,
  furniture and door hardware occupied, the whole west wall from the
  collision model except the two openings (SLAM had missed a stretch of it,
  and the planner routed through the gap). Everything else outside stays
  unknown, which the planner treats as a boundary.

How the robot handles it:

1. **Door routing.** A trip between the dining room and the terrace goes
   square through the door nearest the terrace stop: an inside staging pose,
   straight through to an outside staging pose, then the target (and the
   reverse on the way back). Without it, a sharp turn inside the doorway
   stalled the controller.
2. **Restaurant recovery tree** (`config/navigate_to_pose_cstam.xml`):
   Nav2's tree without Spin (useless and risky in a doorway or beside
   people), waiting first, a short slow BackUp, 8 retries.
3. **Task-level retries.** If Nav2 still aborts, the same leg is retried up
   to 3 times, 5 s apart.
4. **Alternative door.** If a door leg still fails, the route switches to
   the other door.
5. **Give up gracefully.** If no route works, the order is recorded in
   `failed_orders` (in `/delivery/status`), the robot returns to the dock
   and serves the rest of the queue. Only an unreachable dock ends in
   `ERROR`.

Recovery scenarios (`PEDESTRIAN_SCENARIO=...` for `phase2_acceptance.sh`):
`pedestrians_door_blocked.yaml` keeps a guest standing in door B;
`pedestrians_doors_blocked.yaml` blocks both doors.

### Layout and recovery test cases

| Run | Scenario | Result |
|---|---|---|
| t3 | `terrace_1`, `terrace_2`, `table_1`, no people | 3/3 delivered, 0 Nav2 failures |
| R1 | guest standing in door B; `terrace_1`, `table_1` | door B detected blocked both ways, rerouted through door A; 2/2 delivered, 0 Nav2 failures, closest 0.25 m |
| R2 | guests in both doors; `terrace_1`, `table_1` | both doors detected blocked, `terrace_1` given up, robot docked, `table_1` delivered; 0 Nav2 failures |
| reg | the five scenario pedestrians; `table_1`, `terrace_2`, `table_2` | 3/3 delivered, 0 contacts, 0 Nav2 failures, 76 encounters within 1 m |

Found and fixed on the way, each from a recorded run: door leaves, the
terrace deck and the door sills were visual geometry the LiDAR read as
obstacles or people; SLAM had missed part of the west wall, so the planner
routed through it; sharp turns inside the doorway stalled the controller;
a person standing in a doorway flickered as a track and the plan flipped
between doors. Evidence:
[layout and recovery acceptance data](docs/phase2_layout_recovery_acceptance.json).

## Orders and the web UI

`/delivery/request` accepts either a bare location (`table_1`, as before) or
a JSON order:

```bash
ros2 topic pub --once /delivery/request std_msgs/msg/String \
  '{data: "{\"location\": \"table_2\", \"items\": [{\"name\": \"Espresso\", \"qty\": 2}], \"note\": \"no sugar\"}"}'
ros2 topic pub --once /delivery/confirm std_msgs/msg/String '{data: table_2}'   # or the order id
ros2 topic pub --once /delivery/cancel std_msgs/msg/String '{data: table_2}'    # or the order id
```

Each table has at most one open order. Its record (id, items, note,
`created/started/picked_up/arrived/finished` wall-clock times, status
`queued`, `in_progress`, `awaiting_confirmation`, `delivered`, `failed` or
`cancelled`, interruptions) is reported in `/delivery/status` as
`active_order`, `orders` (queue order) and `history` (last 10), next to the
existing fields. `progress` gives the distance still to drive on the current
stage, including door hops, and an ETA at an average 0.3 m/s. A rejection
is reported as `last_rejection` with its order id and reason.

- At the table the robot waits for `/delivery/confirm`. Without one it
  counts the order as delivered (unconfirmed) after the timeout. A manual
  return or a depleted battery while waiting also counts it as delivered,
  so the order is never served twice.
- Cancelling a queued order drops it. Cancelling the active order sends the
  robot back to the dock (the food goes back to the kitchen) without
  requeueing it, then the queue continues.
- Every finished order is appended to `$ROS_HOME/cstam_orders.jsonl`
  (default `~/.ros`), the source for the admin history and analytics.

The `cstam_ui` node is the only bridge between browsers and ROS. It uses the
task manager's topics and services and never sends navigation goals. It is
standard-library Python: REST for commands, Server-Sent Events for live
updates, no rosbridge and nothing to `pip install`. Menu:
`cstam_ui/config/menu.yaml`. The staff dashboard and admin endpoints need
the PIN **`0000`** (`admin_pin:=` changes it, `admin_pin:=''` removes it);
the browser sends it as `X-Admin-Pin` (or `?pin=` for event streams).

| Endpoint | Purpose |
|---|---|
| `GET /api/config` | tables (with zone), dock, kitchen, doors, menu, map metadata |
| `GET /api/map.png` | the saved map (PNG), placed with `map.origin` / `map.resolution` |
| `GET /api/events?order=ID` | live public view: robot state, pose, battery, plan, ETA, that order and its queue position |
| `POST /api/orders` | `{location, items: [{id, qty}], note}`; answers with the accepted order or the robot's reason |
| `GET /api/orders/ID` | one order and its queue position |
| `POST /api/orders/ID/cancel`, `/confirm` | customer cancel (only while queued) and confirmation |
| `GET /api/admin/events`, `/api/admin/state` | everything: status, battery history, tracked people, safety metrics, node health |
| `GET /api/admin/history?limit=N` | finished orders from the log, newest first |
| `POST /api/admin/orders/ID/cancel`, `/api/admin/return_to_dock` | staff controls |

### Pages

| Page | For |
|---|---|
| `/` | landing page: customer or staff |
| `/table/<location>` (e.g. `/table/table_3`; `/table` lists them) | customers, phone first: menu, order, live tracking with ETA and a mini map, "I've got my order" at the table, cancel while queued. The order survives a page reload. Guests can also say or type the order in their own words (see [Voice ordering](#voice-ordering)). |
| `/admin` | staff dashboard. **Overview**: live floor plan (robot, planned route, tracked people, tables, doors), active delivery with its stages, battery with the 20/35/80% policy, queue with cancel, return to dock, battery chart for the last 30 minutes. **Orders**: delivered count, median time to table, confirmation rate, failures, full order log. **Insights**: deliveries per hour or day, revenue, time to table (median and 90th percentile), battery used per delivery and deliveries per charge, popular items, busiest tables, Nav2 goal/failure/retry counters (today, 7 days or all time). **Maintenance**: lifetime distance, driving time, operating time and battery cycles; a service schedule with a forecast of when each item falls due, and "Mark serviced". **System**: node health, data freshness, people-safety metrics, task manager state. |
| `/qr` | printable QR card per table (staff, linked from the dashboard). Each code opens that table's page. |
| `/console` | raw API console for development |

Light and dark themes follow the system setting (toggle top right). The
Geist fonts are bundled (`web/fonts`, SIL OFL 1.1), so the UI works without
internet.

**Voice ordering.** The customer page reads an order in the guest's own
words, spoken or typed, in English or French: "two cappuccinos and a brik",
"deux cafés et une citronnade pour la terrasse 2". `POST /api/voice`
(`cstam_ui/voice.py`) finds menu items (names and the `aliases` in
`menu.yaml`), quantities and a table, and the page adds them to the cart;
the guest still presses Send. The microphone uses the browser's speech
recognition, which browsers only allow on HTTPS or `localhost` (and Chrome's
recognition needs internet). Phones opening the plain-HTTP table page
therefore get the typed box only; for a spoken demo, use the laptop at
`http://localhost:8080/table/table_2`.

**Maintenance data.** Usage is integrated from `/odom` and `/battery/state`
by the UI node and kept in `$ROS_HOME/cstam_robot_usage.json` (saved every
30 s and on exit), so it accumulates across runs; intervals are in
`cstam_ui/config/maintenance.yaml`. It is only tracked while the UI runs.

**Table QR codes.** The codes point at this machine's network address,
detected at startup and printed in the log (`CSTAM UI on http://…`). Phones
must be on the same Wi-Fi, and port 8080 must be open in the laptop's
firewall. If the detected address is wrong (several networks, or a
hostname is preferred), launch with `ui_public_url:=http://<address>:8080`
or edit the address on the `/qr` page before printing. The codes are
generated by a small built-in encoder (`cstam_ui/qr.py`), verified by
decoding with OpenCV in the tests.

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
  '{pose: {header: {frame_id: map}, pose: {position: {x: 5.78, y: 17.25}, orientation: {z: 0.7071, w: 0.7071}}}}' --feedback
colcon test --packages-select cstam_phase1 --event-handlers console_direct+
colcon test-result --verbose
```

Use `headless:=True rviz:=false` for faster server-only execution.
Before changing modes or starting acceptance tests, check that no mapping
helper or old launch remains and inspect `ros2 topic info /cmd_vel -v`.
Normal mode has one physical command publisher, `collision_monitor`
(controller → `velocity_smoother` → `collision_monitor` → Gazebo).

- [Architecture diagram](docs/phase1_architecture.svg)
- [Final validation summary](docs/phase1_final_validation.json)
- [Application acceptance data](docs/phase1_application_acceptance.json)
- [Mapping acceptance data](docs/phase1_mapping_acceptance.json)

## Repository structure

- `cstam-pkg/src/cstam_robot`: robot Xacro, physics, sensors and bridge configuration.
- `cstam-pkg/src/andino_gz/andino_gz`: restaurant assets, collision model, world and GUI launch.
- `cstam-pkg/src/cstam_phase1`: perception, mapping/localization, Nav2, semantic locations, task manager, health checks and tests.
- `cstam-pkg/src/cstam_ui`: web UI backend (HTTP API, live events, menu) and pages.
- `cstam-pkg/src/App`, `cstam-pkg/src/deliverybot_bringup`: legacy prototypes
  (chatbot, QR verification, Streamlit dashboard, mobile bridge) from before
  the current stack. They are not built or launched by it.
- `docs`: intentional acceptance summaries and architecture exports.

All runtime assets resolve through package-share directories. Build/install/log,
ROS logs and temporary measurements are excluded. A separate workspace source
copy was built for portability; a pristine second machine was not tested.

## Limits

First floor only; no elevator. Pedestrians are kinematic visuals: they do
not physically push the robot, so contacts are measured geometrically from
ground truth rather than by contact sensors. The rear and side range
sensors emulate ultrasonics with narrow lidar beams. The terrace part of the
map is drawn from the collision geometry, not SLAM, and only two of the west
doors are open (one leaf each). The people tracker still produces occasional
short-lived false tracks (a few seconds) near walls and furniture edges.
On the development laptop, long runs rendering on the integrated
AMD GPU froze the machine three times (amdgpu `flip_done timed out`); the
RGB-D camera, unused by navigation, now renders at 5 Hz to reduce that load.
Charging is simulated by proximity to the dock pose, not by charger contact
or alignment. Static global
map and real rolling local obstacles. Sparse 16-ring sensing and simulated
friction limit real-hardware conclusions. Dock and table 3 are safe at their
configured headings, not at every possible rotation. Physical dock error in
accepted application runs was 0.176–0.292 m. Controller recovery maneuvers still
occur; these trials establish repeatability for the tested routes, not universal
collision avoidance. Consult the acceptance data for quantitative details.
