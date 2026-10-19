import math

from cstam_phase1.battery_model import (
    BatteryParams,
    charge_power_w,
    discharge_power_w,
    open_circuit_voltage,
    step_energy_wh,
)


PARAMS = BatteryParams()


def test_motion_drains_faster_than_idle():
    idle = step_energy_wh(5.0, 60.0, 0.0, 0.0, False, PARAMS)
    moving = step_energy_wh(5.0, 60.0, 0.2, 0.5, False, PARAMS)
    assert moving < idle < 5.0
    assert math.isclose(discharge_power_w(-0.2, -0.5, PARAMS), 4.0 + 5.0 + 3.0)


def test_one_delivery_uses_a_bounded_share_of_the_battery():
    # Measured delivery: about 340 s, averaging well below 0.2 m/s.
    used = PARAMS.capacity_wh - step_energy_wh(
        PARAMS.capacity_wh, 340.0, 0.15, 0.2, False, PARAMS)
    percent = 100.0 * used / PARAMS.capacity_wh
    assert 5.0 < percent < 15.0


def test_charging_raises_energy_and_tapers_near_full():
    assert step_energy_wh(2.0, 60.0, 0.0, 0.0, True, PARAMS) > 2.0
    assert charge_power_w(0.95, PARAMS) < charge_power_w(0.5, PARAMS)
    assert charge_power_w(0.999, PARAMS) >= PARAMS.charge_power_w * PARAMS.taper_floor


def test_energy_is_clamped():
    assert step_energy_wh(0.01, 3600.0, 1.0, 1.0, False, PARAMS) == 0.0
    assert step_energy_wh(9.99, 3600.0, 0.0, 0.0, True, PARAMS) == PARAMS.capacity_wh


def test_time_scale_accelerates_drain():
    fast = BatteryParams(time_scale=10.0)
    normal_used = 5.0 - step_energy_wh(5.0, 10.0, 0.2, 0.0, False, PARAMS)
    fast_used = 5.0 - step_energy_wh(5.0, 10.0, 0.2, 0.0, False, fast)
    assert math.isclose(fast_used, 10.0 * normal_used)


def test_voltage_is_monotonic_between_empty_and_full():
    values = [open_circuit_voltage(soc / 20.0, PARAMS) for soc in range(21)]
    assert values[0] == PARAMS.empty_voltage
    assert math.isclose(values[-1], PARAMS.full_voltage)
    assert all(a < b for a, b in zip(values, values[1:]))
