# Current Phase 1 checkpoint — 2026-10-01

The user's stop-before-delivery boundary was revoked by the latest request.
**Delivery acceptance is now complete.** Resume from the final accepted profile,
not from old failure hypotheses. Branch `Youssef`; all changes remain uncommitted.
No reset, restore, main modification, commit or push.

## Verified robotics

- Correct centred `base_drive -> base_footprint` reference; calibrated four-wheel
  drivetrain and chassis-clearance fix retained.
- Real 16×360 cloud, body filter, navigation scan and separate clearing cloud.
- Static/inflation global costmap; rolling voxel/inflation local costmap.
- Conservative footprint 0.66×0.54 m, padding 0.01 m, inflation 0.51 m/scaling 5.
- Rotation Shim + DWB, pose-based progress, velocity smoother actual output.
- NavFn Dijkstra, accepted map and semantic pickup/table/dock poses retained.
- Kitchen 3/3, raw navigation 4/4, zero recorded furniture contacts.
- Two fresh headless full deliveries plus an extra GUI-enabled delivery, FIFO table 1 then table 2, duplicate/empty/unknown
  rejection, automatic station return and manual service from table 1 all passed.
- Live SLAM map growth and separate map saving; normal GUI/RViz health passed.
- Five packages build; eleven tests pass; copied clean workspace build/tests/runtime
  pass on this host. Pristine second machine dependency installation not tested.

## Final decisions

Smac2D direct/real kitchen comparison succeeded with the stock recovery tree,
but full application reliability has not been established for it; preserve the
accepted NavFn profile. Collision-checked extra smoothing failed during dock
departure replanning, so it was not adopted. Do not disable collision checks to
force it. RPP was compared and was slower/required more recoveries than Shim+DWB
on the matched customer route. No MPPI or hidden waypoints were introduced.

## Where to find actual evidence

- `PHASE1_REPORT.md`: final 42-item acceptance report, decisions, commands and limits.
- `docs/phase1_navigation_checkpoint.json`: preserved historical navigation gate
  and controller/TF/semantic audits; its application NOT TESTED fields describe
  the earlier pause and are superseded by the final application evidence.
- `docs/phase1_application_acceptance.json`: actual delivery/queue/manual action
  results, stage physical poses, contact counts and source hashes.
- `docs/phase1_mapping_acceptance.json`: live mapping growth and saved map.
- `docs/phase1_planner_comparison.json`: measured alternate planner/smoother trials.
- `docs/PHASE1_TESTS.md`: reproducible acceptance cases.

Docking means station-pose arrival, not charger engagement. Publication/video/
submission actions are not completed or implicitly authorized by engineering
acceptance. Review and explicitly authorize any final checkpoint commit/push.

Final validation: original and copied build 5 packages; eleven tests; focused
rosdep dependencies all satisfied; fresh copied normal health PASS=22 FAIL=0.
All owned runtime helpers and simulator/ROS processes were stopped. The final
bounded one-leg GUI mapping helper completed and saved a 323×423 demo map.
