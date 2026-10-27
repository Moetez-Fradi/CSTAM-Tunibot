"""Regression checks for manual-return arbitration, separate from real acceptance."""
from collections import deque
import json
import os
from types import SimpleNamespace

import pytest
from std_msgs.msg import String
from sensor_msgs.msg import BatteryState
from std_srvs.srv import Trigger
from cstam_phase1.delivery_task_manager import DeliveryTaskManager


def manager():
    node = object.__new__(DeliveryTaskManager)
    node.dock_location = 'dock'
    node.pickup_location = 'kitchen'
    node.locations = {'dock': {}}
    node.state = 'NAVIGATING_TO_PICKUP'
    node.current_stage = 'pickup'
    node.current_goal_handle = None
    node.goal_request_pending = True
    node.manual_dock_requested = False
    node.current_location = None
    node.queue = deque()
    node.battery_percentage = None
    node.battery_charging = False
    node.battery_return = False
    node.at_dock = False
    node.min_start_percentage = 35.0
    node.low_battery_percentage = 20.0
    node.resume_percentage = 80.0
    node.get_logger = lambda: SimpleNamespace(
        info=lambda *_: None, warn=lambda *_: None, error=lambda *_: None)
    node.legs = []
    node.zone = 'room'
    node.doors = None
    node.door_tried = set()
    node.door_in_use = None
    node.last_terrace_y = 0.0
    node.goal_retries = 3
    node.retry_delay = 5.0
    node.goal_attempts = 0
    node.retry_timer = None
    node.failed_orders = []
    node.counters = {'nav_goals': 0, 'nav_failures': 0, 'nav_retries': 0, 'door_reroutes': 0}
    node.orders = {}
    node.history = deque(maxlen=10)
    node.last_rejection = None
    node.confirm_timer = None
    node.confirmation_timeout = 0.0   # deliver on arrival unless a test opts in
    node.progress = None
    node.order_log_file = os.devnull
    node.scheduled = []
    node.create_timer = lambda period, cb: node.scheduled.append(cb) or SimpleNamespace(
        cancel=lambda: None)
    node.destroy_timer = lambda timer: None
    node.events = []
    node.last_message = ''
    node.last_result = None
    node._publish_status = lambda message, log=True: node.events.append(message)
    node._send_navigation_goal = lambda *args: node.events.append(args)
    return node


def test_manual_return_waits_for_pending_goal():
    node = manager()
    response = node._return_to_dock_callback(None, Trigger.Response())
    assert response.success
    assert node.manual_dock_requested
    assert node.state == 'RETURNING_TO_DOCK'
    assert not any(isinstance(event, tuple) for event in node.events)


def test_failed_dock_retries_a_bounded_number_of_times_then_errors():
    node = manager()
    node.state = 'RETURNING_TO_DOCK'
    node.current_stage = 'dock'
    node.goal_request_pending = False
    node._fail = lambda message: node.events.append(('failed', message))
    aborted = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    for _ in range(node.goal_retries):
        node._goal_result_callback(aborted, 'dock', 'dock')
        assert node.scheduled, 'a retry is scheduled'
        node.scheduled.pop()()  # the retry fires and resends the dock goal
    assert sum(isinstance(e, tuple) and e[0] == 'dock' for e in node.events) == node.goal_retries
    node._goal_result_callback(aborted, 'dock', 'dock')
    assert node.events[-1][0] == 'failed'
    assert not node.scheduled


def test_customer_goal_that_keeps_failing_is_given_up_and_robot_docks():
    node = manager()
    node.state = 'NAVIGATING_TO_CUSTOMER'
    node.current_stage = 'customer'
    node.current_location = 'terrace_1'
    node.goal_request_pending = False
    node._return_to_dock = lambda: node.events.append('dock')
    aborted = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    for _ in range(node.goal_retries):
        node._goal_result_callback(aborted, 'terrace_1', 'customer')
        node.scheduled.pop()()
    node._goal_result_callback(aborted, 'terrace_1', 'customer')
    assert node.failed_orders == ['terrace_1']
    assert node.current_location is None
    assert node.events[-1] == 'dock'


def test_stale_retry_is_skipped_after_a_manual_return():
    node = manager()
    node.state = 'NAVIGATING_TO_PICKUP'
    node.current_stage = 'pickup'
    node.current_location = 'table_1'
    node.goal_request_pending = False
    aborted = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    node._goal_result_callback(aborted, 'kitchen', 'pickup')
    retry = node.scheduled.pop()
    node._return_to_dock_callback(None, Trigger.Response())
    assert list(node.queue) == ['table_1']  # waiting order kept
    sent_before = len([e for e in node.events if isinstance(e, tuple)])
    retry()
    assert len([e for e in node.events if isinstance(e, tuple)]) == sent_before


def test_manual_return_wins_over_completed_pickup():
    node = manager()
    node.manual_dock_requested = True
    node._return_to_dock = lambda: node.events.append('dock')
    future = SimpleNamespace(result=lambda: SimpleNamespace(status=4))
    node._goal_result_callback(future, 'kitchen', 'pickup')
    assert node.events == ['dock']
    assert list(node.queue) == []


def test_manual_return_requeues_interrupted_order_first():
    node = manager()
    node.manual_dock_requested = True
    node.current_location = 'table_2'
    node.queue = deque(['table_3'])
    node._return_to_dock = lambda: node.events.append('dock')
    future = SimpleNamespace(result=lambda: SimpleNamespace(status=5))
    node._goal_result_callback(future, 'kitchen', 'pickup')
    assert list(node.queue) == ['table_2', 'table_3']
    assert node.current_location is None
    assert node.events[-1] == 'dock'


def battery(percent, status=BatteryState.POWER_SUPPLY_STATUS_DISCHARGING):
    return BatteryState(percentage=percent / 100.0, power_supply_status=status)


def test_low_battery_interrupts_delivery_and_returns_to_dock():
    node = manager()
    node.goal_request_pending = False
    node.current_goal_handle = SimpleNamespace(
        cancel_goal_async=lambda: node.events.append('cancel'))
    node._battery_callback(battery(19.0))
    assert node.battery_return
    assert node.manual_dock_requested
    assert node.state == 'RETURNING_TO_DOCK'
    assert 'cancel' in node.events


def test_low_battery_does_not_interrupt_return_to_dock():
    node = manager()
    node.state = 'RETURNING_TO_DOCK'
    node.current_stage = 'dock'
    node._battery_callback(battery(10.0))
    assert not node.manual_dock_requested
    assert not node.battery_return


def test_dock_arrival_after_low_battery_starts_charging():
    node = manager()
    node.battery_return = True
    node.battery_percentage = 18.0
    node.manual_dock_requested = True
    future = SimpleNamespace(result=lambda: SimpleNamespace(status=4))
    node._goal_result_callback(future, 'dock', 'dock')
    assert node.state == 'CHARGING'
    assert node.at_dock


def test_charging_resumes_queue_at_resume_threshold():
    node = manager()
    node.state = 'CHARGING'
    node.at_dock = True
    node.battery_return = True
    node.goal_request_pending = False
    node.queue = deque(['table_1'])
    node._battery_callback(battery(79.0, BatteryState.POWER_SUPPLY_STATUS_CHARGING))
    assert node.state == 'CHARGING'
    node._battery_callback(battery(80.0, BatteryState.POWER_SUPPLY_STATUS_CHARGING))
    assert node.state == 'NAVIGATING_TO_PICKUP'
    assert node.current_location == 'table_1'
    assert not node.battery_return


def test_new_delivery_waits_at_dock_when_battery_is_low():
    node = manager()
    node.state = 'IDLE'
    node.at_dock = True
    node.goal_request_pending = False
    node.battery_percentage = 30.0
    node.queue = deque(['table_1'])
    node._start_queued_task()
    assert node.state == 'CHARGING'
    assert list(node.queue) == ['table_1']


def test_low_battery_between_deliveries_returns_to_dock_first():
    node = manager()
    node.state = 'IDLE'
    node.at_dock = False
    node.goal_request_pending = False
    node.battery_percentage = 30.0
    node.queue = deque(['table_2'])
    node._start_queued_task()
    assert node.state == 'RETURNING_TO_DOCK'
    assert ('dock', 'dock') in node.events
    assert list(node.queue) == ['table_2']


def test_depleted_battery_cancels_and_keeps_order():
    node = manager()
    node.goal_request_pending = False
    node.current_location = 'table_3'
    node.current_goal_handle = SimpleNamespace(
        cancel_goal_async=lambda: node.events.append('cancel'))
    node._battery_callback(battery(0.0))
    assert node.state == 'BATTERY_DEPLETED'
    assert 'cancel' in node.events
    assert list(node.queue) == ['table_3']
    # The cancelled goal's late result must not overwrite the depleted state.
    future = SimpleNamespace(result=lambda: SimpleNamespace(status=5))
    node._goal_result_callback(future, 'kitchen', 'pickup')
    assert node.state == 'BATTERY_DEPLETED'


def door_manager():
    node = manager()
    node.locations = {
        'dock': {'x': -3.63, 'y': 0.85, 'yaw': 0.0},
        'kitchen': {'x': 0.02, 'y': 9.27, 'yaw': 1.0},
        'terrace_1': {'x': -8.05, 'y': 6.55, 'yaw': 3.14},
        'terrace_2': {'x': -8.00, 'y': 2.50, 'yaw': 3.14},
    }
    node.doors = {'terrace_x': -7.05, 'inside_x': -6.40, 'outside_x': -7.75,
                  'y': {'door_a': 3.74, 'door_b': 7.20}}
    node.goal_request_pending = False
    node.sent = []
    node._send_pose_goal = lambda name, pose, stage: node.sent.append((name, stage))
    node._send_navigation_goal = lambda location, stage: node.sent.append((location, stage))
    node.door_path_max, node.door_recheck, node.door_checks = 2.5, 5.0, 0
    node._check_door = lambda stage: node._door_decision(1.4, stage)  # doors clear
    return node


def succeed(node, stage):
    name = node.sent[-1][0]
    node._goal_result_callback(SimpleNamespace(result=lambda: SimpleNamespace(status=4)),
                               name, stage)


def test_trip_to_the_terrace_goes_square_through_the_nearest_door():
    node = door_manager()
    node.state = 'NAVIGATING_TO_CUSTOMER'
    node.current_location = 'terrace_1'
    node._navigate('terrace_1', 'customer')
    assert node.sent[-1] == ('door_b_out_1', 'customer')   # terrace_1 is by door B
    succeed(node, 'customer')
    assert node.sent[-1] == ('door_b_out_2', 'customer')
    succeed(node, 'customer')
    assert node.sent[-1] == ('terrace_1', 'customer')
    assert node.zone == 'terrace'


def test_trip_within_a_zone_has_no_door_legs():
    node = door_manager()
    node._navigate('kitchen', 'pickup')
    assert node.sent == [('kitchen', 'pickup')]


def test_return_from_the_terrace_uses_the_door_by_the_last_terrace_stop():
    node = door_manager()
    node.zone, node.last_terrace_y = 'terrace', 2.5   # at terrace_2, by door A
    node._navigate('dock', 'dock')
    assert node.sent[-1] == ('door_a_in_1', 'dock')


def test_blocked_door_reroutes_through_the_other_door_then_gives_up():
    node = door_manager()
    node.state = 'NAVIGATING_TO_CUSTOMER'
    node.current_stage = 'customer'
    node.current_location = 'terrace_1'
    node._return_to_dock = lambda: node.sent.append(('dock-return', 'dock'))
    node._navigate('terrace_1', 'customer')
    aborted = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    for door in ('door_b', 'door_a'):
        assert node.sent[-1][0].startswith(door)
        for _ in range(node.goal_retries):
            node._goal_result_callback(aborted, node.sent[-1][0], 'customer')
            node.scheduled.pop()()
        node._goal_result_callback(aborted, node.sent[-1][0], 'customer')
    assert node.failed_orders == ['terrace_1']
    assert node.sent[-1] == ('dock-return', 'dock')


def at_door_b(node):
    node.state = 'NAVIGATING_TO_CUSTOMER'
    node.current_stage = 'customer'
    node.current_location = 'terrace_1'
    node.door_path_max, node.door_recheck, node.door_checks = 2.5, 5.0, 0
    node._navigate('terrace_1', 'customer')
    node.checks = []
    node._check_door = lambda stage: node.checks.append(stage)
    succeed(node, 'customer')          # inside pose of door B reached
    assert node.checks == ['customer'] and node.sent[-1][0] == 'door_b_out_1'


def test_clear_door_is_driven_straight_through():
    node = door_manager()
    at_door_b(node)
    node._door_decision(1.4, 'customer')
    assert node.sent[-1] == ('door_b_out_2', 'customer')


def test_blocked_door_waits_once_then_reroutes_through_the_other_door():
    node = door_manager()
    at_door_b(node)
    node._door_decision(6.0, 'customer')   # planner goes the long way round
    assert node.sent[-1][0] == 'door_b_out_1'
    node.scheduled.pop()()                 # recheck after waiting
    assert node.checks == ['customer', 'customer']
    node._door_decision(None, 'customer')  # still blocked (no path)
    assert node.sent[-1] == ('door_a_out_1', 'customer')


def test_both_doors_blocked_gives_the_order_up():
    node = door_manager()
    at_door_b(node)
    node._return_to_dock = lambda: node.sent.append(('dock-return', 'dock'))
    for _ in range(2):
        node._door_decision(None, 'customer')
        if node.scheduled:
            node.scheduled.pop()()
    succeed(node, 'customer')              # inside pose of door A reached
    for _ in range(2):
        node._door_decision(None, 'customer')
        if node.scheduled:
            node.scheduled.pop()()
    assert node.failed_orders == ['terrace_1']
    assert node.sent[-1] == ('dock-return', 'dock')


SUCCEEDED = SimpleNamespace(result=lambda: SimpleNamespace(status=4))


def order_manager():
    node = manager()
    node.locations = {name: {'floor': 1, 'x': 0.0, 'y': 0.0, 'yaw': 0.0}
                      for name in ('dock', 'kitchen', 'table_1', 'table_2')}
    node.state = 'IDLE'
    node.current_stage = None
    node.goal_request_pending = False
    node.at_dock = True
    return node


def request(node, payload):
    data = payload if isinstance(payload, str) else json.dumps(payload)
    node._request_callback(String(data=data))


def drive_to_table(node):
    """Queue table_1 (JSON order) and drive through pickup to the table."""
    request(node, {'id': 'A1', 'location': 'table_1', 'items': [
        {'name': 'Coffee', 'qty': 2}, 'Water'], 'note': 'no sugar', 'source': 'web'})
    assert node.state == 'NAVIGATING_TO_PICKUP'
    assert node.orders['table_1']['status'] == 'in_progress'
    node._goal_result_callback(SUCCEEDED, 'kitchen', 'pickup')
    assert node.orders['table_1']['picked_up_at'] is not None
    node._goal_result_callback(SUCCEEDED, 'table_1', 'customer')


def test_json_order_is_queued_with_items_and_reported():
    node = order_manager()
    node.state = 'CHARGING'           # keeps the order waiting in the queue
    request(node, {'id': 'A1', 'location': 'Table_1',
                   'items': [{'name': 'Coffee', 'qty': 2}, 'Water']})
    request(node, 'table_2')          # plain strings keep working
    status = node._status_payload()
    assert status['queue'] == ['table_1', 'table_2']
    first, second = status['orders']
    assert first['id'] == 'A1' and first['status'] == 'queued'
    assert first['items'] == [{'name': 'Coffee', 'qty': 2}, {'name': 'Water', 'qty': 1}]
    assert second['items'] == [] and second['id']
    json.dumps(status)                # the payload stays serializable


@pytest.mark.parametrize('payload, reason', [
    ('{"location": "table_1", "items": [{"name": "Tea", "qty": 0}]}', 'quantity'),
    ('{"location": "table_1", "items": "tea"}', 'items must be a list'),
    ('{not json', 'invalid JSON'),
    ('dock', 'unknown location'),
    ('kitchen', 'unknown location'),
    ('{"location": "table_9", "id": "X"}', 'unknown location'),
])
def test_invalid_orders_are_rejected_with_a_reason(payload, reason):
    node = order_manager()
    request(node, payload)
    assert not node.queue and not node.orders and node.state == 'IDLE'
    assert reason in node.last_rejection['reason']


def test_duplicate_order_id_is_rejected():
    node = order_manager()
    node.state = 'CHARGING'
    request(node, {'id': 'A1', 'location': 'table_1'})
    request(node, {'id': 'A1', 'location': 'table_2'})
    assert list(node.queue) == ['table_1']
    assert node.last_rejection == {**node.last_rejection, 'id': 'A1', 'location': 'table_2'}


def test_robot_waits_at_the_table_until_the_customer_confirms():
    node = order_manager()
    node.confirmation_timeout = 20.0
    drive_to_table(node)
    assert node.state == 'AWAITING_CONFIRMATION'
    assert node.orders['table_1']['confirm_by'] is not None
    assert node.scheduled, 'a confirmation timeout is armed'
    node._confirm_callback(String(data='table_2'))      # wrong table: ignored
    assert node.state == 'AWAITING_CONFIRMATION'
    node._confirm_callback(String(data='A1'))
    done = node.history[-1]
    assert done['status'] == 'delivered' and done['confirmed']
    assert done['items'][0] == {'name': 'Coffee', 'qty': 2} and done['note'] == 'no sugar'
    assert node.state == 'RETURNING_TO_DOCK' and node.events[-1] == ('dock', 'dock')
    assert not node.orders


def test_unconfirmed_delivery_completes_after_the_timeout():
    node = order_manager()
    node.confirmation_timeout = 20.0
    drive_to_table(node)
    node.scheduled.pop()()
    assert node.history[-1]['status'] == 'delivered'
    assert not node.history[-1]['confirmed']
    assert node.state == 'RETURNING_TO_DOCK'


def test_zero_timeout_delivers_on_arrival():
    node = order_manager()
    drive_to_table(node)
    assert node.history[-1]['status'] == 'delivered'
    assert node.state == 'RETURNING_TO_DOCK'


def test_cancelling_a_queued_order_removes_it():
    node = order_manager()
    node.state = 'CHARGING'
    request(node, {'id': 'A1', 'location': 'table_1'})
    request(node, 'table_2')
    node._cancel_callback(String(data='A1'))
    assert list(node.queue) == ['table_2']
    assert node.history[-1]['id'] == 'A1' and node.history[-1]['status'] == 'cancelled'


def test_cancelling_the_active_order_returns_to_dock_without_requeueing():
    node = order_manager()
    request(node, 'table_1')
    request(node, 'table_2')
    node.current_goal_handle = SimpleNamespace(
        cancel_goal_async=lambda: node.events.append('cancel'))
    node._cancel_callback(String(data='table_1'))
    assert 'cancel' in node.events and node.state == 'RETURNING_TO_DOCK'
    node._goal_result_callback(SimpleNamespace(result=lambda: SimpleNamespace(status=5)),
                               'kitchen', 'pickup')
    assert list(node.queue) == ['table_2']             # the other order waits
    assert node.history[-1]['status'] == 'cancelled'
    assert node.events[-1] == ('dock', 'dock')


def test_manual_return_at_the_table_counts_the_order_as_delivered():
    node = order_manager()
    node.confirmation_timeout = 20.0
    drive_to_table(node)
    node._return_to_dock_callback(None, Trigger.Response())
    assert node.history[-1]['status'] == 'delivered'
    assert not node.queue                              # not delivered twice
    assert node.events[-1] == ('dock', 'dock')


def test_interrupted_order_is_marked_requeued():
    node = order_manager()
    request(node, 'table_1')
    node._requeue_interrupted_order()
    order = node.orders['table_1']
    assert order['status'] == 'queued' and order['interruptions'] == 1


def test_given_up_order_is_recorded_as_failed():
    node = order_manager()
    request(node, 'table_1')
    aborted = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    for _ in range(node.goal_retries):
        node._goal_result_callback(aborted, 'kitchen', 'pickup')
        node.scheduled.pop()()
    node._goal_result_callback(aborted, 'kitchen', 'pickup')
    assert node.history[-1]['status'] == 'failed'
    assert 'unreachable' in node.history[-1]['reason']


def test_finished_orders_are_appended_to_the_log(tmp_path):
    node = order_manager()
    node.order_log_file = str(tmp_path / 'logs' / 'orders.jsonl')
    drive_to_table(node)
    lines = (tmp_path / 'logs' / 'orders.jsonl').read_text().splitlines()
    assert [json.loads(line)['id'] for line in lines] == ['A1']


def test_progress_adds_the_door_hops_still_ahead():
    node = order_manager()
    node.eta_speed = 0.5
    node.last_feedback_publish = 0.0
    node.current_stage = 'customer'
    node.locations['terrace_1'] = {'floor': 1, 'x': -3.0, 'y': 4.0, 'yaw': 0.0}
    node.legs = [{'name': 'door_b_out_1', 'x': 0.0, 'y': 0.0, 'yaw': 0.0},
                 {'name': 'door_b_out_2', 'x': 0.0, 'y': 4.0, 'yaw': 0.0}, 'terrace_1']
    node._feedback_callback(SimpleNamespace(
        feedback=SimpleNamespace(distance_remaining=1.0)))
    assert node.progress == {'stage': 'customer', 'distance_remaining_m': 8.0, 'eta_sec': 16}


def test_orders_record_battery_and_navigation_is_counted():
    node = order_manager()
    node.battery_percentage = 91.04
    request(node, 'table_1')
    assert node.orders['table_1']['battery_start'] == 91.0
    aborted = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    node._goal_result_callback(aborted, 'kitchen', 'pickup')     # fails once, retried
    node.scheduled.pop()()
    node._goal_result_callback(SUCCEEDED, 'kitchen', 'pickup')
    node.battery_percentage = 84.0
    node._goal_result_callback(SUCCEEDED, 'table_1', 'customer')
    done = node.history[-1]
    assert (done['battery_start'], done['battery_end']) == (91.0, 84.0)
    assert node.counters['nav_failures'] == 1 and node.counters['nav_retries'] == 1
    assert node._status_payload()['counters'] == node.counters
