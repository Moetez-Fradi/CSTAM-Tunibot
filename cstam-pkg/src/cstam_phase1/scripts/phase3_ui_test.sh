#!/usr/bin/env bash
# Phase 3 end-to-end test: a customer order through the web UI.
#
# Launches the headless simulation (with the web UI) in its own process
# group, waits for the startup health check, then acts as a customer and as
# staff over HTTP only: rejected orders, a real order, live tracking, the
# confirmation at the table, the robot docking, and the admin views. The
# physical dock error is measured from Gazebo ground truth.
#
# Usage: [PEDESTRIANS=false] [UI_PORT=8080] [ADMIN_PIN=0000] \
#        phase3_ui_test.sh OUTPUT_DIR [LOCATION]
# Writes OUTPUT_DIR/{launch.log, health.txt, ui_test.json}; exit 0 = PASS.
set -u

OUT="${1:?usage: phase3_ui_test.sh OUTPUT_DIR [LOCATION]}"
LOCATION="${2:-table_1}"
PORT="${UI_PORT:-8080}"
PIN="${ADMIN_PIN:-0000}"
mkdir -p "${OUT}"

PHASE1_SHARE="$(ros2 pkg prefix --share cstam_phase1)"
export FASTDDS_DEFAULT_PROFILES_FILE="${PHASE1_SHARE}/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_DEFAULT_PROFILES_FILE}"

setsid ros2 launch cstam_phase1 phase1.launch.py headless:=True rviz:=false \
  pedestrians:="${PEDESTRIANS:-true}" ui:=true ui_port:="${PORT}" admin_pin:="${PIN}" \
  > "${OUT}/launch.log" 2>&1 &
LAUNCH=$!
cleanup() {
  kill -INT -- "-${LAUNCH}" 2>/dev/null
  sleep 10
  kill -9 -- "-${LAUNCH}" 2>/dev/null
}
trap cleanup EXIT

CSTAM_PHASE1_HEALTH_TIMEOUT=100.0 CSTAM_PHASE1_HARD_TIMEOUT=115 \
  bash "${PHASE1_SHARE}/scripts/phase1_smoke_test.sh" > "${OUT}/health.txt" 2>&1
grep -E "PASS=" "${OUT}/health.txt"

python3 - "${OUT}/ui_test.json" "${LOCATION}" "${PORT}" "${PIN}" \
  "${PHASE1_SHARE}/maps/restaurant" <<'EOF'
import json
import math
import sys
import time
import urllib.error
import urllib.request

import yaml

output, location, port, pin, maps = sys.argv[1:6]
BASE = f'http://127.0.0.1:{port}'
results, failures = [], []
started = time.monotonic()


def check(name, ok, detail=''):
    results.append({'check': name, 'ok': bool(ok), 'detail': detail})
    (print if ok else lambda *a: (print(*a), failures.append(name)))(
        f'{"PASS" if ok else "FAIL"}: {name}{" - " + str(detail) if detail else ""}')
    return ok


def call(path, body=None, admin=None, timeout=20):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method='POST' if data else 'GET')
    request.add_header('Content-Type', 'application/json')
    if admin is not None:
        request.add_header('X-Admin-Pin', admin)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b'null')
    except (urllib.error.URLError, OSError) as error:
        return None, str(error)


def wait(_what, condition, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(1.0)
    return None


def finish():
    summary = {'pass': not failures, 'failures': failures, 'checks': results,
               'elapsed_sec': round(time.monotonic() - started, 1)}
    with open(output, 'w', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2)
    print(f'PASS={sum(r["ok"] for r in results)} FAIL={len(failures)}')
    sys.exit(0 if not failures else 1)


def state():
    status, view = call('/api/state')
    return view if status == 200 and isinstance(view, dict) else {}


online = wait('online', lambda: state().get('online'), 60)
check('web UI up and task manager online', online)
if not online:
    finish()
status, config = call('/api/config')
menu = config.get('menu') or []
check('config lists the table and a menu',
      status == 200 and location in [p['name'] for p in config.get('locations', [])]
      and len(menu) >= 2)

# Invalid orders never reach the robot.
for name, body in [('unknown table', {'location': 'table_99', 'items': [{'id': menu[0]['id']}]}),
                   ('empty order', {'location': location, 'items': []}),
                   ('unknown item', {'location': location, 'items': [{'id': 'nope'}]}),
                   ('quantity too high', {'location': location,
                                          'items': [{'id': menu[0]['id'], 'qty': 99}]})]:
    status, answer = call('/api/orders', body)
    check(f'rejects {name}', status == 400, answer.get('error') if isinstance(answer, dict) else answer)

items = [{'id': menu[0]['id'], 'qty': 2}, {'id': menu[1]['id'], 'qty': 1}]
status, placed = call('/api/orders', {'location': location, 'items': items, 'note': 'UI test'})
order_id = (placed or {}).get('order', {}).get('id') if isinstance(placed, dict) else None
check('order accepted', status == 201 and order_id, placed)
if not order_id:
    finish()
status, duplicate = call('/api/orders', {'location': location, 'items': items})
check('second order for the same table refused', status == 409, duplicate)
status, _ = call('/api/orders/' + order_id + '/confirm', {})
check('confirm before arrival refused', status == 409)

# Follow the order like the table page does, confirm at the table.
seen, confirmed_answer = [], None
deadline = time.monotonic() + 900
while time.monotonic() < deadline:
    status, view = call('/api/orders/' + order_id)
    order = (view or {}).get('order') if status == 200 else None
    if order and (not seen or seen[-1][1] != order['status']):
        seen.append((round(time.monotonic() - started), order['status']))
        print(f'  {seen[-1][0]:5d}s order {order["status"]}', flush=True)
    if order and order['status'] == 'awaiting_confirmation':
        status, confirmed_answer = call('/api/orders/' + order_id + '/confirm', {})
        check('customer confirms at the table', status == 200, confirmed_answer.get('order', {}).get('status'))
    if order and order['status'] in ('delivered', 'failed', 'cancelled'):
        break
    time.sleep(1.0)
statuses = [s for _, s in seen]
check('order went queued/active -> at table -> delivered',
      'awaiting_confirmation' in statuses and statuses[-1:] == ['delivered'], statuses)
check('delivery recorded as confirmed', order and order.get('confirmed'))

docked = wait('docked', lambda: (state().get('robot') or {}).get('state') == 'IDLE', 400)
check('robot back at the dock and IDLE', docked)

status, _ = call('/api/admin/state', admin='9999')
check('admin API refuses a wrong PIN', status == 401)
status, admin = call('/api/admin/state', admin=pin)
admin_status = (admin or {}).get('status') or {}
history = [o for o in admin_status.get('history') or [] if o.get('id') == order_id]
check('admin sees the order in history', status == 200 and history and history[0]['status'] == 'delivered')
dock_error = admin_status.get('dock_error')
check('final docking approach reported its error', dock_error is not None, dock_error)
status, analytics = call('/api/admin/analytics?range=today', admin=pin)
check('analytics count the delivery', status == 200
      and (analytics or {}).get('delivered', 0) >= 1, (analytics or {}).get('delivered'))

# Physical dock error from Gazebo ground truth (not AMCL).
try:
    import rclpy
    from geometry_msgs.msg import PoseStamped
    rclpy.init()
    node = rclpy.create_node('cstam_phase3_ui_test')
    truth = []
    node.create_subscription(PoseStamped, '/model/cstam/pose', truth.append, 10)
    end = time.monotonic() + 10
    while not truth and time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.5)
    with open(f'{maps}/world_alignment.yaml', encoding='utf-8') as stream:
        world = yaml.safe_load(stream)['world_from_map']
    with open(f'{maps}/locations.yaml', encoding='utf-8') as stream:
        dock = yaml.safe_load(stream)['dock']
    if truth:
        p, q = truth[-1].pose.position, truth[-1].pose.orientation
        c, s = math.cos(world['yaw']), math.sin(world['yaw'])
        dx, dy = p.x - world['x'], p.y - world['y']
        x, y = c * dx + s * dy, -s * dx + c * dy
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)) - world['yaw']
        error = math.hypot(x - dock['x'], y - dock['y'])
        yaw_error = abs(math.remainder(yaw - dock['yaw'], math.tau))
        check('physical dock error under 0.10 m / 0.10 rad', error < 0.10 and yaw_error < 0.10,
              f'{error:.3f} m, {yaw_error:.3f} rad')
    else:
        check('ground-truth pose available', False)
    node.destroy_node()
    rclpy.shutdown()
except Exception as error:  # the UI checks above still count
    check('ground-truth dock measurement', False, error)
finish()
EOF
