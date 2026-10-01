"""Regression checks for manual-return arbitration, separate from real acceptance."""
from types import SimpleNamespace
from std_srvs.srv import Trigger
from cstam_phase1.delivery_task_manager import DeliveryTaskManager


def manager():
    node = object.__new__(DeliveryTaskManager)
    node.dock_location = 'dock'
    node.locations = {'dock': {}}
    node.state = 'NAVIGATING_TO_PICKUP'
    node.current_stage = 'pickup'
    node.current_goal_handle = None
    node.goal_request_pending = True
    node.manual_dock_requested = False
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
