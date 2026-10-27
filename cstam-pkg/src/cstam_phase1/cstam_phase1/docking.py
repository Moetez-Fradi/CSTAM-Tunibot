"""Final docking approach: from Nav2's goal tolerance onto the dock pose.

Nav2 accepts the dock goal within 0.25 m (a tighter goal tolerance makes the
controller oscillate in the 1.86 m corridor). This slow point-turn-point
controller then closes the remaining error: turn towards the dock point,
drive straight (backwards if it is behind), and turn to the dock heading.
Pure functions, no ROS; the task manager feeds it the AMCL pose and sends
the command through the collision monitor, so people still stop it.
"""

from dataclasses import dataclass
import math


def _wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def _clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class DockingParams:
    xy_tolerance: float = 0.04     # m, done when within this ...
    yaw_tolerance: float = 0.04    # rad, ... and this
    xy_release: float = 0.08       # m, final turn restarts the approach only beyond this
    heading_tolerance: float = 0.12  # rad, drive only when this well aligned
    max_speed: float = 0.12        # m/s
    min_speed: float = 0.03        # m/s, below this the wheels barely move
    max_turn: float = 0.6          # rad/s
    min_turn: float = 0.15         # rad/s
    gain: float = 1.2


class DockApproach:
    """Call step(pose) at a fixed rate; returns (linear, angular, done)."""

    def __init__(self, target, params=None):
        self.target = target          # (x, y, yaw) in the map frame
        self.params = params or DockingParams()
        self.final_turn = False

    def error(self, pose):
        """(distance, heading error to the dock heading) from pose."""
        return (math.hypot(self.target[0] - pose[0], self.target[1] - pose[1]),
                _wrap(self.target[2] - pose[2]))

    def _turn(self, error):
        p = self.params
        rate = _clamp(p.gain * error, -p.max_turn, p.max_turn)
        if abs(rate) < p.min_turn:
            rate = math.copysign(p.min_turn, error)
        return rate

    def step(self, pose):
        p = self.params
        x, y, yaw = pose
        distance, yaw_error = self.error(pose)
        if self.final_turn and distance > p.xy_release:
            self.final_turn = False
        if not self.final_turn and distance <= p.xy_tolerance:
            self.final_turn = True
        if self.final_turn:
            if abs(yaw_error) <= p.yaw_tolerance:
                return 0.0, 0.0, True
            return 0.0, self._turn(yaw_error), False

        bearing = math.atan2(self.target[1] - y, self.target[0] - x)
        direction = 1.0
        heading_error = _wrap(bearing - yaw)
        if abs(heading_error) > math.pi / 2:  # the point is behind: back up to it
            direction = -1.0
            heading_error = _wrap(heading_error + math.pi)
        if abs(heading_error) > p.heading_tolerance:
            return 0.0, self._turn(heading_error), False
        speed = _clamp(p.gain * distance, p.min_speed, p.max_speed)
        # Gentle steering while driving keeps the line without stopping.
        steer = _clamp(p.gain * heading_error, -p.max_turn, p.max_turn)
        return direction * speed, steer, False
