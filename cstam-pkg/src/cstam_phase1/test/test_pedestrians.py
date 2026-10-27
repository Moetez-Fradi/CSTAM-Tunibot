import math
import pathlib

import numpy as np
import yaml

from cstam_phase1.pedestrian_model import (
    Pedestrian,
    PedestrianConfig,
    PedestrianParams,
    footprint_clearance,
)
from cstam_phase1.people_tracking import StaticMap


PACKAGE = pathlib.Path(__file__).parents[1]


def walker(behavior, route=((0.0, 0.0), (10.0, 0.0)), speed=1.0):
    return Pedestrian(PedestrianConfig(
        name='p', route=[(x, y, 0.0) for x, y in route],
        behavior=behavior, speed=speed))


def run(pedestrian, seconds, robot=None, others=(), dt=0.05):
    clearances = []
    for _ in range(int(seconds / dt)):
        pedestrian.step(dt, robot, others)
        if robot is not None:
            clearances.append(footprint_clearance(robot, pedestrian.position))
    return clearances


def test_footprint_clearance_matches_rectangle():
    robot = (0.0, 0.0, 0.0)
    assert math.isclose(footprint_clearance(robot, (1.35, 0.0)), 1.0 - 0.22)
    assert math.isclose(footprint_clearance(robot, (0.0, 1.27)), 1.0 - 0.22)
    assert footprint_clearance(robot, (0.2, 0.0)) < 0.0
    rotated = (0.0, 0.0, math.pi / 2)
    assert math.isclose(footprint_clearance(rotated, (0.0, 1.35)), 1.0 - 0.22)


def test_walks_route_at_bounded_speed_and_turns_back():
    p = walker('polite', route=((0.0, 0.0), (3.0, 0.0)))
    run(p, 2.0)
    assert 1.2 < p.position[0] < 2.0
    run(p, 2.5)  # reaches x=3 at about 3.5 s, then turns in place
    assert p.target == 0 and p.direction == -1
    run(p, 1.5)
    assert p.position[0] < 2.9  # walking back


def test_polite_pedestrian_yields_then_goes_around_with_personal_space():
    p = walker('polite')
    robot = (4.0, 0.0, math.pi)  # head-on in the walking lane
    yielded, furthest, clearances = False, 0.0, []
    for _ in range(int(20.0 / 0.05)):
        p.step(0.05, robot, ())
        yielded |= p.yielding
        furthest = max(furthest, p.position[0])
        clearances.append(footprint_clearance(robot, p.position))
    assert yielded
    # Lanes are validated at 0.2 m samples while the sweep is diagonal.
    assert min(clearances) >= p.params.personal_space - 0.02
    assert furthest > 5.0  # went around instead of waiting forever


def test_polite_pedestrian_walks_by_when_its_lane_already_clears_the_robot():
    p = walker('polite')
    robot = (4.0, 1.2, 0.0)  # beside the lane, 0.71 m from the person's edge
    clearances = run(p, 8.0, robot)
    assert p.position[0] > 5.0 and not p.detouring
    assert min(clearances) > 0.3


def test_polite_pedestrian_goes_left_when_right_is_blocked():
    p = walker('polite')
    robot = (3.0, 0.0, math.pi)
    lowest = 0.0
    for _ in range(int(20.0 / 0.05)):
        p.step(0.05, robot, (), is_free=lambda x, y: y > -0.1)
        lowest = min(lowest, p.offset)
        assert p.position[1] > -0.1
    assert lowest < -0.2  # negative offset = to the left of travel


def test_oblivious_pedestrian_keeps_speed_but_cannot_walk_through_robot():
    p = walker('oblivious')
    robot = (4.0, 0.0, math.pi)
    clearances = run(p, 5.5, robot)  # reaches the robot, before patience ends
    assert not p.yielding
    assert p.offset == 0.0
    assert p.speed == 0.0
    assert min(clearances) >= p.params.contact_margin - 1e-6


def test_pedestrians_do_not_walk_into_each_other():
    p = walker('oblivious')
    other = (2.0, 0.0)
    run(p, 6.0, others=[other])
    assert math.hypot(p.position[0] - other[0], p.position[1] - other[1]) >= 0.5


def _load_map():
    meta = yaml.safe_load((PACKAGE / 'maps' / 'restaurant' / 'restaurant.yaml').read_text())
    raw = (PACKAGE / 'maps' / 'restaurant' / meta['image']).read_bytes()
    parts, index = [], 0
    while len(parts) < 4:  # P5 header: magic, width, height, maxval
        while raw[index:index + 1].isspace():
            index += 1
        if raw[index:index + 1] == b'#':
            index = raw.index(b'\n', index) + 1
            continue
        end = index
        while not raw[end:end + 1].isspace():
            end += 1
        parts.append(raw[index:end])
        index = end
    width, height = int(parts[1]), int(parts[2])
    pixels = np.frombuffer(raw[index + 1:index + 1 + width * height], dtype=np.uint8)
    pixels = pixels.reshape(height, width)[::-1]  # image top row is max y
    occupancy = (255 - pixels.astype(float)) / 255.0
    grid = np.full(pixels.shape, -1, dtype=np.int8)
    grid[occupancy > meta['occupied_thresh']] = 100
    grid[occupancy < meta['free_thresh']] = 0
    return grid, meta


def test_scenario_routes_stay_clear_of_the_saved_map():
    grid, meta = _load_map()
    static = StaticMap(grid, meta['resolution'], meta['origin'][0], meta['origin'][1],
                       margin=0.25)
    scenario = yaml.safe_load((PACKAGE / 'config' / 'pedestrians.yaml').read_text())
    assert len(scenario['pedestrians']) >= 4
    names = set()
    for item in scenario['pedestrians']:
        config = PedestrianConfig.from_dict(item)
        names.add(config.name)
        route = config.route + ([config.route[0]] if config.mode == 'loop' else [])
        for (x0, y0, _), (x1, y1, _) in zip(route, route[1:]):
            samples = max(2, int(math.hypot(x1 - x0, y1 - y0) / 0.05))
            t = np.linspace(0.0, 1.0, samples)
            points = np.column_stack([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
            blocked = static.is_static(points)
            assert not blocked.any(), (
                f'{config.name} route passes within 0.25 m of the map at '
                f'{points[blocked][0]}')
    assert len(names) == len(scenario['pedestrians'])


def test_blocked_pedestrian_detours_around_a_stopped_robot():
    # A stopped robot squarely in the lane must not create a deadlock.
    for behavior in ('polite', 'oblivious'):
        p = walker(behavior)
        robot = (4.0, 0.0, math.pi / 2)  # parked across the lane
        furthest, clearances = 0.0, []
        for _ in range(int(20.0 / 0.05)):
            p.step(0.05, robot, ())
            furthest = max(furthest, p.position[0])
            clearances.append(footprint_clearance(robot, p.position))
        assert furthest > 5.0, behavior  # got past the robot
        assert min(clearances) >= p.params.contact_margin - 1e-6


def test_detour_needs_a_free_side():
    p = walker('oblivious')
    robot = (4.0, 0.0, math.pi / 2)
    for _ in range(int(20 / 0.05)):
        p.step(0.05, robot, (), is_free=lambda x, y: abs(y) < 0.1)
    assert not p.detouring
    assert p.position[0] < 4.0  # walls on both sides: it waits


def test_detour_never_chooses_the_side_through_the_robot():
    p = walker('oblivious')
    # Robot just ahead and to the right of the lane: only left is clear.
    robot = (4.0, -0.75, math.pi / 2)
    run(p, 20.0, robot)
    assert p.detour_offset < 0.0 or not p.detouring


def test_detouring_pedestrian_keeps_personal_space():
    p = walker('oblivious')
    robot = (4.0, 0.0, math.pi / 2)
    floor = None
    for _ in range(int(20.0 / 0.05)):
        p.step(0.05, robot, ())
        clearance = footprint_clearance(robot, p.position)
        if p.detouring:
            if floor is None:  # where the detour began
                floor = min(clearance, p.params.personal_space)
            # Lanes are validated at 0.2 m samples while motion is diagonal,
            # so allow a centimetre or two of undershoot.
            assert clearance >= floor - 0.02
    assert floor is not None


def test_two_people_blocking_each_other_resolve_by_detouring():
    a = walker('oblivious', route=((0.0, 0.0), (6.0, 0.0)))
    b = walker('oblivious', route=((6.0, 0.0), (0.0, 0.0)))
    a_max, b_min = 0.0, 6.0
    for _ in range(int(20.0 / 0.05)):
        a.step(0.05, None, [b.position])
        b.step(0.05, None, [a.position])
        assert math.dist(a.position, b.position) >= 0.45
        a_max, b_min = max(a_max, a.position[0]), min(b_min, b.position[0])
    # Both got past each other to the far end of their lane.
    assert a_max > 5.5 and b_min < 0.5


def test_detour_squeezes_along_a_narrow_aisle():
    # 1.6 m aisle (|y| < 0.8 is free) with a stopped robot hugging the left wall.
    free = lambda x, y: abs(y) < 0.8 - 0.22  # noqa: E731
    p = walker('polite')
    robot = (4.0, 0.45, 0.0)
    furthest = 0.0
    for _ in range(int(30.0 / 0.05)):
        p.step(0.05, robot, (), is_free=free)
        furthest = max(furthest, p.position[0])
        assert footprint_clearance(robot, p.position) >= 0.0
    assert furthest > 5.0


def test_position_never_jumps_even_when_turning_with_an_offset():
    p = walker('polite', route=((0.0, 0.0), (3.0, 0.0)))
    p.offset = 0.9  # e.g. still stepped aside when reaching the route end
    last = p.position
    for _ in range(int(20.0 / 0.05)):
        p.step(0.05)
        here = p.position
        assert math.dist(here, last) <= 1.0 * 0.05 + 0.5 * 0.05 + 1e-6
        last = here


def test_scenario_soak_around_a_parked_robot_has_no_jumps_overlaps_or_gridlock():
    """All scenario people for 3 simulated minutes around a parked robot."""
    grid, meta = _load_map()
    static = StaticMap(grid, meta['resolution'], meta['origin'][0], meta['origin'][1],
                       margin=0.30)

    def is_free(x, y):
        return not bool(static.is_static(np.array([[x, y]]))[0])
    scenario = yaml.safe_load((PACKAGE / 'config' / 'pedestrians.yaml').read_text())
    spots = {  # where the robot really waits: dock, west aisle, kitchen
        'dock': (-3.63, 0.85, -0.522),
        'west_aisle': (-5.74, 4.0, 1.5),
        'kitchen_pose': (0.02, 9.27, 1.049),
    }
    dt = 1.0 / 15.0
    for spot, robot in spots.items():
        people = [Pedestrian(PedestrianConfig.from_dict(d),
                             PedestrianParams(**scenario.get('params', {})))
                  for d in scenario['pedestrians']]
        still = {p.config.name: 0.0 for p in people}
        for _ in range(int(180.0 / dt)):
            for p in people:
                before = p.position
                p.step(dt, robot, [q.position for q in people if q is not p], is_free)
                jump = math.dist(before, p.position)
                assert jump < 0.12, (spot, p.config.name, jump)
                assert footprint_clearance(robot, p.position) >= 0.0, (spot, p.config.name)
                waiting = p.dwell > 0.0 or p.delay > 0.0
                still[p.config.name] = (0.0 if jump > 1e-4 or waiting
                                        else still[p.config.name] + dt)
                assert still[p.config.name] < 30.0, (spot, p.config.name, 'gridlock')


def test_person_overlapping_the_robot_can_always_step_out():
    p = walker('oblivious', route=((0.0, 0.0), (0.0, 5.0)))
    robot = (0.0, -0.2, 0.0)  # the robot ended up overlapping the person
    start = footprint_clearance(robot, p.position)
    assert start < 0.0
    run(p, 3.0, robot)
    assert footprint_clearance(robot, p.position) > start


def test_person_with_no_way_past_turns_back_instead_of_waiting_forever():
    # Aisle exactly blocked: robot across it and no free side lanes.
    free = lambda x, y: abs(y) < 0.05  # noqa: E731
    p = walker('polite', route=((0.0, 0.0), (10.0, 0.0)))
    robot = (4.0, 0.0, math.pi / 2)
    for _ in range(int(25.0 / 0.05)):
        p.step(0.05, robot, (), is_free=free)
    assert p.position[0] < 3.0  # walked back the way they came


def _waypoint_changes(pedestrian, step, seconds, dt=0.05):
    keys = []
    for _ in range(int(seconds / dt)):
        step()
        keys.append((pedestrian.target, pedestrian.direction))
    return sum(1 for a, b in zip(keys, keys[1:]) if a != b)


def test_two_people_stuck_on_each_other_give_way_without_a_robot():
    # Face to face, already closer than person_spacing, in a corridor with
    # no room for a side lane: every move closes the gap. This froze waiter
    # and guest for good in the simulator (the give-way needed a robot).
    free = lambda x, y: abs(y) < 0.25  # noqa: E731
    a = walker('oblivious', route=((0.0, 0.0), (10.0, 0.0)))
    b = walker('polite', route=((3.0, 0.2), (-7.0, 0.2)))
    b.config.name = 'q'  # a different stagger from a

    b_keys = []

    def step():
        a.step(0.05, None, [b.position], free)
        b.step(0.05, None, [a.position], free)
        b_keys.append((b.target, b.direction))
    assert _waypoint_changes(a, step, 60.0) > 0
    assert len(set(b_keys)) > 1


def test_person_behind_a_parked_robot_never_livelocks_at_any_heading():
    # Walking into the robot's rear: a detour lane that dips below the
    # contact margin used to be chosen, refused by the motion check and
    # chosen again, resetting the give-way timer each time, forever.
    for i in range(63):
        yaw = -math.pi + i * 0.1
        p = walker('oblivious', speed=0.5)
        robot = (4.0, 0.12, yaw)
        changes = _waypoint_changes(p, lambda: p.step(0.05, robot, ()), 40.0)
        assert changes > 0, f'stuck behind the robot at yaw {yaw:.1f}'
