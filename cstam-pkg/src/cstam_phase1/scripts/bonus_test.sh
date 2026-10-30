#!/usr/bin/env bash
# End-to-end test of the two bonus features over the web API only:
# VIP recognition (camera) with queue priority, and the elevator to the
# upper dining room.
#
# Launches the headless simulation with the scenario pedestrians (the VIP
# among them), waits for the health check, then:
#   1. orders to table 2: the robot serves it facing the VIP, who stands on
#      the far side of that table, and must recognise them there (the
#      position is compared with Gazebo ground truth);
#   2. orders table 1, table 3 and table 2 at once: table 2 (the VIP's) must
#      be served before table 3, which was ordered first;
#   3. orders to table 4 upstairs: the robot must ride up, deliver, ride
#      down and dock.
#
# Usage: [UI_PORT=8080] [ADMIN_PIN=0000] bonus_test.sh OUTPUT_DIR
# Writes OUTPUT_DIR/{launch.log, health.txt, bonus_test.json}; exit 0 = PASS.
set -u

OUT="${1:?usage: bonus_test.sh OUTPUT_DIR}"
PORT="${UI_PORT:-8080}"
PIN="${ADMIN_PIN:-0000}"
mkdir -p "${OUT}"

PHASE1_SHARE="$(ros2 pkg prefix --share cstam_phase1)"
export FASTDDS_DEFAULT_PROFILES_FILE="${PHASE1_SHARE}/config/fastdds_udp.xml"
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_DEFAULT_PROFILES_FILE}"

setsid ros2 launch cstam_phase1 phase1.launch.py headless:=True rviz:=false \
  ui:=true ui_port:="${PORT}" admin_pin:="${PIN}" > "${OUT}/launch.log" 2>&1 &
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

python3 - "${OUT}/bonus_test.json" "${PORT}" "${PIN}" <<'EOF'
import json
import math
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

import rclpy
from std_msgs.msg import String

output, port, pin = sys.argv[1:4]
BASE = f'http://127.0.0.1:{port}'
results, failures = [], []
started = time.monotonic()

# Ground truth of the people, to score where the camera put the VIP.
rclpy.init()
node = rclpy.create_node('cstam_bonus_test')
truth, vip_samples = {}, []


def on_sighting(message):
    sighting = json.loads(message.data)
    if sighting.get('visible') and 'guest_vip' in truth:
        gx, gy = truth['guest_vip']
        vip_samples.append(math.hypot(sighting['x'] - gx, sighting['y'] - gy))


node.create_subscription(String, '/pedestrians/state', lambda m: truth.update(json.loads(m.data)), 10)
node.create_subscription(String, '/vip/status', on_sighting, 10)
threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()


def check(name, ok, detail=''):
    results.append({'check': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        failures.append(name)
    print(f'{"PASS" if ok else "FAIL"}: {name}{" - " + str(detail) if detail != "" else ""}', flush=True)
    return ok


def call(path, body=None, admin=False, timeout=20):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method='POST' if data else 'GET')
    request.add_header('Content-Type', 'application/json')
    if admin:
        request.add_header('X-Admin-Pin', pin)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b'null')
    except (urllib.error.URLError, OSError) as error:
        return None, str(error)


def status():
    code, view = call('/api/admin/state', admin=True)
    return (view or {}).get('status') or {} if code == 200 else {}


def finish():
    summary = {'pass': not failures, 'failures': failures, 'checks': results,
               'elapsed_sec': round(time.monotonic() - started, 1)}
    with open(output, 'w', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2)
    print(f'PASS={sum(r["ok"] for r in results)} FAIL={len(failures)}')
    sys.exit(0 if not failures else 1)


floors_seen = set()


def watch():
    """Record the robot's floor."""
    s = status()
    floors_seen.add(s.get('floor', 1))
    return s


def order(location):
    code, placed = call('/api/orders', {'location': location, 'items': [{'id': 'espresso', 'qty': 1}]})
    return (placed or {}).get('order', {}).get('id') if code == 201 else None


def follow(order_ids, timeout):
    """Confirm each order at its table; return {id: order} once all are finished."""
    finished, deadline = {}, time.monotonic() + timeout
    while time.monotonic() < deadline and len(finished) < len(order_ids):
        watch()
        for oid in order_ids:
            if oid in finished:
                continue
            code, view = call(f'/api/orders/{oid}')
            o = (view or {}).get('order') if code == 200 else None
            if o and o['status'] == 'awaiting_confirmation':
                call(f'/api/orders/{oid}/confirm', {})
            elif o and o['status'] in ('delivered', 'failed', 'cancelled'):
                finished[oid] = o
        time.sleep(1.0)
    return finished


end = time.monotonic() + 60
while time.monotonic() < end and not status().get('state'):
    time.sleep(1.0)
check('robot online', status().get('state'))

# 1. The VIP is recognised at table 2 ---------------------------------------
first = order('table_2')
done = follow([first], 600) if first else {}
check('table 2 delivered', done.get(first, {}).get('status') == 'delivered')
vip = status().get('vip')
check('VIP recognised at table 2 by the camera', vip and vip.get('table') == 'table_2', vip)
check('VIP sightings scored against ground truth', vip_samples, len(vip_samples))
if vip_samples:
    check('VIP position within 0.5 m of ground truth (median)',
          statistics.median(vip_samples) < 0.5,
          f'median {statistics.median(vip_samples):.2f} m over {len(vip_samples)} samples')

# 2. Their next order jumps the queue ------------------------------------------
ids = {name: order(name) for name in ('table_1', 'table_3', 'table_2')}
check('three orders accepted', all(ids.values()), ids)
time.sleep(2.0)
s = status()
queue = [o['location'] for o in s.get('orders') or []]
check('VIP table queued ahead of table 3', queue.index('table_2') < queue.index('table_3')
      if 'table_2' in queue and 'table_3' in queue else s.get('current_location') == 'table_2', queue)
done = follow([i for i in ids.values() if i], 1500)
starts = {name: (done.get(oid) or {}).get('started_at') for name, oid in ids.items()}
check('all three delivered', all((done.get(oid) or {}).get('status') == 'delivered' for oid in ids.values()))
check('VIP order served before table 3', starts['table_2'] and starts['table_3']
      and starts['table_2'] < starts['table_3'], starts)
check('VIP order marked VIP', (done.get(ids['table_2']) or {}).get('vip'))

# 3. Upstairs by the elevator -----------------------------------------------------
floors_seen.clear()
up = order('table_4')
t0 = time.monotonic()
done = follow([up], 900) if up else {}
check('table 4 (upstairs) delivered', done.get(up, {}).get('status') == 'delivered',
      f'{time.monotonic() - t0:.0f} s order to delivered')
check('robot rode to floor 2', 2 in floors_seen, sorted(floors_seen))
end = time.monotonic() + 600
while time.monotonic() < end and not (status().get('state') == 'IDLE' and status().get('floor') == 1):
    watch()
    time.sleep(1.0)
s = status()
check('back at the dock on floor 1', s.get('state') == 'IDLE' and s.get('floor') == 1,
      f'{s.get("state")} floor {s.get("floor")}, dock error {s.get("dock_error")}')
finish()
EOF
