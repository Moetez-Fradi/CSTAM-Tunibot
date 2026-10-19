"""Regression checks for manual-return arbitration, separate from real acceptance."""
from collections import deque
from types import SimpleNamespace
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
    node.events = []
    node._publish_status = lambda message: node.events.append(message)
    node._send_navigation_goal = lambda *args: node.events.append(args)
    return node


def test_manual_return_waits_for_pending_goal():
    node = manager()
    response = node._return_to_dock_callback(None, Trigger.Response())
    assert response.success
    assert node.manual_dock_requested
    assert node.state == 'RETURNING_TO_DOCK'
    assert not any(isinstance(event, tuple) for event in node.events)


def test_failed_manual_dock_does_not_retry_forever():
    node = manager()
    node.manual_dock_requested = True
    node._fail = lambda message: node.events.append(('failed', message))
    node._return_to_dock = lambda: node.events.append('retried')
    future = SimpleNamespace(result=lambda: SimpleNamespace(status=6))
    node._goal_result_callback(future, 'dock', 'dock')
    assert node.events[0][0] == 'failed'
    assert 'retried' not in node.events


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
