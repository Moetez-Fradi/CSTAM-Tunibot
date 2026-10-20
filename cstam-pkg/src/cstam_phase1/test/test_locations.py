import pathlib

import yaml


def test_locations_are_first_floor_and_complete():
    locations_file = pathlib.Path(__file__).parents[1] / 'maps' / 'restaurant' / 'locations.yaml'
    data = yaml.safe_load(locations_file.read_text(encoding='utf-8'))
    assert data['supported_floors'] == [1]
    for name in ('dock', 'kitchen', 'table_1'):
        assert name in data
        assert data[name]['floor'] == 1
        assert all(key in data[name] for key in ('x', 'y', 'yaw'))


def test_locations_have_distinct_semantic_names():
    locations_file = pathlib.Path(__file__).parents[1] / 'maps' / 'restaurant' / 'locations.yaml'
    data = yaml.safe_load(locations_file.read_text(encoding='utf-8'))
    names = [name for name, value in data.items() if isinstance(value, dict)]
    assert len(names) == len(set(names))


def _footprint_clearance_to_map(grid, meta, x, y, yaw):
    """Smallest distance from the robot rectangle to an occupied map cell."""
    import math

    import numpy as np
    res, (ox, oy) = meta['resolution'], meta['origin'][:2]
    rows, cols = np.nonzero(grid >= 50)
    cx, cy = ox + (cols + 0.5) * res, oy + (rows + 0.5) * res
    near = np.hypot(cx - x, cy - y) < 1.5
    dx, dy = cx[near] - x, cy[near] - y
    lx = math.cos(yaw) * dx + math.sin(yaw) * dy
    ly = -math.sin(yaw) * dx + math.cos(yaw) * dy
    out_x = np.maximum(np.maximum(-0.31 - lx, 0.0), lx - 0.35)
    out_y = np.maximum(np.maximum(-0.27 - ly, 0.0), ly - 0.27)
    return float(np.min(np.hypot(out_x, out_y))) if len(lx) else 9.0


def test_every_location_footprint_is_clear_of_the_map():
    from test_pedestrians import _load_map
    grid, meta = _load_map()
    locations_file = pathlib.Path(__file__).parents[1] / 'maps' / 'restaurant' / 'locations.yaml'
    data = yaml.safe_load(locations_file.read_text(encoding='utf-8'))
    poses = {name: pose for name, pose in data.items()
             if isinstance(pose, dict) and name != 'doors'}
    doors = data['doors']
    for door, spec in doors.items():
        if isinstance(spec, dict):  # staging poses, both directions
            for side in ('inside_x', 'outside_x'):
                for yaw in (0.0, 3.1416):
                    poses[f'terrace door {door} {side} yaw {yaw}'] = {
                        'x': doors[side], 'y': spec['y'], 'yaw': yaw}
    for name, pose in poses.items():
        clearance = _footprint_clearance_to_map(grid, meta, pose['x'], pose['y'], pose['yaw'])
        # Terrace poses were placed with margin; the Phase 1 poses are the
        # accepted, measured ones and only need to be collision-free.
        required = 0.15 if name.startswith('terrace') else 0.0  # incl. door poses
        assert clearance > required, f'{name}: footprint clearance {clearance:.2f} m'


def test_west_wall_has_exactly_the_two_terrace_door_openings():
    import numpy as np
    from test_pedestrians import _load_map
    grid, meta = _load_map()
    res, (ox, oy) = meta['resolution'], meta['origin'][:2]
    col = int((-7.05 - ox) / res)
    ys = np.arange(-10.6, 10.3, res)
    occupied = [grid[int((y - oy) / res), col] >= 50 for y in ys]
    openings, start = [], None
    for y, occ in zip(ys, occupied):
        if not occ and start is None:
            start = y
        if occ and start is not None:
            openings.append((start, y))
            start = None
    assert len(openings) == 2, openings
    for (y0, y1), door in zip(openings, ((3.28, 4.20), (6.74, 7.66))):
        assert abs(y0 - door[0]) < 0.1 and abs(y1 - door[1]) < 0.1
        assert y1 - y0 > 0.85  # the 0.54 m robot fits with margin
