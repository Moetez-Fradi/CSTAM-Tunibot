"""Lifetime usage of the robot and the maintenance it implies.

Distance, driving time and operating time are integrated from /odom; battery
cycles from /battery/state (cumulative discharge / 100 %). Totals survive
restarts in a JSON file. Each maintenance item in config/maintenance.yaml has
an interval on one of these metrics; usage since its last service gives the
state, and the recent daily usage rate forecasts when it falls due.
"""

from datetime import date, timedelta
import json
import os
import time

import yaml


METRICS = {
    'distance_m': 'distance driven',
    'drive_s': 'driving time',
    'operating_s': 'operating time',
    'battery_cycles': 'battery cycles',
}
MOVING_SPEED = 0.02      # m/s; below this the wheels are considered still
TURNING_SPEED = 0.05     # rad/s
MAX_ODOM_GAP_S = 1.0     # longer gaps (pause, restart) are not integrated
MAX_BATTERY_STEP = 5.0   # %; a larger drop is a manual override, not use
FORECAST_DAYS = 14       # usage rate = average over active days in this window
DUE_SOON = 0.8           # fraction of the interval that counts as "due soon"


def load_schedule(path):
    with open(path, encoding='utf-8') as stream:
        data = yaml.safe_load(stream) or {}
    items = []
    for item in data.get('items') or []:
        if item['metric'] not in METRICS:
            raise ValueError(f'{item["id"]}: unknown metric {item["metric"]}')
        items.append({'id': str(item['id']), 'name': str(item['name']),
                      'metric': item['metric'], 'interval': float(item['interval']),
                      'task': str(item.get('task', ''))})
    return items


class UsageTracker:
    def __init__(self, path, schedule, clock=time.time, today=date.today):
        self.path, self.schedule = path, schedule
        self._clock, self._today = clock, today
        self.totals = {metric: 0.0 for metric in METRICS}
        self.daily = {}          # 'YYYY-MM-DD' -> {metric: amount}
        self.services = {}       # item id -> {'at': time, 'totals': {metric: total}}
        self.since = clock()
        self._last_odom = None
        self._last_battery = None
        self.dirty = False
        self._load()

    # ----- persistence -----------------------------------------------------

    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return
        self.totals.update({k: float(v) for k, v in data.get('totals', {}).items() if k in METRICS})
        self.daily = data.get('daily', {})
        self.services = data.get('services', {})
        self.since = data.get('since', self.since)

    def save(self):
        if not self.dirty:
            return
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as stream:
            json.dump({'totals': self.totals, 'daily': self.daily,
                       'services': self.services, 'since': self.since}, stream)
        os.replace(tmp, self.path)   # never leave a half-written file
        self.dirty = False

    # ----- inputs ----------------------------------------------------------

    def _add(self, metric, amount):
        if amount <= 0:
            return
        self.totals[metric] += amount
        day = self.daily.setdefault(self._today().isoformat(), {})
        day[metric] = day.get(metric, 0.0) + amount
        self.dirty = True

    def odometry(self, stamp, linear, angular):
        """One /odom sample: stamp in seconds, body speeds in m/s and rad/s."""
        last, self._last_odom = self._last_odom, stamp
        if last is None:
            return
        dt = stamp - last
        if not 0.0 < dt <= MAX_ODOM_GAP_S:
            return
        self._add('operating_s', dt)
        self._add('distance_m', abs(linear) * dt)
        if abs(linear) > MOVING_SPEED or abs(angular) > TURNING_SPEED:
            self._add('drive_s', dt)

    def battery(self, percentage, charging):
        last, self._last_battery = self._last_battery, percentage
        if last is None or charging or percentage is None:
            return
        drop = last - percentage
        if 0.0 < drop <= MAX_BATTERY_STEP:
            self._add('battery_cycles', drop / 100.0)

    def record_service(self, item_id):
        if item_id not in {item['id'] for item in self.schedule}:
            raise KeyError(item_id)
        self.services[item_id] = {'at': self._clock(), 'totals': dict(self.totals)}
        self.dirty = True

    # ----- report ----------------------------------------------------------

    def _daily_rate(self, metric):
        """Average use per active day over the recent window (None if idle)."""
        today = self._today()
        amounts = [self.daily.get((today - timedelta(days=d)).isoformat(), {}).get(metric, 0.0)
                   for d in range(FORECAST_DAYS)]
        active = [a for a in amounts if a > 0]
        return sum(active) / len(active) if active else None

    def report(self):
        items = []
        for item in self.schedule:
            metric = item['metric']
            service = self.services.get(item['id'])
            used = self.totals[metric] - (service['totals'].get(metric, 0.0) if service else 0.0)
            fraction = used / item['interval'] if item['interval'] > 0 else 0.0
            remaining = max(0.0, item['interval'] - used)
            rate = self._daily_rate(metric)
            state = 'overdue' if fraction >= 1.0 else 'soon' if fraction >= DUE_SOON else 'ok'
            items.append({
                **item, 'used': round(used, 3), 'fraction': round(fraction, 4),
                'remaining': round(remaining, 3), 'state': state,
                'daily_rate': None if rate is None else round(rate, 3),
                'due_in_days': None if not rate else round(remaining / rate, 1),
                'last_service': service['at'] if service else None,
            })
        return {'totals': {k: round(v, 3) for k, v in self.totals.items()},
                'since': self.since, 'items': items}
