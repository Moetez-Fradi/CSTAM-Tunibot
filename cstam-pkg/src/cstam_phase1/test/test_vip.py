"""VIP recognition: colour, position, table, and queue priority."""
import json
import math
import pathlib
import time
from types import SimpleNamespace

import numpy as np
import yaml

from cstam_phase1.vip_detector import load_tables, locate, nearest_table, vip_mask

PACKAGE = pathlib.Path(__file__).parents[1]
LOCATIONS = PACKAGE / 'maps' / 'restaurant' / 'locations.yaml'
FX = FY = 554.3   # 640 px over 1.047 rad
CX, CY = 320.0, 240.0


def test_only_the_vip_jacket_matches():
    scenario = yaml.safe_load((PACKAGE / 'config' / 'pedestrians.yaml').read_text())
    vip = [p for p in scenario['pedestrians'] if p.get('vip')]
    assert len(vip) == 1
    others = [p['color'] for p in scenario['pedestrians'] if not p.get('vip')]
    # Rendered shirts at full and at half light, plus the table plaque colours.
    plaques = [(1, 0.78, 0.18), (0.25, 0.85, 1), (1, 0.36, 0.30), (0.35, 1, 0.5), (1, 0.92, 0.6)]
    samples = [tuple(int(255 * c * k) for c in col) for col in others + plaques for k in (1.0, 0.5)]
    image = np.array([samples], dtype=np.uint8)
    assert not vip_mask(image).any()
    jacket = np.array([[[255, 26, 191]]], dtype=np.uint8)
    assert vip_mask(jacket).all()


def test_vip_is_located_from_mask_and_depth():
    mask = np.zeros((480, 640), dtype=bool)
    depth = np.full((480, 640), np.inf, dtype=np.float32)
    mask[200:280, 400:440] = True      # torso right of the image centre
    depth[200:280, 400:440] = 3.0
    x, y, z = locate(mask, depth, FX, FY, CX, CY)
    u = 419.5
    assert abs(z - 3.0 - 0.19) < 0.01                 # pushed to the body centre
    assert abs(x - (u - CX) / FX * z) < 0.02 and x > 0   # to the right in the optical frame
    assert locate(mask & False, depth, FX, FY, CX, CY) is None
    assert locate(mask, np.full_like(depth, np.nan), FX, FY, CX, CY) is None


def test_sighting_is_matched_to_the_nearest_table():
    tables = load_tables(str(LOCATIONS))
    assert set(tables) == {'table_1', 'table_2', 'table_3'}   # floor 1 only
    # Where the scenario VIP stands: east of table 2.
    assert nearest_table(tables, -2.75, 1.99, 1.6) == 'table_2'
    assert nearest_table(tables, 3.0, 8.0, 1.6) is None
    upstairs = load_tables(str(LOCATIONS), floor=2)
    assert set(upstairs) == {'table_4', 'table_5'}


def _manager_with_queue(*locations):
    from test_delivery_control import manager
    node = manager()
    node.state = 'NAVIGATING_TO_PICKUP'
    node.goal_request_pending = True
    for location in locations:
        node.orders[location] = node._new_order(location)
        node.queue.append(location)
    return node


def _sighting(table, age=0.0):
    return SimpleNamespace(data=json.dumps({
        'visible': True, 'table': table, 'last_seen': time.time() - age, 'x': -2.75, 'y': 1.99}))


def test_vip_table_moves_to_the_front_of_the_queue():
    node = _manager_with_queue('table_1', 'table_3', 'table_2')
    node._vip_callback(_sighting('table_2'))
    assert list(node.queue) == ['table_2', 'table_1', 'table_3']
    assert node.orders['table_2']['vip'] and node.events[-1] == 'VIP at table_2: their order goes first'
    assert node._status_payload()['vip']['table'] == 'table_2'


def test_vip_order_placed_later_also_goes_first():
    node = _manager_with_queue('table_1', 'table_3')
    node._vip_callback(_sighting('table_2'))   # seen before they order
    assert list(node.queue) == ['table_1', 'table_3']
    node.orders['table_2'] = node._new_order('table_2')
    node.queue.append('table_2')
    node._prioritise_vip()
    assert list(node.queue)[0] == 'table_2'


def test_an_interrupted_order_keeps_its_promised_place():
    node = _manager_with_queue('table_1', 'table_3', 'table_2')
    node.orders['table_1']['interruptions'] = 1
    node._vip_callback(_sighting('table_2'))
    assert list(node.queue) == ['table_1', 'table_2', 'table_3']


def test_an_old_sighting_gives_no_priority():
    node = _manager_with_queue('table_1', 'table_2')
    node._vip_callback(_sighting('table_2', age=3600))
    assert list(node.queue) == ['table_1', 'table_2']
    assert node._status_payload()['vip'] is None
