# Phase 1 recording plan — maximum 3 minutes

Required footage: **real CSTAM basic movement and live SLAM mapping**. Optional
accepted navigation/delivery excerpts may follow. Full deliveries take over
five minutes, so show an explicitly labelled excerpt or time-lapse; never imply
an entire delivery occurred in a short uncut clip.

Prepare builds, GUI windows and sourced terminals before recording. Record only
Gazebo/RViz and the relevant terminal; exclude unrelated personal windows.
Use the commands in [PHASE1_DEMO_GUIDE.md](PHASE1_DEMO_GUIDE.md).

| Time | Visible action | Narration |
|---|---|---|
| 0:00–0:10 | Restaurant, CSTAM, title | First-floor robot, ROS 2 Jazzy and Gazebo Harmonic. |
| 0:10–0:25 | RViz 3D cloud and navigation scan | Real 16 × 360 simulated LiDAR; body filtering and 2D projection. |
| 0:25–1:25 | Mapping mode, physical turn and forward motion, map growth | SLAM combines real scan, wheel odometry and TF. Show the live map changing. |
| 1:25–1:40 | Map saver command and saved PGM/YAML | Save the demonstration map without replacing the accepted navigation map. |
| 1:40–1:55 | Labelled switch to normal mode; automatic AMCL, health PASS | Restart/wait may be edited out with a clear mode-change label. |
| 1:55–2:25 | Accepted navigation excerpt or labelled delivery time-lapse | Kitchen → table → dock uses actual NavigateToPose results. |
| 2:25–2:40 | Actual IDLE-at-dock status and robot at station | Docking means return to a station pose, not charger alignment. |
| 2:40–2:55 | Architecture SVG and brief result summary | Perception, localization, Nav2, delivery queue and docking. |

Target **2:55**, leaving 5 seconds margin. If GUI wall time is slow, use an
explicitly labelled time-lapse for motion; map and robot must remain visible.
Do not substitute an animation or fabricated sensor/map footage. Preserve an
uncut original of recorded segments. Confirm exported duration <=180 seconds.

Recording, video upload, public-link verification and submission-form completion
are separate operator actions. No video or upload is claimed as completed here.
