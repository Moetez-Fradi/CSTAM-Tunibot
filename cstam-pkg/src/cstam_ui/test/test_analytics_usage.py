"""Order analytics and maintenance usage tracking (no ROS graph needed)."""
from datetime import date, datetime, timedelta
import json
import os

import pytest

from cstam_ui import analytics
from cstam_ui.usage import load_schedule, UsageTracker


PACKAGE = os.path.dirname(os.path.dirname(__file__))
SCHEDULE = os.path.join(PACKAGE, 'config', 'maintenance.yaml')
NOW = datetime(2026, 10, 26, 15, 30).timestamp()
PRICES = {'Espresso': 3.5, 'Brik': 5.5}


def order(status, minutes_ago, location='table_1', items=(('Espresso', 2),), to_table=60.0,
          confirmed=True, battery=(90.0, 84.0), days_ago=0):
    created = NOW - days_ago * 86400 - minutes_ago * 60
    return {'id': f'{status}{minutes_ago}{days_ago}', 'status': status, 'location': location,
            'items': [{'name': n, 'qty': q} for n, q in items], 'created_at': created,
            'started_at': created + 5, 'arrived_at': created + to_table if status == 'delivered' else None,
            'finished_at': created + to_table + 10, 'confirmed': confirmed and status == 'delivered',
            'battery_start': battery[0], 'battery_end': battery[1]}


# ----- analytics -----------------------------------------------------------------

def test_today_summary():
    orders = [
        order('delivered', 30, items=(('Espresso', 2), ('Brik', 1)), to_table=50),
        order('delivered', 90, location='table_2', to_table=70, confirmed=False, battery=(84, 80)),
        order('delivered', 95, location='table_2', to_table=90, battery=(40, 85)),  # charged
        order('failed', 20, location='terrace_1'),
        order('cancelled', 10),
        order('delivered', 0, days_ago=2),          # not today
    ]
    report = analytics.summarize(orders, PRICES, 'today', now=NOW)
    assert (report['orders'], report['delivered'], report['failed'], report['cancelled']) == (5, 3, 1, 1)
    assert report['success_rate'] == 0.75
    assert report['confirmed_rate'] == pytest.approx(2 / 3, abs=1e-3)
    assert report['time_to_table']['median'] == 70
    assert report['revenue'] == 2 * 3.5 + 5.5 + 2 * 3.5 + 2 * 3.5
    assert report['battery_per_delivery'] == 5.0         # (6 + 4) / 2; charged order skipped
    assert report['deliveries_per_charge'] == 20.0
    assert report['top_items'][0] == {'name': 'Espresso', 'qty': 6}
    assert report['tables'][0] == {'location': 'table_2', 'count': 2}
    assert len(report['volume']) == 24
    # 15:00, 14:00 and 13:55 (now is 15:30)
    assert [report['volume'][h]['count'] for h in (13, 14, 15, 16)] == [1, 1, 1, 0]


def test_week_and_all_ranges_bucket_by_day():
    orders = [order('delivered', 0, days_ago=d) for d in (0, 1, 1, 6, 9)]
    week = analytics.summarize(orders, PRICES, '7d', now=NOW)
    assert [b['count'] for b in week['volume']] == [1, 0, 0, 0, 0, 2, 1]
    everything = analytics.summarize(orders, PRICES, 'all', now=NOW)
    assert len(everything['volume']) == 10 and everything['delivered'] == 5


def test_empty_log_and_bad_range():
    report = analytics.summarize([], PRICES, 'all', now=NOW)
    assert report['delivered'] == 0 and report['success_rate'] is None
    assert report['time_to_table']['median'] is None and len(report['volume']) == 1
    with pytest.raises(ValueError):
        analytics.summarize([], PRICES, 'year', now=NOW)


# ----- usage & maintenance ------------------------------------------------------------

class Clock:
    def __init__(self):
        self.day = date(2026, 10, 26)
        self.t = 1000.0

    def today(self):
        return self.day


def tracker(tmp_path, clock):
    return UsageTracker(str(tmp_path / 'usage.json'), load_schedule(SCHEDULE),
                        clock=lambda: clock.t, today=clock.today)


def test_odometry_and_battery_integrate_into_usage(tmp_path):
    clock = Clock()
    usage = tracker(tmp_path, clock)
    for i in range(101):                      # 10 s at 0.5 m/s, 10 Hz
        usage.odometry(100.0 + i * 0.1, 0.5, 0.0)
    for i in range(51):                       # 5 s turning in place
        usage.odometry(110.0 + i * 0.1, 0.0, 0.8)
    for i in range(31):                       # 3 s standing still
        usage.odometry(115.0 + i * 0.1, 0.0, 0.0)
    usage.odometry(300.0, 0.5, 0.0)           # gap (pause): not integrated
    totals = usage.totals
    assert totals['distance_m'] == pytest.approx(5.0, abs=0.06)
    assert totals['drive_s'] == pytest.approx(15.0, abs=0.2)
    assert totals['operating_s'] == pytest.approx(18.0, abs=0.3)

    for pct, charging in ((80.0, False), (79.0, False), (78.5, False), (90.0, True),
                          (89.0, False), (19.0, False)):   # last one: manual override
        usage.battery(pct, charging)
    assert totals['battery_cycles'] == pytest.approx(0.025)


def test_service_resets_an_item_and_forecast_uses_daily_rate(tmp_path):
    clock = Clock()
    usage = tracker(tmp_path, clock)
    for day in range(3):                      # 2 km a day for three days
        clock.day = date(2026, 10, 24) + timedelta(days=day)
        usage._add('distance_m', 2000.0)
    wheels = next(i for i in usage.report()['items'] if i['id'] == 'wheels')
    assert wheels['used'] == 6000 and wheels['state'] == 'ok'
    assert wheels['daily_rate'] == 2000 and wheels['due_in_days'] == 22.0
    usage._add('distance_m', 34000.0)         # 40 km of 50: due soon
    assert next(i for i in usage.report()['items'] if i['id'] == 'wheels')['state'] == 'soon'
    usage._add('distance_m', 10000.0)
    assert next(i for i in usage.report()['items'] if i['id'] == 'wheels')['state'] == 'overdue'
    clock.t = 5000.0
    usage.record_service('wheels')
    wheels = next(i for i in usage.report()['items'] if i['id'] == 'wheels')
    assert wheels['used'] == 0 and wheels['state'] == 'ok' and wheels['last_service'] == 5000.0
    with pytest.raises(KeyError):
        usage.record_service('wings')


def test_usage_survives_a_restart(tmp_path):
    clock = Clock()
    usage = tracker(tmp_path, clock)
    usage._add('distance_m', 123.0)
    usage.record_service('sensors')
    usage.save()
    data = json.loads((tmp_path / 'usage.json').read_text())
    assert data['totals']['distance_m'] == 123.0
    again = tracker(tmp_path, clock)
    assert again.totals['distance_m'] == 123.0 and 'sensors' in again.services
    assert not os.path.exists(tmp_path / 'usage.json.tmp')


def test_idle_robot_has_no_forecast(tmp_path):
    report = tracker(tmp_path, Clock()).report()
    assert all(i['due_in_days'] is None and i['state'] == 'ok' for i in report['items'])
    assert {i['id'] for i in report['items']} == {'wheels', 'drive', 'sensors', 'battery', 'inspection'}
