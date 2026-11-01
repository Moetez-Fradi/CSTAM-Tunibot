"""VIP recognition: colour, position, table, and queue priority."""
import json
import pathlib
import time
from types import SimpleNamespace

import numpy as np

from cstam_phase1.vip_detector import find_badges, load_tables, locate, nearest_table

PACKAGE = pathlib.Path(__file__).parents[1]
LOCATIONS = PACKAGE / 'maps' / 'restaurant' / 'locations.yaml'
FX = FY = 554.3   # 640 px over 1.047 rad
CX, CY = 320.0, 240.0


def _scene(marker_id=7, side=80, at=(400, 200), mirror=False):
    """A grey camera image with one ArUco badge (white quiet zone) pasted in."""
    import cv2
    image = np.full((480, 640), 120, dtype=np.uint8)
    marker = cv2.aruco.drawMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), marker_id, side)
    if mirror:
        marker = marker[:, ::-1]
    q = side // 6
    badge = np.full((side + 2 * q, side + 2 * q), 255, dtype=np.uint8)
    badge[q:-q, q:-q] = marker
    u, v = at
    image[v:v + badge.shape[0], u:u + badge.shape[1]] = badge
    return image, (u + q + side / 2, v + q + side / 2)


def test_only_the_vip_badge_is_recognised():
    image, centre = _scene()
    badges = find_badges(image, 7)
    assert len(badges) == 1
    assert np.allclose(badges[0].mean(axis=0), centre, atol=1.5)
    assert find_badges(_scene(marker_id=9)[0], 7) == []         # someone else's badge
    assert find_badges(_scene(mirror=True)[0], 7) == []          # not a valid id-7 badge
    assert find_badges(_scene(side=12)[0], 7, min_side_px=14) == []   # too far to trust
    assert find_badges(np.full((480, 640), 120, dtype=np.uint8), 7) == []
    # The badge image the simulator puts on the VIP decodes as their id.
    import cv2
    badge = cv2.imread(str(PACKAGE / 'config' / 'vip_badge.png'), cv2.IMREAD_GRAYSCALE)
    canvas = np.full((480, 640), 120, dtype=np.uint8)
    canvas[100:100 + badge.shape[0], 100:100 + badge.shape[1]] = badge
    assert len(find_badges(canvas, 7)) == 1


def test_vip_is_located_from_badge_and_depth():
    image, (u, v) = _scene()
    quad = find_badges(image, 7)[0]
    depth = np.full((480, 640), np.inf, dtype=np.float32)
    depth[150:320, 380:520] = 3.0
    x, y, z = locate(quad, depth, FX, FY, CX, CY)
    assert abs(z - 3.0 - 0.19) < 0.01                 # pushed to the body centre
    assert abs(x - (u - CX) / FX * z) < 0.02 and x > 0   # to the right in the optical frame
    assert locate(quad, np.full_like(depth, np.nan), FX, FY, CX, CY) is None


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
