# Evidence index

Measured results behind the claims in the main README. JSON files are
summaries of recorded runs; the scripts that produce them are in
`cstam-pkg/src/cstam_phase1/scripts`.

| File | What it shows |
|---|---|
| `phase1_architecture.{svg,png,mmd,dot}` | node and topic architecture (Phase 1) |
| `phase1_gazebo.png`, `phase1_rviz.png`, `phase1_paths.png` | simulation, RViz and planned paths |
| `phase1_mapping_acceptance.json` | SLAM mapping run: map growth, odometry distance |
| `phase1_aisle_measurement.json` | narrowest aisle vs the padded robot footprint |
| `phase1_planner_comparison.json` | NavFn vs Smac vs smoothed replanning |
| `phase1_navigation_checkpoint.json` | raw Nav2 goals and kitchen starts |
| `phase1_application_acceptance.json` | deliveries, queue, rejection, manual dock return |
| `phase1_gui_acceptance.json` | GUI launch, health check, one command publisher |
| `phase1_final_validation.json` | Phase 1 summary |
| `phase2_dynamic_obstacles_acceptance.json` | deliveries among pedestrians: contacts, clearances, stalls |
| `phase2_layout_recovery_acceptance.json` | terrace doors, blocked doors and recovery |
| `phase2_sensor_coverage.json` | 360° people sensing probe |
| `CSTAM_Phase2_Test_Cases.html`, `Selecao-test-cases-documentation.pdf` | Phase 2 test-case documentation |
| `phase3_ui_acceptance.json` | end-to-end web order (`phase3_ui_test.sh`): 18/18 checks, physical dock error 0.062 m |
| `phase3_tracker_false_tracks.json` | false people tracks before/after the furniture filters |
