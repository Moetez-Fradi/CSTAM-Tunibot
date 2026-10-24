"""Delivery locations, the menu, and validation of orders placed from the web.

Locations come from the same locations.yaml the task manager uses, so the UI
can never offer a table the robot does not know. Everything here is plain
Python (no ROS) so it is unit-tested directly.
"""

import uuid

import yaml


MAX_ITEMS = 20       # distinct lines per order (task manager limit)
MAX_QTY = 20         # per line (task manager limit)
MAX_NOTE = 200


def _label(name):
    """table_1 -> Table 1, terrace_2 -> Terrace 2."""
    return ' '.join(part.capitalize() for part in name.split('_'))


class Catalog:
    def __init__(self, locations_file, menu_file, dock='dock', pickup='kitchen'):
        with open(locations_file, encoding='utf-8') as stream:
            data = yaml.safe_load(stream) or {}
        with open(menu_file, encoding='utf-8') as stream:
            menu = yaml.safe_load(stream) or {}
        doors = data.get('doors') or {}
        terrace_x = doors.get('terrace_x')
        self.points = {}
        for name, value in data.items():
            if name in ('supported_floors', 'doors') or not isinstance(value, dict):
                continue
            self.points[name] = {
                'name': name, 'label': _label(name), 'floor': int(value['floor']),
                'x': float(value['x']), 'y': float(value['y']), 'yaw': float(value['yaw']),
                'zone': ('terrace' if terrace_x is not None and value['x'] < terrace_x
                         else 'dining room'),
            }
        self.dock, self.pickup = dock, pickup
        self.doors = [
            {'name': name, 'label': _label(name), 'y': float(value['y']),
             'inside_x': float(doors['inside_x']), 'outside_x': float(doors['outside_x'])}
            for name, value in doors.items() if isinstance(value, dict)]
        self.currency = str(menu.get('currency', 'TND'))
        self.menu = []
        for item in menu.get('items') or []:
            self.menu.append({
                'id': str(item['id']), 'name': str(item['name']),
                'category': str(item.get('category', 'Other')),
                'price': round(float(item.get('price', 0.0)), 3),
            })
        self.menu_by_id = {item['id']: item for item in self.menu}

    def delivery_locations(self):
        return [p for name, p in sorted(self.points.items())
                if name not in (self.dock, self.pickup) and p['floor'] == 1]

    def public_config(self):
        return {
            'locations': self.delivery_locations(),
            'dock': self.points.get(self.dock),
            'pickup': self.points.get(self.pickup),
            'doors': self.doors,
            'menu': self.menu,
            'currency': self.currency,
        }

    def build_order(self, body):
        """Validate a browser order; return (task-manager order, total price).

        Raises ValueError with a message that is safe to show to the customer.
        """
        if not isinstance(body, dict):
            raise ValueError('order must be a JSON object')
        location = str(body.get('location') or '').strip().lower()
        if location not in {p['name'] for p in self.delivery_locations()}:
            raise ValueError(f'unknown table "{location}"')
        lines = body.get('items')
        if not isinstance(lines, list) or not lines:
            raise ValueError('add at least one item to the order')
        quantities = {}
        for line in lines:
            if not isinstance(line, dict):
                raise ValueError('invalid order line')
            item = self.menu_by_id.get(str(line.get('id')))
            if item is None:
                raise ValueError(f'unknown menu item "{line.get("id")}"')
            try:
                qty = int(line.get('qty', 1))
            except (TypeError, ValueError):
                raise ValueError(f'invalid quantity for {item["name"]}') from None
            quantities[item['id']] = quantities.get(item['id'], 0) + qty
        if len(quantities) > MAX_ITEMS:
            raise ValueError(f'at most {MAX_ITEMS} different items per order')
        items, total = [], 0.0
        for item_id, qty in quantities.items():
            item = self.menu_by_id[item_id]
            if not 1 <= qty <= MAX_QTY:
                raise ValueError(f'{item["name"]}: quantity must be 1-{MAX_QTY}')
            items.append({'name': item['name'], 'qty': qty})
            total += qty * item['price']
        note = str(body.get('note') or '').strip()
        if len(note) > MAX_NOTE:
            raise ValueError(f'note is limited to {MAX_NOTE} characters')
        order = {'id': uuid.uuid4().hex[:6], 'location': location, 'items': items,
                 'note': note, 'source': str(body.get('source') or 'web')[:32]}
        return order, round(total, 3)


def find_order(status, order_id):
    """Locate an order in a /delivery/status payload.

    Returns (order, queue_position) where queue_position is 1-based for a
    queued order, 0 for the active one and None for a finished one; or
    (None, None) when the order is not known.
    """
    if not status or not order_id:
        return None, None
    active = status.get('active_order')
    if active and active.get('id') == order_id:
        return active, 0
    for index, order in enumerate(status.get('orders') or []):
        if order.get('id') == order_id:
            return order, index + 1
    for order in reversed(status.get('history') or []):
        if order.get('id') == order_id:
            return order, None
    return None, None
