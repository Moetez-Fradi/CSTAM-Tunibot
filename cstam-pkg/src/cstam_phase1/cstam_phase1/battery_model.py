"""Pure energy model for the simulated CSTAM battery; no ROS dependencies.

Discharge power grows with the commanded motion actually measured on /odom:
an always-on electronics load plus terms proportional to linear and angular
speed. Charging is constant-power up to a taper point, then decreases
linearly, like the constant-current/constant-voltage phase of a Li-ion pack.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryParams:
    capacity_wh: float = 10.0
    idle_power_w: float = 4.0
    linear_power_w_per_mps: float = 25.0
    angular_power_w_per_radps: float = 6.0
    charge_power_w: float = 60.0
    # Above this state of charge the charging power tapers towards zero.
    taper_start: float = 0.8
    # Lowest fraction of charge_power used near full, so charging finishes.
    taper_floor: float = 0.1
    # 3S Li-ion pack: 9.9 V empty, 12.6 V full.
    empty_voltage: float = 9.9
    full_voltage: float = 12.6
    # Accelerates drain and charge for demonstrations; 1.0 is the real model.
    time_scale: float = 1.0


def discharge_power_w(linear_mps, angular_radps, params):
    return (params.idle_power_w
            + params.linear_power_w_per_mps * abs(linear_mps)
            + params.angular_power_w_per_radps * abs(angular_radps))


def charge_power_w(state_of_charge, params):
    if state_of_charge < params.taper_start:
        return params.charge_power_w
    remaining = (1.0 - state_of_charge) / max(1e-6, 1.0 - params.taper_start)
    return params.charge_power_w * max(params.taper_floor, remaining)


def net_power_w(energy_wh, linear_mps, angular_radps, charging, params):
    """Signed battery power: positive while charging, negative while draining."""
    draw = discharge_power_w(linear_mps, angular_radps, params)
    if not charging:
        return -draw
    return charge_power_w(energy_wh / params.capacity_wh, params) - draw


def step_energy_wh(energy_wh, dt_sec, linear_mps, angular_radps, charging, params):
    """Integrate stored energy over dt_sec and clamp it to [0, capacity]."""
    if dt_sec <= 0.0:
        return energy_wh
    power = net_power_w(energy_wh, linear_mps, angular_radps, charging, params)
    energy = energy_wh + power * dt_sec * params.time_scale / 3600.0
    return min(params.capacity_wh, max(0.0, energy))


def open_circuit_voltage(state_of_charge, params):
    """Piecewise-linear Li-ion curve: steep below 10%, nearly flat in the middle."""
    soc = min(1.0, max(0.0, state_of_charge))
    span = params.full_voltage - params.empty_voltage
    # (state of charge, fraction of the voltage span)
    curve = ((0.0, 0.0), (0.1, 0.45), (0.9, 0.85), (1.0, 1.0))
    for (soc_a, v_a), (soc_b, v_b) in zip(curve, curve[1:]):
        if soc <= soc_b:
            ratio = (soc - soc_a) / (soc_b - soc_a)
            return params.empty_voltage + span * (v_a + ratio * (v_b - v_a))
    return params.full_voltage
