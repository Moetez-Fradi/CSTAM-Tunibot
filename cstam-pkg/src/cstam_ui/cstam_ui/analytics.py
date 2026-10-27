"""Business view of the order log: volume, speed, revenue, energy, demand.

Input is the list of finished orders (the task manager's JSON-lines log);
times are wall-clock seconds and bucketed in the server's local time.
"""

from collections import Counter
from datetime import datetime, timedelta
import statistics


RANGES = ('today', '7d', 'all')
MAX_DAYS = 60     # daily buckets shown for "all"


def _quantile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def summarize(orders, prices, range_name='today', now=None):
    """prices: menu item name -> unit price."""
    if range_name not in RANGES:
        raise ValueError(f'range must be one of {", ".join(RANGES)}')
    now = datetime.fromtimestamp(now) if now is not None else datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_name == 'today':
        start = midnight
    elif range_name == '7d':
        start = midnight - timedelta(days=6)
    else:
        first = min((o['created_at'] for o in orders), default=now.timestamp())
        start = max(datetime.fromtimestamp(first).replace(hour=0, minute=0, second=0, microsecond=0),
                    midnight - timedelta(days=MAX_DAYS - 1))
    picked = [o for o in orders if o.get('created_at') and o['created_at'] >= start.timestamp()]

    delivered = [o for o in picked if o['status'] == 'delivered']
    failed = [o for o in picked if o['status'] == 'failed']
    cancelled = [o for o in picked if o['status'] == 'cancelled']
    to_table = [o['arrived_at'] - o['created_at'] for o in delivered if o.get('arrived_at')]
    waiting = [o['started_at'] - o['created_at'] for o in delivered if o.get('started_at')]
    energy = [o['battery_start'] - o['battery_end'] for o in delivered
              if o.get('battery_start') is not None and o.get('battery_end') is not None
              and o['battery_end'] <= o['battery_start']]   # charged mid-order: skip

    items, revenue = Counter(), 0.0
    for order in delivered:
        for line in order.get('items') or []:
            items[line['name']] += line['qty']
            revenue += line['qty'] * prices.get(line['name'], 0.0)
    tables = Counter(o.get('location') for o in delivered if o.get('location'))

    # Volume over time: hours for one day, days otherwise.
    if range_name == 'today':
        buckets = [{'label': f'{h:02d}:00', 'start': (midnight + timedelta(hours=h)).timestamp(),
                    'count': 0} for h in range(24)]
        index = lambda t: datetime.fromtimestamp(t).hour  # noqa: E731
    else:
        days = (midnight - start).days + 1
        buckets = [{'label': (start + timedelta(days=d)).strftime('%a %d'),
                    'start': (start + timedelta(days=d)).timestamp(), 'count': 0} for d in range(days)]
        index = lambda t: (datetime.fromtimestamp(t).replace(  # noqa: E731
            hour=0, minute=0, second=0, microsecond=0) - start).days
    for order in delivered:
        i = index(order['created_at'])
        if 0 <= i < len(buckets):
            buckets[i]['count'] += 1

    settled = len(delivered) + len(failed)
    return {
        'range': range_name, 'from': start.timestamp(), 'to': now.timestamp(),
        'orders': len(picked), 'delivered': len(delivered), 'failed': len(failed),
        'cancelled': len(cancelled),
        'success_rate': round(len(delivered) / settled, 3) if settled else None,
        'confirmed_rate': round(sum(bool(o.get('confirmed')) for o in delivered) / len(delivered), 3)
        if delivered else None,
        'time_to_table': {'median': _quantile(to_table, 0.5), 'p90': _quantile(to_table, 0.9)},
        'wait_before_start': {'median': _quantile(waiting, 0.5)},
        'battery_per_delivery': round(statistics.mean(energy), 2) if energy else None,
        'deliveries_per_charge': round(100.0 / statistics.mean(energy), 1)
        if energy and statistics.mean(energy) > 0 else None,
        'revenue': round(revenue, 2),
        'average_ticket': round(revenue / len(delivered), 2) if delivered else None,
        'top_items': [{'name': n, 'qty': q} for n, q in items.most_common(6)],
        'tables': [{'location': n, 'count': c} for n, c in tables.most_common()],
        'volume': buckets,
    }
