"""Catalog, map conversion, hub and HTTP API checks (no ROS graph needed)."""
from http.client import HTTPConnection
import json
import os
import re
import struct
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib

import pytest

from cstam_ui.catalog import Catalog, find_order
from cstam_ui.hub import StateHub
from cstam_ui.map_image import load_map, read_pgm
from cstam_ui.qr import QrCode
from cstam_ui.server import UiServer


HERE = os.path.dirname(__file__)
PACKAGE = os.path.dirname(HERE)
RESTAURANT = os.path.join(PACKAGE, '..', 'cstam_phase1', 'maps', 'restaurant')
LOCATIONS = os.path.join(RESTAURANT, 'locations.yaml')
MENU = os.path.join(PACKAGE, 'config', 'menu.yaml')


@pytest.fixture
def catalog():
    return Catalog(LOCATIONS, MENU)


# ----- catalog ---------------------------------------------------------------

def test_catalog_offers_tables_and_terrace_but_not_dock_or_kitchen(catalog):
    names = [p['name'] for p in catalog.delivery_locations()]
    assert 'table_1' in names and 'terrace_1' in names
    assert 'dock' not in names and 'kitchen' not in names
    zones = {p['name']: p['zone'] for p in catalog.delivery_locations()}
    assert zones['terrace_1'] == 'terrace' and zones['table_1'] == 'dining room'
    assert {d['name'] for d in catalog.doors} == {'door_a', 'door_b'}


def test_catalog_offers_the_upstairs_tables_and_the_elevator(catalog):
    places = {p['name']: p for p in catalog.delivery_locations()}
    assert places['table_4']['floor'] == 2 and places['table_4']['zone'] == 'upstairs'
    assert places['table_4']['label'] == 'Table 4'
    config = catalog.public_config()
    assert config['elevator']['x'] == 0.91 and catalog.floors == {1, 2}
    assert catalog.floor_maps == {1: 'restaurant.yaml', 2: 'floor2.yaml'}


def test_build_order_merges_lines_and_prices_them(catalog):
    order, total = catalog.build_order({'location': 'Table_2', 'items': [
        {'id': 'espresso', 'qty': 2}, {'id': 'brik', 'qty': 1}, {'id': 'espresso', 'qty': 1}],
        'note': ' extra napkins '})
    assert order['location'] == 'table_2' and order['note'] == 'extra napkins'
    assert order['items'] == [{'name': 'Espresso', 'qty': 3}, {'name': "Brik à l'oeuf", 'qty': 1}]
    assert total == pytest.approx(3 * 3.5 + 5.5)
    assert len(order['id']) == 6


@pytest.mark.parametrize('body, message', [
    ({'location': 'dock', 'items': [{'id': 'water'}]}, 'unknown table'),
    ({'location': 'table_1', 'items': []}, 'at least one item'),
    ({'location': 'table_1', 'items': [{'id': 'pizza'}]}, 'unknown menu item'),
    ({'location': 'table_1', 'items': [{'id': 'water', 'qty': 0}]}, 'quantity'),
    ({'location': 'table_1', 'items': [{'id': 'water', 'qty': 'x'}]}, 'invalid quantity'),
    ({'location': 'table_1', 'items': [{'id': 'water'}], 'note': 'x' * 201}, 'note'),
    ([], 'JSON object'),
])
def test_build_order_rejects_bad_input(catalog, body, message):
    with pytest.raises(ValueError, match=message):
        catalog.build_order(body)


def test_find_order_reports_queue_position():
    status = {'active_order': {'id': 'a'}, 'orders': [{'id': 'b'}, {'id': 'c'}],
              'history': [{'id': 'd'}]}
    assert find_order(status, 'a')[1] == 0
    assert find_order(status, 'c')[1] == 2
    assert find_order(status, 'd') == ({'id': 'd'}, None)
    assert find_order(status, 'zz') == (None, None)


# ----- map -------------------------------------------------------------------

def test_saved_map_converts_to_a_valid_png():
    png, meta = load_map(os.path.join(RESTAURANT, 'restaurant.yaml'))
    width, height, pixels = read_pgm(os.path.join(RESTAURANT, 'restaurant.pgm'))
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    assert struct.unpack('>II', png[16:24]) == (width, height)
    assert meta == {'width': width, 'height': height, 'resolution': 0.05,
                    'origin': [-14.204, -12.882]}
    # Decode IDAT back and compare the first row with the PGM.
    length = struct.unpack('>I', png[33:37])[0]
    raw = zlib.decompress(png[41:41 + length])
    assert raw[0] == 0 and raw[1:1 + width] == pixels[:width]


# ----- hub -------------------------------------------------------------------

def test_hub_samples_battery_history_and_hides_other_orders():
    now = [1000.0]
    hub = StateHub(clock=lambda: now[0])
    for step in range(4):
        hub.update('battery', {'percentage': 90.0 - step, 'charging': False})
        now[0] += 2.0
    assert [p for _, p, _ in hub.admin_view()['battery_history']] == [90.0, 87.0]
    hub.update('status', {'state': 'IDLE', 'queue': ['table_1'],
                          'orders': [{'id': 'x1', 'location': 'table_1'}]})
    public = hub.public_view()
    assert 'orders' not in json.dumps(public) and public['queue_length'] == 1
    assert hub.public_view('x1')['queue_position'] == 1


def test_hub_wait_for_wakes_on_update():
    hub = StateHub()
    threading.Timer(0.05, lambda: hub.update('status', {'state': 'IDLE'})).start()
    assert hub.wait_for(lambda d: d.get('status'), 2.0) == {'state': 'IDLE'}
    assert hub.wait_for(lambda d: d.get('nothing'), 0.05) is None


# ----- HTTP API ----------------------------------------------------------------

class FakeRobot:
    """Plays the task manager's side of the topics, synchronously."""

    def __init__(self, hub):
        self.hub = hub
        self.status = {'state': 'IDLE', 'queue': [], 'orders': [], 'active_order': None,
                       'history': [], 'last_rejection': None}
        self.dock_calls = 0
        hub.update('task_manager_online', True)
        self._publish()

    def _publish(self):
        self.hub.update('status', json.loads(json.dumps(self.status)))

    def send_order(self, order):
        if order['location'] in self.status['queue']:
            self.status['last_rejection'] = {
                'id': order['id'], 'reason': f'duplicate request for "{order["location"]}"'}
        else:
            self.status['queue'].append(order['location'])
            self.status['orders'].append(
                {**order, 'status': 'queued', 'finished_at': None})
        self._publish()

    def start_next(self):
        order = self.status['orders'].pop(0)
        self.status['queue'].pop(0)
        order['status'] = 'awaiting_confirmation'
        self.status['active_order'] = order
        self._publish()

    def send_cancel(self, key):
        for order in self.status['orders']:
            if order['id'] == key:
                self.status['orders'].remove(order)
                self.status['queue'].remove(order['location'])
                self.status['history'].append(
                    {**order, 'status': 'cancelled', 'finished_at': time.time()})
        self._publish()

    def send_confirm(self, key):
        order = self.status['active_order']
        self.status['active_order'] = None
        self.status['history'].append({**order, 'status': 'delivered', 'finished_at': 1.0})
        self._publish()

    def record_service(self, item_id):
        if item_id != 'wheels':
            raise KeyError(item_id)
        report = {'items': [{'id': 'wheels', 'used': 0.0, 'last_service': 1.0}]}
        self.hub.update('maintenance', report)
        return report

    def return_to_dock(self, timeout):
        self.dock_calls += 1
        return True, 'return-to-dock requested'


@pytest.fixture
def api(catalog, tmp_path):
    hub = StateHub()
    robot = FakeRobot(hub)
    log = tmp_path / 'orders.jsonl'
    now = time.time()
    log.write_text(''.join(json.dumps({
        'id': f'h{i}', 'status': 'delivered', 'location': 'table_1', 'created_at': now - 60,
        'arrived_at': now - 10, 'items': [{'name': 'Espresso', 'qty': 1}]}) + '\n'
                           for i in range(3)) + 'not json\n')
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'index.html').write_text('<h1>home</h1>')
    (web / 'admin.html').write_text('<h1>admin</h1>')
    (tmp_path / 'built.css').write_text('body{}')
    (web / 'style.css').symlink_to(tmp_path / 'built.css')   # as --symlink-install does
    (web / 'fonts').mkdir()
    (web / 'fonts' / 'geist.woff2').write_bytes(b'wOF2')
    png, meta = load_map(os.path.join(RESTAURANT, 'restaurant.yaml'))
    server = UiServer(hub, catalog, robot, str(web), png, meta, admin_pin='4321',
                      order_log_file=str(log), host='127.0.0.1', port=0,
                      public_url='http://10.0.0.7:8080/',
                      floor_maps={2: load_map(os.path.join(RESTAURANT, 'floor2.yaml'))})
    server.start()
    base = f'http://127.0.0.1:{server.port}'

    def call(method, path, body=None, pin=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(base + path, data=data, method=method)
        request.add_header('Content-Type', 'application/json')
        if pin:
            request.add_header('X-Admin-Pin', pin)
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read()
                kind = response.headers['Content-Type']
                return response.status, json.loads(raw) if 'json' in kind else raw
        except HTTPError as error:
            return error.code, json.loads(error.read())
    yield call, robot, base
    server.stop()


def test_order_round_trip_with_cancel_and_confirm(api):
    call, robot, _ = api
    status, body = call('POST', '/api/orders', {
        'location': 'table_1', 'items': [{'id': 'cappuccino', 'qty': 2}]})
    assert status == 201 and body['queue_position'] == 1 and body['total'] == 10.0
    first = body['order']['id']
    status, body = call('POST', '/api/orders', {'location': 'table_1', 'items': [{'id': 'water'}]})
    assert status == 409 and 'already has an order' in body['error']
    status, body = call('POST', '/api/orders', {'location': 'table_2', 'items': [{'id': 'water'}]})
    second = body['order']['id']
    assert call('GET', f'/api/orders/{second}')[1]['queue_position'] == 2

    status, body = call('POST', f'/api/orders/{second}/cancel')
    assert status == 200 and body['order']['status'] == 'cancelled'
    status, body = call('POST', f'/api/orders/{first}/confirm')
    assert status == 409                                     # not at the table yet
    robot.start_next()
    status, body = call('POST', f'/api/orders/{first}/cancel')
    assert status == 409 and 'staff' in body['error']        # customers cannot stop the robot
    status, body = call('POST', f'/api/orders/{first}/confirm')
    assert status == 200 and body['order']['status'] == 'delivered'
    assert call('GET', '/api/orders/nope')[0] == 404


def test_invalid_order_and_offline_robot(api):
    call, robot, _ = api
    status, body = call('POST', '/api/orders', {'location': 'kitchen', 'items': [{'id': 'water'}]})
    assert status == 400 and 'unknown table' in body['error']
    robot.hub.update('task_manager_online', False)
    status, body = call('POST', '/api/orders', {'location': 'table_1', 'items': [{'id': 'water'}]})
    assert status == 503


def test_admin_endpoints_need_the_pin(api):
    call, robot, _ = api
    assert call('GET', '/api/admin/state')[0] == 401
    assert call('POST', '/api/admin/return_to_dock', pin='0000')[0] == 401
    status, body = call('POST', '/api/admin/return_to_dock', pin='4321')
    assert status == 200 and robot.dock_calls == 1
    status, body = call('GET', '/api/admin/history?limit=2', pin='4321')
    assert [o['id'] for o in body['orders']] == ['h2', 'h1'] and body['total'] == 3
    assert call('GET', '/api/admin/history?limit=x', pin='4321')[0] == 400
    status, body = call('GET', '/api/admin/state', pin='4321')
    assert body['online'] and body['status']['state'] == 'IDLE'


def test_config_map_and_pages(api):
    call, _, base = api
    status, config = call('GET', '/api/config')
    assert status == 200 and config['admin_pin_required'] and config['map']['resolution'] == 0.05
    assert any(item['id'] == 'espresso' for item in config['menu'])
    status, png = call('GET', '/api/map.png')
    assert status == 200 and png.startswith(b'\x89PNG')
    assert call('GET', '/')[1] == b'<h1>home</h1>'
    assert call('GET', '/admin')[1] == b'<h1>admin</h1>'
    assert call('GET', '/style.css')[1] == b'body{}'
    assert call('GET', '/../setup.py')[0] == 404
    assert call('GET', '/missing.js')[0] == 404
    assert call('GET', '/api/unknown')[0] == 404


def test_events_stream_pushes_the_public_view(api):
    _, robot, base = api
    with urlopen(base + '/api/events', timeout=5) as stream:
        assert stream.headers['Content-Type'] == 'text/event-stream'
        assert stream.readline() == b'event: state\n'
        first = json.loads(stream.readline()[len(b'data: '):])
        assert first['robot']['state'] == 'IDLE' and first['online']
        stream.readline()
        robot.status['state'] = 'NAVIGATING_TO_PICKUP'
        robot._publish()
        assert stream.readline() == b'event: state\n'
        update = json.loads(stream.readline()[len(b'data: '):])
        assert update['robot']['state'] == 'NAVIGATING_TO_PICKUP'


def test_keep_alive_survives_a_post_whose_body_the_route_ignores(api):
    call, robot, base = api
    status, body = call('POST', '/api/orders', {'location': 'table_1', 'items': [{'id': 'water'}]})
    order_id = body['order']['id']
    robot.start_next()
    connection = HTTPConnection(base.split('//')[1], timeout=5)
    connection.request('POST', f'/api/orders/{order_id}/confirm', body='{}',
                       headers={'Content-Type': 'application/json'})
    assert connection.getresponse().read() and True
    connection.request('GET', '/api/health')   # same socket
    response = connection.getresponse()
    assert response.status == 200 and json.loads(response.read())['ok']
    connection.close()


# ----- QR codes ------------------------------------------------------------------

def test_table_qr_codes_decode_to_their_urls():
    cv2 = pytest.importorskip('cv2')
    np = pytest.importorskip('numpy')
    detector = cv2.QRCodeDetector()

    def decode(code):
        base = np.pad(np.where(np.array(code.modules), 0, 255).astype(np.uint8), 4,
                      constant_values=255)
        for scale in (8, 5, 11):
            image = cv2.resize(base, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
            text, _, _ = detector.detectAndDecode(image)
            if text:
                return text
        return ''
    for name in ('table_1', 'table_2', 'table_3', 'terrace_1', 'terrace_2'):
        for base in ('http://192.168.1.23:8080', 'http://cstam-robot.local:8080'):
            url = f'{base}/table/{name}'
            code = QrCode(url, 'M')
            assert decode(code) == url, (url, code.version, code.mask)


def test_qr_structure_and_capacity():
    code = QrCode('http://192.168.1.23:8080/table/terrace_2', 'M')
    assert code.version == 3 and code.size == 29            # 40 bytes fit version 3-M
    for x, y in ((0, 0), (code.size - 7, 0), (0, code.size - 7)):   # finder corners dark
        assert code.modules[y][x]
    assert code.modules[code.size - 8][8]                   # the always-dark module
    # Byte-mode capacities from the standard: 1-M holds 14 bytes, 40-L 2953.
    assert QrCode('x' * 14, 'M').version == 1 and QrCode('x' * 15, 'M').version == 2
    assert QrCode('x' * 2953, 'L').version == 40
    with pytest.raises(ValueError):
        QrCode('x' * 2954, 'L')


def test_qr_endpoints(api):
    call, _, base = api
    with urlopen(base + '/api/qr.svg?text=' + 'http%3A%2F%2F10.0.0.7%3A8080%2Ftable%2Ftable_1') as r:
        assert r.headers['Content-Type'] == 'image/svg+xml'
        assert r.read().startswith(b'<svg')
    assert call('GET', '/api/qr.svg?text=hello')[0] == 400
    assert call('GET', '/api/admin/qr')[0] == 401
    status, body = call('GET', '/api/admin/qr', pin='4321')
    assert body['base_url'] == 'http://10.0.0.7:8080'
    assert {'name': 'table_1', 'label': 'Table 1', 'zone': 'dining room',
            'url': 'http://10.0.0.7:8080/table/table_1'} in body['tables']


def test_bundled_fonts_are_served_as_woff2(api):
    _, _, base = api
    with urlopen(base + '/fonts/geist.woff2') as r:
        assert r.headers['Content-Type'] == 'font/woff2'
        assert 'max-age' in r.headers['Cache-Control']


def test_style_sheet_uses_only_bundled_fonts():
    css = open(os.path.join(PACKAGE, 'web', 'style.css'), encoding='utf-8').read()
    assert 'googleapis' not in css
    for url in re.findall(r"url\('/fonts/([^']+)'\)", css):
        assert os.path.isfile(os.path.join(PACKAGE, 'web', 'fonts', url)), url


def test_analytics_and_maintenance_endpoints(api):
    call, robot, _ = api
    assert call('GET', '/api/admin/analytics')[0] == 401
    status, report = call('GET', '/api/admin/analytics?range=all', pin='4321')
    assert status == 200 and report['currency'] == 'TND' and report['delivered'] == 3
    assert report['labels']['table_1'] == 'Table 1'
    assert call('GET', '/api/admin/analytics?range=year', pin='4321')[0] == 400
    assert call('GET', '/api/admin/maintenance', pin='4321')[0] == 503   # not tracked yet
    status, body = call('POST', '/api/admin/maintenance/wheels/service', {}, pin='4321')
    assert status == 200 and body['items'][0]['used'] == 0.0
    assert call('GET', '/api/admin/maintenance', pin='4321')[1] == body
    assert call('POST', '/api/admin/maintenance/wings/service', {}, pin='4321')[0] == 404
    assert call('POST', '/api/admin/maintenance/wheels/service', {})[0] == 401


def test_voice_endpoint(api):
    call, _, _ = api
    status, body = call('POST', '/api/voice', {'text': 'deux cafés pour la table 2'})
    assert status == 200 and body['location'] == 'table_2'
    assert body['items'] == [{'id': 'espresso', 'name': 'Espresso', 'qty': 2}]
    assert call('POST', '/api/voice', {'text': ''})[0] == 400
    assert call('POST', '/api/voice', {'text': 'x' * 301})[0] == 400


def test_menu_is_translated_for_the_customer_page(catalog):
    config = catalog.public_config()
    for item in config['menu']:
        assert item['names'].get('fr') and item['names'].get('ar'), item['id']
    for name in {item['category'] for item in config['menu']}:
        assert set(config['categories'][name]) >= {'fr', 'ar'}, name


def test_page_wording_has_every_key_in_every_language():
    source = open(os.path.join(PACKAGE, 'web', 'i18n.js'), encoding='utf-8').read()
    strings = source[source.index('const STRINGS'):source.index('const SERVER')]
    blocks = re.split(r'^    (en|fr|ar): \{$', strings, flags=re.M)[1:]
    keys = {lang: set(re.findall(r'(?:^      |, )(\w+): ', body, flags=re.M))
            for lang, body in zip(blocks[::2], blocks[1::2])}
    assert set(keys) == {'en', 'fr', 'ar'} and len(keys['en']) > 60
    assert keys['fr'] == keys['en'] and keys['ar'] == keys['en']
    page = open(os.path.join(PACKAGE, 'web', 'table.js'), encoding='utf-8').read()
    for used in set(re.findall(r"\bt\('(\w+)'", page)):
        assert used in keys['en'], used


def test_each_floor_has_its_map(api):
    call, _, _ = api
    status, config = call('GET', '/api/config')
    assert set(config['maps']) == {'1', '2'} and config['maps']['1'] == config['map']
    assert config['maps']['2']['origin'] != config['maps']['1']['origin']
    one, two = call('GET', '/api/map.png')[1], call('GET', '/api/map.png?floor=2')[1]
    assert one.startswith(b'\x89PNG') and two.startswith(b'\x89PNG') and one != two
    assert call('GET', '/api/map.png?floor=3')[0] == 404
    assert call('GET', '/api/map.png?floor=x')[0] == 400
