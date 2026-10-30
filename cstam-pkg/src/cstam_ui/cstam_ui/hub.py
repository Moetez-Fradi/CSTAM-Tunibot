"""Thread-safe latest-value store shared by the ROS node and the web server.

The ROS executor thread writes (status, battery, pose, plan, people, ...);
HTTP threads read snapshots and block on changes for Server-Sent Events.
"""

from collections import deque
import threading
import time

from cstam_ui.catalog import find_order


BATTERY_SAMPLE_SEC = 5.0


class StateHub:
    def __init__(self, battery_history_sec=1800.0, clock=time.time):
        self._clock = clock
        self._cond = threading.Condition()
        self._version = 0
        self._data = {}
        self._updated = {}
        self._battery_history = deque(
            maxlen=max(1, int(battery_history_sec / BATTERY_SAMPLE_SEC)))

    @property
    def version(self):
        with self._cond:
            return self._version

    def update(self, key, value):
        with self._cond:
            now = self._clock()
            self._data[key] = value
            self._updated[key] = now
            if key == 'battery' and value is not None and value.get('percentage') is not None:
                last = self._battery_history[-1] if self._battery_history else None
                if last is None or now - last[0] >= BATTERY_SAMPLE_SEC:
                    self._battery_history.append(
                        (round(now, 1), value['percentage'], bool(value.get('charging'))))
            self._version += 1
            self._cond.notify_all()

    def get(self, key, default=None):
        with self._cond:
            return self._data.get(key, default)

    def wait_change(self, version, timeout):
        """Block until the version moves past `version`; return the new version."""
        with self._cond:
            self._cond.wait_for(lambda: self._version != version, timeout)
            return self._version

    def wait_for(self, predicate, timeout):
        """Block until predicate(data) returns something truthy (or timeout)."""
        end = time.monotonic() + timeout
        with self._cond:
            while True:
                result = predicate(self._data)
                remaining = end - time.monotonic()
                if result or remaining <= 0:
                    return result
                self._cond.wait(remaining)

    # ----- views -----------------------------------------------------------

    def _ages(self, now):
        return {key: round(now - stamp, 1) for key, stamp in self._updated.items()}

    def public_view(self, order_id=None):
        """What any customer device may see: the robot, not other orders."""
        with self._cond:
            now = self._clock()
            status = self._data.get('status') or {}
            battery = self._data.get('battery') or {}
            view = {
                'server_time': now,
                'online': bool(self._data.get('task_manager_online')),
                'robot': {
                    'state': status.get('state'),
                    'stage': status.get('current_stage'),
                    'floor': status.get('floor', 1),
                    'message': status.get('message'),
                    'progress': status.get('progress'),
                    'pose': self._data.get('pose'),
                    'battery': {'percentage': battery.get('percentage'),
                                'charging': battery.get('charging')},
                },
                'queue_length': len(status.get('queue') or []),
                'plan': self._data.get('plan'),
            }
            if order_id is not None:
                order, position = find_order(status, order_id)
                view['order'] = order
                view['queue_position'] = position
            return view

    def admin_view(self):
        with self._cond:
            now = self._clock()
            view = {key: value for key, value in self._data.items()}
            view['server_time'] = now
            view['ages'] = self._ages(now)
            view['battery_history'] = list(self._battery_history)
            view['online'] = bool(self._data.get('task_manager_online'))
            return view
