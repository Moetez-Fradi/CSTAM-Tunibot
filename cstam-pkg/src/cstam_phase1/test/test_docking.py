"""Final docking approach controller."""
import math

import pytest

from cstam_phase1.docking import DockApproach

DOCK = (5.78, 15.50, math.pi / 2)


def simulate(start, seconds=40.0, dt=0.1):
    approach = DockApproach(DOCK)
    x, y, yaw = start
    furthest = 0.0
    for step in range(int(seconds / dt)):
        linear, angular, done = approach.step((x, y, yaw))
        if done:
            return (x, y, yaw), step * dt, furthest
        assert abs(linear) <= approach.params.max_speed + 1e-9
        assert abs(angular) <= approach.params.max_turn + 1e-9
        yaw += angular * dt
        x += linear * dt * math.cos(yaw)
        y += linear * dt * math.sin(yaw)
        furthest = max(furthest, math.hypot(x - DOCK[0], y - DOCK[1]))
    raise AssertionError(f'not docked from {start}')


@pytest.mark.parametrize('dx, dy, dyaw', [
    (0.0, -0.25, 0.0),      # short of the dock, straight
    (0.0, 0.20, 0.1),       # overshot: backs up
    (0.20, -0.10, -0.2),    # beside it, turned away
    (-0.18, 0.15, 0.2),
    (0.03, 0.0, 0.35),      # in place, wrong heading only
    (0.0, 0.0, 0.0),        # already there
])
def test_reaches_the_dock_pose_from_nav2_tolerance(dx, dy, dyaw):
    (x, y, yaw), took, furthest = simulate((DOCK[0] + dx, DOCK[1] + dy, DOCK[2] + dyaw))
    assert math.hypot(x - DOCK[0], y - DOCK[1]) <= 0.04 + 1e-6
    assert abs(math.remainder(yaw - DOCK[2], math.tau)) <= 0.04 + 1e-6
    assert took < 25.0
    # Never wanders off: the corridor is 1.86 m wide.
    assert furthest <= math.hypot(dx, dy) + 0.05


def test_does_not_restart_the_approach_for_a_small_drift_during_the_final_turn():
    approach = DockApproach(DOCK)
    approach.step((DOCK[0] + 0.02, DOCK[1], DOCK[2] + 0.3))
    assert approach.final_turn
    linear, angular, done = approach.step((DOCK[0] + 0.06, DOCK[1], DOCK[2] + 0.3))
    assert linear == 0.0 and angular != 0.0 and not done
