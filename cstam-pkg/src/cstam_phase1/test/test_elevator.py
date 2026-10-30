"""Elevator legs and the task manager's routing between floors."""
import math
import pathlib

from cstam_phase1.elevator import floor_of_height, in_cabin, load_elevator, ride_legs

LOCATIONS = pathlib.Path(__file__).parents[1] / 'maps' / 'restaurant' / 'locations.yaml'
LIFT = load_elevator(str(LOCATIONS))


def test_ride_legs_drive_straight_through_the_cabin():
    up = ride_legs(LIFT, 1, 2)
    assert [leg['name'] for leg in up] == [
        'elevator_lobby_f1', 'elevator_cabin_f1', 'elevator_ride_f2', 'elevator_exit_f2']
    assert up[2]['ride'] == 2
    # One heading the whole way: in from the north, out to the south.
    assert {leg['yaw'] for leg in up if 'yaw' in leg} == {LIFT['floors'][1]['enter_yaw']}
    assert up[0]['y'] > up[1]['y'] > up[3]['y']
    down = ride_legs(LIFT, 2, 1)
    assert down[0]['y'] < down[1]['y'] < down[3]['y']
    assert ride_legs(LIFT, 1, 1) == [] and ride_legs(None, 1, 2) == []


def test_cabin_presence_and_floor_from_height():
    assert in_cabin(LIFT, LIFT['x'] + 0.2, LIFT['cabin_y'] - 0.3)
    assert not in_cabin(LIFT, LIFT['x'], LIFT['cabin_y'] + 1.0)   # still in the lobby
    assert floor_of_height(LIFT, 0.03) == 1
    assert floor_of_height(LIFT, 2.6) == 2


def test_task_manager_routes_up_and_back_through_the_elevator():
    from test_delivery_control import manager
    node = manager()
    node.locations = {
        'dock': {'floor': 1, 'x': 5.78, 'y': 15.5, 'yaw': 1.57},
        'table_4': {'floor': 2, 'x': -5.64, 'y': -17.02, 'yaw': 0.0},
        'terrace_1': {'floor': 1, 'x': -8.05, 'y': 6.55, 'yaw': math.pi},
    }
    node.elevator = LIFT
    node.floor = 1
    node.doors = {'terrace_x': -7.05, 'inside_x': -6.4, 'outside_x': -7.75,
                  'y': {'door_a': 3.74, 'door_b': 7.2}}
    up = node._plan_legs('table_4')
    assert [leg['name'] for leg in up][2] == 'elevator_ride_f2'
    node.floor = 2
    assert node._plan_legs('table_4') == []
    # Upstairs to the terrace: ride down first, then out through a door.
    names = [leg['name'] for leg in node._plan_legs('terrace_1')]
    assert names[:4] == ['elevator_lobby_f2', 'elevator_cabin_f2', 'elevator_ride_f1', 'elevator_exit_f1']
    assert names[4].endswith('_out_1') and names[5].endswith('_out_2')
    # From the terrace up: in through a door, then the elevator.
    node.floor, node.zone, node.last_terrace_y = 1, 'terrace', 6.55
    names = [leg['name'] for leg in node._plan_legs('table_4')]
    assert names[0].endswith('_in_1') and names[2] == 'elevator_lobby_f1'


def test_ride_leg_calls_the_elevator_and_moves_on():
    from types import SimpleNamespace
    from test_delivery_control import manager
    node = manager()
    node.elevator = LIFT
    node.floor = 1
    node.riding = False
    calls = []

    class Client:
        def service_is_ready(self):
            return True

        def call_async(self, request):
            calls.append(request)
            return SimpleNamespace(add_done_callback=lambda cb: calls.append(cb))
    node.elevator_clients = {2: Client(), 1: Client()}
    sent = []
    node._send_pose_goal = lambda name, pose, stage: sent.append(name)
    node.legs = ride_legs(LIFT, 1, 2)[2:] + ['table_4']
    node._send_next_leg('customer')
    assert node.riding and node.events[-1] == 'riding the elevator to floor 2'
    done = calls[-1]
    done(SimpleNamespace(result=lambda: SimpleNamespace(success=True, message='arrived')))
    assert node.floor == 2 and not node.riding
    assert sent == ['elevator_exit_f2']


def test_a_failed_ride_is_retried_like_a_failed_goal():
    from types import SimpleNamespace
    from test_delivery_control import manager
    node = manager()
    node.elevator, node.floor, node.riding = LIFT, 1, False
    node.legs = ride_legs(LIFT, 1, 2)[2:] + ['table_4']
    node.current_stage = 'customer'
    node.retry_timer = None
    node._ride_done(SimpleNamespace(result=lambda: SimpleNamespace(
        success=False, message='robot is not in the cabin')), node.legs[0], 'customer')
    assert node.floor == 1 and node.goal_attempts == 1
    assert 'retry 1/3' in node.events[-1]


def test_dock_return_requested_during_a_ride_waits_for_the_cabin():
    from test_delivery_control import manager
    node = manager()
    node.riding = True
    node.goal_request_pending = False
    node.state = 'NAVIGATING_TO_CUSTOMER'
    node.current_location = 'table_4'
    node.locations = {'dock': {}}
    ok, _ = node._request_dock_return('manual')
    assert ok and node.manual_dock_requested and node.state == 'RETURNING_TO_DOCK'
    assert not any(isinstance(e, tuple) for e in node.events)   # no goal sent mid-ride
