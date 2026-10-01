# Phase 1 submission checklist

## Technical acceptance

- [x] First-floor simulated robot, four-wheel physics and contact sensors
- [x] Real 3D cloud, body filtering, navigation projection and clearing stream
- [x] Live SLAM growth during real movement; map saving
- [x] Saved map, automatic AMCL, TF and normal-mode health `PASS=22 FAIL=0`
- [x] Kitchen reliability: three independent clean starts, 3/3
- [x] Raw navigation gate: short/long/obstacle/passage, 4/4
- [x] Full deliveries: two independent fresh starts, both ending IDLE at dock
- [x] FIFO queue, maximum one active Nav2 goal, final queue empty
- [x] Duplicate, unknown and empty request rejection
- [x] Automatic dock return and manual return service from table 1
- [x] No non-ground contacts in recorded accepted navigation/application runs
- [x] Build, eleven regression tests, smoke and diff checks
- [x] README, architecture diagram, demo and test documentation

## Publication / operator checklist

- [ ] Review final uncommitted source changes on `Youssef`
- [ ] Authorize final checkpoint commit and branch push
- [ ] Confirm repository visibility and evaluator access at submission time
- [ ] Record required movement + mapping footage
- [ ] Export video <=3 minutes and check duration
- [ ] Upload video and test download link without authentication
- [ ] Complete the submission form using the actual current deadline

Repository: https://github.com/Moetez-Fradi/CSTAM-Tunibot
No commit, push, visibility change, upload or form submission was performed in
this engineering continuation. Earlier visibility was PRIVATE; access must be
checked again by the owner before submission. No deadline is inferred from old
mail or historical reports.

Read [PHASE1_REPORT.md](PHASE1_REPORT.md) for measured tolerances and limitations.
Passing the tested simulation routes does not establish real hardware safety,
precise charging alignment or behavior in arbitrary layouts.
