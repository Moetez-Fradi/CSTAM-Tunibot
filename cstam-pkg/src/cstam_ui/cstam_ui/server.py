"""HTTP API and static web server for the CSTAM UI (standard library only).

Live updates use Server-Sent Events: browsers reconnect on their own, it
passes through any proxy, and it needs no extra Python dependency on the
robot. Commands are ordinary JSON POSTs.

Public (customer) endpoints:
  GET  /api/health, /api/config, /api/map.png, /api/state
  GET  /api/events[?order=ID]          SSE stream of the public view
  POST /api/orders                     {location, items:[{id, qty}], note}
  GET  /api/orders/ID
  POST /api/orders/ID/cancel           only while the order is still queued
  POST /api/orders/ID/confirm          customer received the order
  GET  /api/qr.svg?text=URL            QR code (black on white) for a page URL
Admin endpoints (PIN in X-Admin-Pin header or ?pin=, when admin_pin is set):
  GET  /api/admin/state, /api/admin/events, /api/admin/history[?limit=N]
  GET  /api/admin/qr                   table page URLs for printed QR cards
  POST /api/admin/orders/ID/cancel     any open order
  POST /api/admin/return_to_dock
"""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
import os
import re
import threading
from urllib.parse import parse_qs, urlparse

from cstam_ui.catalog import find_order
from cstam_ui.qr import QrCode


mimetypes.add_type('font/woff2', '.woff2')

MAX_BODY = 16 * 1024
ANSWER_TIMEOUT_SEC = 3.0   # wait for the task manager to accept or reject
SSE_PERIOD_SEC = 0.25      # at most 4 updates per second per client
SSE_KEEPALIVE_SEC = 15.0
ORDER_PATH = re.compile(r'^/api/(admin/)?orders/([A-Za-z0-9_-]{1,32})(?:/(cancel|confirm))?$')


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class UiServer:
    """Owns the HTTP server; `bridge` sends commands to ROS."""

    def __init__(self, hub, catalog, bridge, web_dir, map_png=None, map_meta=None,
                 admin_pin='', order_log_file=None, host='0.0.0.0', port=8080,
                 public_url=''):
        self.hub, self.catalog, self.bridge = hub, catalog, bridge
        # abspath, not realpath: --symlink-install links each file elsewhere.
        self.web_dir = os.path.abspath(web_dir)
        self.map_png, self.map_meta = map_png, map_meta
        self.admin_pin = admin_pin
        self.order_log_file = order_log_file
        self.public_url = public_url.rstrip('/')
        self.stopping = threading.Event()
        handler = type('Handler', (_Handler,), {'app': self})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.thread = None

    @property
    def port(self):
        return self.httpd.server_address[1]

    def start(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name='cstam_ui_http', daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.httpd.shutdown()
        self.httpd.server_close()

    # ----- order commands --------------------------------------------------

    def _status(self, data):
        return data.get('status')

    def place_order(self, body):
        if not self.hub.get('task_manager_online'):
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, 'the robot is offline')
        try:
            order, total = self.catalog.build_order(body)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from None
        self.bridge.send_order(order)

        def answered(data):
            status = self._status(data) or {}
            rejection = status.get('last_rejection') or {}
            if rejection.get('id') == order['id']:
                return 'rejected', rejection.get('reason')
            found, position = find_order(status, order['id'])
            if found is not None:
                return 'accepted', (found, position)
            return None
        answer = self.hub.wait_for(answered, ANSWER_TIMEOUT_SEC)
        if not answer:
            raise ApiError(HTTPStatus.GATEWAY_TIMEOUT, 'the robot did not answer; try again')
        if answer[0] == 'rejected':
            reason = answer[1] or 'rejected'
            if reason.startswith('duplicate request'):
                reason = 'this table already has an order on the way'
            raise ApiError(HTTPStatus.CONFLICT, reason)
        found, position = answer[1]
        return {'order': found, 'queue_position': position, 'total': total,
                'currency': self.catalog.currency}

    def order_info(self, order_id):
        order, position = find_order(self._status(self.hub.admin_view()), order_id)
        if order is None:
            raise ApiError(HTTPStatus.NOT_FOUND, 'unknown order')
        return {'order': order, 'queue_position': position}

    def cancel_order(self, order_id, admin):
        order = self.order_info(order_id)['order']
        if order['finished_at'] is not None:
            raise ApiError(HTTPStatus.CONFLICT, f'order is already {order["status"]}')
        if not admin and order['status'] != 'queued':
            raise ApiError(HTTPStatus.CONFLICT,
                           'the robot is already on its way; ask a member of staff')
        self.bridge.send_cancel(order_id)
        return self._wait_finished(order_id, 'cancelled')

    def confirm_order(self, order_id):
        order = self.order_info(order_id)['order']
        if order['status'] != 'awaiting_confirmation':
            raise ApiError(HTTPStatus.CONFLICT, 'the robot is not at your table yet')
        self.bridge.send_confirm(order_id)
        return self._wait_finished(order_id, 'delivered')

    def _wait_finished(self, order_id, status):
        def done(data):
            order, _ = find_order(self._status(data), order_id)
            return order if order is not None and order['status'] == status else None
        order = self.hub.wait_for(done, ANSWER_TIMEOUT_SEC)
        if order is None:
            raise ApiError(HTTPStatus.GATEWAY_TIMEOUT, 'the robot did not answer; try again')
        return {'order': order, 'queue_position': None}

    def return_to_dock(self):
        ok, message = self.bridge.return_to_dock(ANSWER_TIMEOUT_SEC)
        if not ok:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, message)
        return {'message': message}

    def history(self, limit):
        """Finished orders from the task manager's JSON-lines log, newest first."""
        orders = []
        if self.order_log_file and os.path.exists(self.order_log_file):
            with open(self.order_log_file, encoding='utf-8') as stream:
                for line in stream:
                    try:
                        orders.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        orders.reverse()
        return {'orders': orders[:limit], 'total': len(orders)}

    def table_links(self):
        base = self.public_url or f'http://localhost:{self.port}'
        return {'base_url': base, 'tables': [
            {**{k: p[k] for k in ('name', 'label', 'zone')}, 'url': f'{base}/table/{p["name"]}'}
            for p in self.catalog.delivery_locations()]}

    def check_pin(self, supplied):
        return not self.admin_pin or hmac.compare_digest(
            (supplied or '').encode(), self.admin_pin.encode())


class _Handler(BaseHTTPRequestHandler):
    app = None  # set per server
    server_version = 'cstam_ui/0.1'
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass  # the ROS logger reports errors; per-request logs are noise

    # ----- helpers ---------------------------------------------------------

    def _send(self, status, body, content_type='application/json', cache=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'max-age=3600' if cache else 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _query(self):
        return {k: v[-1] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _limit(self, default=200, most=1000):
        try:
            return max(1, min(most, int(self._query().get('limit', default))))
        except ValueError:
            raise ApiError(HTTPStatus.BAD_REQUEST, 'limit must be a number') from None

    def _require_admin(self):
        supplied = self.headers.get('X-Admin-Pin') or self._query().get('pin')
        if not self.app.check_pin(supplied):
            raise ApiError(HTTPStatus.UNAUTHORIZED, 'admin PIN required')

    def _body(self):
        """The request's JSON body, read once.

        Every POST must consume its body, even when the route ignores it:
        with keep-alive, unread bytes would prefix the next request.
        """
        if hasattr(self, '_parsed_body'):
            return self._parsed_body
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_BODY:
            self.close_connection = True
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, 'request too large')
        raw = self.rfile.read(length) if length else b''
        self._parsed_body = {}
        if raw:
            try:
                self._parsed_body = json.loads(raw)
            except json.JSONDecodeError:
                raise ApiError(HTTPStatus.BAD_REQUEST, 'body must be JSON') from None
        return self._parsed_body

    def _handle(self, routes):
        path = urlparse(self.path).path
        self.__dict__.pop('_parsed_body', None)   # one handler serves a whole connection
        try:
            if self.command == 'POST':
                self._body()
            for pattern, action in routes:
                match = re.fullmatch(pattern, path)
                if match:
                    return action(*match.groups())
            raise ApiError(HTTPStatus.NOT_FOUND, 'not found')
        except ApiError as error:
            self._send(error.status, {'error': error.message})
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ----- GET -------------------------------------------------------------

    def do_GET(self):
        app = self.app
        self._handle([
            (r'/api/health', lambda: self._send(HTTPStatus.OK, {
                'ok': True, 'online': bool(app.hub.get('task_manager_online'))})),
            (r'/api/config', lambda: self._send(HTTPStatus.OK, {
                **app.catalog.public_config(), 'map': app.map_meta,
                'admin_pin_required': bool(app.admin_pin)})),
            (r'/api/map\.png', self._map),
            (r'/api/qr\.svg', self._qr),
            (r'/api/state', lambda: self._send(
                HTTPStatus.OK, app.hub.public_view(self._query().get('order')))),
            (r'/api/events', lambda: self._events(
                lambda: app.hub.public_view(self._query().get('order')))),
            (r'/api/orders/([A-Za-z0-9_-]{1,32})',
             lambda oid: self._send(HTTPStatus.OK, app.order_info(oid))),
            (r'/api/admin/state', self._admin(lambda: self._send(
                HTTPStatus.OK, app.hub.admin_view()))),
            (r'/api/admin/events', self._admin(lambda: self._events(app.hub.admin_view))),
            (r'/api/admin/qr', self._admin(lambda: self._send(HTTPStatus.OK, app.table_links()))),
            (r'/api/admin/history', self._admin(lambda: self._send(
                HTTPStatus.OK, app.history(self._limit())))),
            (r'/api/.*', self._not_found),
            (r'(/.*)', self._static),
        ])

    do_HEAD = do_GET

    def _admin(self, action):
        def guarded(*args):
            self._require_admin()
            return action(*args)
        return guarded

    def _not_found(self):
        raise ApiError(HTTPStatus.NOT_FOUND, 'not found')

    def _map(self):
        if self.app.map_png is None:
            raise ApiError(HTTPStatus.NOT_FOUND, 'no map loaded')
        self._send(HTTPStatus.OK, self.app.map_png, 'image/png', cache=True)

    def _qr(self):
        text = self._query().get('text', '')
        # Page links only: this is not a general-purpose QR service.
        if not re.fullmatch(r'https?://[^\s]{1,300}', text):
            raise ApiError(HTTPStatus.BAD_REQUEST, 'text must be an http(s) URL')
        self._send(HTTPStatus.OK, QrCode(text, 'M').svg(title=text), 'image/svg+xml', cache=True)

    def _static(self, path):
        relative = path.lstrip('/') or 'index.html'
        if relative.endswith('/'):
            relative += 'index.html'
        full = os.path.normpath(os.path.join(self.app.web_dir, relative))
        if not full.startswith(self.app.web_dir + os.sep) or not os.path.isfile(full):
            if '.' in os.path.basename(relative):
                raise ApiError(HTTPStatus.NOT_FOUND, 'not found')
            # Page routes like /admin or /table/table_3 -> <first segment>.html
            page = relative.split('/')[0] + '.html'
            full = os.path.join(self.app.web_dir, page)
            if not os.path.isfile(full):
                raise ApiError(HTTPStatus.NOT_FOUND, 'not found')
        content_type = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        if content_type.startswith('text/') or content_type.endswith(('javascript', 'json')):
            content_type += '; charset=utf-8'
        with open(full, 'rb') as stream:
            self._send(HTTPStatus.OK, stream.read(), content_type,
                       cache=content_type.startswith('font/'))

    def _events(self, view):
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()
        self.close_connection = True
        hub, stopping = self.app.hub, self.app.stopping
        version = None
        while not stopping.is_set():
            new_version = hub.wait_change(version, SSE_KEEPALIVE_SEC) \
                if version is not None else hub.version
            if new_version == version:
                self.wfile.write(b': keepalive\n\n')
            else:
                version = new_version
                payload = json.dumps(view(), separators=(',', ':'))
                self.wfile.write(f'event: state\ndata: {payload}\n\n'.encode())
            self.wfile.flush()
            stopping.wait(SSE_PERIOD_SEC)

    # ----- POST ------------------------------------------------------------

    def do_POST(self):
        app = self.app
        path = urlparse(self.path).path
        match = ORDER_PATH.match(path)

        def order_action():
            admin, order_id, action = match.groups()
            if admin:
                self._require_admin()
            if action == 'cancel':
                return self._send(HTTPStatus.OK, app.cancel_order(order_id, bool(admin)))
            if action == 'confirm' and not admin:
                return self._send(HTTPStatus.OK, app.confirm_order(order_id))
            raise ApiError(HTTPStatus.NOT_FOUND, 'not found')

        def admin_dock():
            self._require_admin()
            self._send(HTTPStatus.OK, app.return_to_dock())

        self._handle([
            (r'/api/orders', lambda: self._send(
                HTTPStatus.CREATED, app.place_order(self._body()))),
            (ORDER_PATH.pattern[1:-1], lambda *_: order_action()),
            (r'/api/admin/return_to_dock', admin_dock),
        ])
