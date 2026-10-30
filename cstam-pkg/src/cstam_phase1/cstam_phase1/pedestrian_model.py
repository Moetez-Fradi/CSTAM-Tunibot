"""Pure pedestrian motion model for the restaurant simulation; no ROS here.

Each pedestrian walks a route in the map frame. Behaviour types:

* ``polite``: notices the robot ahead and slows down. If its lane already
  passes the robot comfortably it just walks by; otherwise it steps into a
  free side lane, and if there is none it stops and waits.
* ``oblivious``: keeps walking at full speed and never steps aside. It only
  stops when the next step would physically touch the robot or another
  person, so the robot alone is responsible for keeping its distance.

A lane is only taken if every point along it, for the next few metres, is
free on the static map and keeps clearance from the robot. Nobody waits
forever: after ``patience`` seconds held up (by the robot or another
person) people detour through the widest valid lane, keeping personal space
from the robot. Without real progress towards the next waypoint for about
three patience periods (staggered per person), they give way and walk back,
or skip the waypoint if the robot stands on it.
"""

from dataclasses import dataclass, field
import math


# Robot footprint in base_footprint, identical to the Nav2 footprint.
ROBOT_X_MIN, ROBOT_X_MAX = -0.31, 0.35
ROBOT_Y_HALF = 0.27
PERSON_RADIUS = 0.22


def footprint_clearance(robot_pose, point, radius=PERSON_RADIUS):
    """Distance from the robot rectangle to a person disc (negative = overlap)."""
    rx, ry, ryaw = robot_pose
    dx, dy = point[0] - rx, point[1] - ry
    cos_y, sin_y = math.cos(ryaw), math.sin(ryaw)
    local_x = cos_y * dx + sin_y * dy
    local_y = -sin_y * dx + cos_y * dy
    out_x = max(ROBOT_X_MIN - local_x, 0.0, local_x - ROBOT_X_MAX)
    out_y = max(-ROBOT_Y_HALF - local_y, 0.0, local_y - ROBOT_Y_HALF)
    return math.hypot(out_x, out_y) - radius


def _wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


@dataclass
class PedestrianConfig:
    name: str
    route: list            # [(x, y, dwell_sec), ...] in the map frame
    behavior: str = 'polite'
    speed: float = 0.9
    mode: str = 'pingpong'  # 'pingpong' or 'loop'
    start_delay: float = 0.0
    color: tuple = (0.2, 0.4, 0.8)
    vip: bool = False      # wears the VIP colour the robot's camera looks for

    @classmethod
    def from_dict(cls, data):
        route = []
        for waypoint in data['route']:
            dwell = float(waypoint[2]) if len(waypoint) > 2 else 0.0
            route.append((float(waypoint[0]), float(waypoint[1]), dwell))
        if len(route) < 2:
            raise ValueError(f'pedestrian {data["name"]} needs at least two waypoints')
        behavior = str(data.get('behavior', 'polite'))
        if behavior not in ('polite', 'oblivious'):
            raise ValueError(f'unknown behavior {behavior}')
        mode = str(data.get('mode', 'pingpong'))
        if mode not in ('pingpong', 'loop'):
            raise ValueError(f'unknown route mode {mode}')
        return cls(
            name=str(data['name']), route=route, behavior=behavior,
            speed=float(data.get('speed', 0.9)), mode=mode,
            start_delay=float(data.get('start_delay', 0.0)),
            color=tuple(float(c) for c in data.get('color', (0.2, 0.4, 0.8))),
            vip=bool(data.get('vip', False)))


@dataclass
class PedestrianParams:
    accel: float = 1.0               # m/s^2 speed change limit
    turn_rate: float = 3.0           # rad/s heading change limit
    notice_distance: float = 2.5     # robot noticed within this range
    notice_half_angle: float = 1.2   # rad, cone around walking direction
    polite_stop_clearance: float = 0.45
    polite_full_speed_clearance: float = 1.8
    polite_pass_clearance: float = 0.30  # lane clearance to just walk by
    passing_speed_factor: float = 0.6
    sidestep: float = 0.45           # m lateral offset of a polite side lane
    sidestep_rate: float = 0.5       # m/s lateral speed
    contact_margin: float = 0.03     # nobody walks closer than this
    person_spacing: float = 0.55     # centre distance kept from others
    patience: float = 4.0            # s held up before detouring
    progress_step: float = 0.25      # m closer to the waypoint that counts as progress
    # Detour lane offsets, widest first: in a narrow aisle people squeeze
    # along the wall rather than wait forever.
    detour_offsets: tuple = (0.95, 0.75, 0.6, 0.45)
    personal_space: float = 0.15     # detour lanes keep this from the robot
    lane_lookahead: float = 2.5      # m of lane checked before taking it
    detour_length: float = 2.0       # m of progress before rejoining the path
    detour_speed_factor: float = 0.5


@dataclass
class Pedestrian:
    config: PedestrianConfig
    params: PedestrianParams = field(default_factory=PedestrianParams)

    def __post_init__(self):
        first, second = self.config.route[0], self.config.route[1]
        self.nominal = [first[0], first[1]]
        self.offset = 0.0
        self.heading = math.atan2(second[1] - first[1], second[0] - first[0])
        # Lateral offsets are measured from the path segment, never from the
        # body heading: turning on the spot must not move the body.
        self.path_dir = self.heading
        self.speed = 0.0
        self.target = 1
        self.direction = 1
        self.dwell = first[2]
        self.delay = self.config.start_delay
        self.yielding = False
        self.held_time = 0.0
        self.detouring = False
        self.detour_offset = 0.0
        self.detour_progress = 0.0
        # Real progress towards the next waypoint. Unlike held_time it is not
        # reset by starting or abandoning a detour, so shuffling in and out
        # of side lanes without getting anywhere still counts as stuck.
        self.stuck_time = 0.0
        self.best_remaining = math.inf

    # Geometry ---------------------------------------------------------------
    def _right(self):
        return (math.sin(self.path_dir), -math.cos(self.path_dir))

    def _point(self, along, offset):
        """Point `along` metres ahead on the path, `offset` to the right."""
        right = self._right()
        return (self.nominal[0] + math.cos(self.path_dir) * along + right[0] * offset,
                self.nominal[1] + math.sin(self.path_dir) * along + right[1] * offset)

    @property
    def position(self):
        return self._point(0.0, self.offset)

    @property
    def velocity(self):
        return (self.speed * math.cos(self.heading), self.speed * math.sin(self.heading))

    def _remaining(self):
        tx, ty, _ = self.config.route[self.target]
        return math.hypot(tx - self.nominal[0], ty - self.nominal[1])

    def _lane_ok(self, offset, robot_pose, is_free, min_clearance, length, others=()):
        """Sweep from the current offset to `offset`, then `length` along it."""
        length = min(length, self._remaining())
        if robot_pose is not None:
            # Never closer than now: someone the robot already came close to
            # may still move away or along, just not further in. Nor below
            # the contact margin, which _blocked() would refuse to walk.
            current = footprint_clearance(robot_pose, self.position) - 0.01
            if current + 0.01 >= self.params.contact_margin:
                current = max(current, self.params.contact_margin)
            min_clearance = min(min_clearance, current)
        points = [self._point(0.0, self.offset + (offset - self.offset) * k / 4.0)
                  for k in range(1, 5)]
        steps = max(1, int(length / 0.2))
        points += [self._point(length * k / steps, offset) for k in range(1, steps + 1)]
        for point in points:
            if is_free is not None and not is_free(*point):
                return False
            if (robot_pose is not None
                    and footprint_clearance(robot_pose, point) < min_clearance):
                return False
            if any(math.hypot(point[0] - o[0], point[1] - o[1]) < self.params.person_spacing
                   for o in others):
                return False
        return True

    def _find_lane(self, offsets, robot_pose, is_free, min_clearance, others=()):
        for distance in offsets:
            for side in (1.0, -1.0):  # right first, as people usually do
                offset = side * distance
                if self._lane_ok(offset, robot_pose, is_free, min_clearance,
                                 self.params.lane_lookahead, others):
                    return offset
        return None

    # Route --------------------------------------------------------------------
    def _stagger(self):
        """Person-specific 0..1, so two people never retry in lockstep."""
        return (sum(map(ord, self.config.name)) % 5) / 4.0

    def _reset_progress(self):
        self.stuck_time = 0.0
        self.best_remaining = math.inf

    def _advance_target(self):
        route = self.config.route
        if self.config.mode == 'loop':
            self.target = (self.target + 1) % len(route)
        else:
            nxt = self.target + self.direction
            if not 0 <= nxt < len(route):
                self.direction = -self.direction
                nxt = self.target + self.direction
            self.target = nxt

    def _arrive(self, dwell):
        """Switch to the next segment without moving the body.

        The nominal point snaps back onto the waypoint and any lateral
        displacement is re-expressed as an offset from the new segment, so a
        person still stepped aside does not tilt their whole next path. If
        the displacement does not fit the new segment (a sharp corner), it is
        absorbed instead.
        """
        here = self.position
        waypoint = self.config.route[self.target][:2]
        self.dwell = dwell
        self.detouring = False
        self.held_time = 0.0
        self._reset_progress()
        self._advance_target()
        tx, ty, _ = self.config.route[self.target]
        self.path_dir = math.atan2(ty - waypoint[1], tx - waypoint[0])
        right = self._right()
        dx, dy = here[0] - waypoint[0], here[1] - waypoint[1]
        lateral = dx * right[0] + dy * right[1]
        along = dx * math.cos(self.path_dir) + dy * math.sin(self.path_dir)
        if abs(along) <= 0.06:
            self.nominal = [waypoint[0], waypoint[1]]
            self.offset = lateral
        else:
            self.nominal = list(here)
            self.offset = 0.0
            self.path_dir = math.atan2(ty - here[1], tx - here[0])

    def _turn_back(self):
        """Give way: walk back towards the previous waypoint."""
        here = self.position
        self.detouring = False
        self.held_time = 0.0
        self._reset_progress()
        if self.config.mode == 'pingpong':
            self.direction = -self.direction
            self.target = min(max(self.target + self.direction, 0),
                              len(self.config.route) - 1)
        else:
            self.target = (self.target - 1) % len(self.config.route)
        self.nominal = list(here)
        self.offset = 0.0
        tx, ty, _ = self.config.route[self.target]
        self.path_dir = math.atan2(ty - here[1], tx - here[0])

    # Perception of the robot ------------------------------------------------
    def _robot_ahead(self, robot_pose):
        """Clearance to the robot if it is inside the notice cone, else None."""
        if robot_pose is None:
            return None
        px, py = self.position
        dx, dy = robot_pose[0] - px, robot_pose[1] - py
        if math.hypot(dx, dy) > self.params.notice_distance + 0.5:
            return None
        if abs(_wrap(math.atan2(dy, dx) - self.heading)) > self.params.notice_half_angle:
            return None
        clearance = footprint_clearance(robot_pose, (px, py))
        return clearance if clearance <= self.params.notice_distance else None

    def _robot_passed(self, robot_pose):
        """True once the robot is behind the person (or far away)."""
        if robot_pose is None:
            return True
        px, py = self.position
        dx, dy = robot_pose[0] - px, robot_pose[1] - py
        forward = dx * math.cos(self.path_dir) + dy * math.sin(self.path_dir)
        return forward < -0.5 or math.hypot(dx, dy) > self.params.notice_distance + 1.0

    def _blocked(self, point, robot_pose, others, is_free):
        if robot_pose is not None:
            new_clear = footprint_clearance(robot_pose, point)
            # Moving away is always allowed, even for someone the robot
            # itself has pushed into contact.
            if (new_clear < self.params.contact_margin
                    and new_clear < footprint_clearance(robot_pose, self.position) - 1e-9):
                return True
        if is_free is not None and self.offset != 0.0 and not is_free(*point):
            return True  # never walk an offset lane into furniture
        here = self.position
        for other in others:
            new_gap = math.hypot(point[0] - other[0], point[1] - other[1])
            old_gap = math.hypot(here[0] - other[0], here[1] - other[1])
            if new_gap < self.params.person_spacing and new_gap < old_gap:
                return True
        return False

    # Main update --------------------------------------------------------------
    def step(self, dt, robot_pose=None, others=(), is_free=None):
        """Advance by dt seconds. others: positions of the other pedestrians."""
        p = self.params
        if self.delay > 0.0:
            self.delay -= dt
            return
        if self.dwell > 0.0:
            self.dwell -= dt
            self.speed = 0.0
            return

        tx, ty, tdwell = self.config.route[self.target]
        dx, dy = tx - self.nominal[0], ty - self.nominal[1]
        distance = math.hypot(dx, dy)
        if distance < 0.05:
            self._arrive(tdwell)
            return
        self.path_dir = math.atan2(dy, dx)
        if distance < self.best_remaining - p.progress_step:
            self.best_remaining = distance
            self.stuck_time = 0.0
        else:
            self.stuck_time += dt

        if (self.detouring and self.detour_progress >= p.detour_length
                and self._robot_passed(robot_pose)):
            self.detouring = False
        ahead = self._robot_ahead(robot_pose)
        desired_speed = self.config.speed
        desired_offset = self.offset if self.detouring else 0.0
        self.yielding = False
        if self.detouring:
            desired_offset = self.detour_offset
            desired_speed *= p.detour_speed_factor
        elif self.config.behavior == 'polite' and ahead is not None:
            self.yielding = True
            if self._lane_ok(0.0, robot_pose, is_free, p.polite_pass_clearance,
                             p.lane_lookahead):
                desired_speed *= p.passing_speed_factor  # just walk by
            else:
                lane = self._find_lane((p.sidestep,), robot_pose, is_free,
                                       p.polite_pass_clearance)
                if lane is not None:
                    desired_offset = lane
                    desired_speed *= p.passing_speed_factor
                else:
                    span = p.polite_full_speed_clearance - p.polite_stop_clearance
                    factor = (ahead - p.polite_stop_clearance) / span
                    desired_speed *= min(1.0, max(0.0, factor))
        # Slow to a stop at the waypoint instead of overshooting it.
        desired_speed = min(desired_speed, math.sqrt(2.0 * p.accel * distance) + 0.05)

        # Heading follows the path direction, with a bounded turn rate.
        turn = _wrap(self.path_dir - self.heading)
        max_turn = p.turn_rate * dt
        self.heading = _wrap(self.heading + max(-max_turn, min(max_turn, turn)))
        if abs(turn) > 1.0:
            desired_speed = 0.0  # turn in place at sharp corners

        change = desired_speed - self.speed
        self.speed = max(0.0, self.speed + max(-p.accel * dt, min(p.accel * dt, change)))
        offset_change = desired_offset - self.offset
        max_shift = p.sidestep_rate * dt
        new_offset = self.offset + max(-max_shift, min(max_shift, offset_change))
        step_len = min(self.speed * dt, distance)

        right = self._right()
        candidate = (self.nominal[0] + dx / distance * step_len + right[0] * new_offset,
                     self.nominal[1] + dy / distance * step_len + right[1] * new_offset)
        blocked = self._blocked(candidate, robot_pose, others, is_free)

        held = blocked or (ahead is not None and self.speed < 0.05)
        self.held_time = self.held_time + dt if held else 0.0
        if self.detouring and self.held_time > p.patience:
            # The chosen lane jammed (usually two people picking crossing
            # lanes at once). Give up and wait a person-specific extra time
            # before re-planning, so two people never retry in lockstep.
            self.detouring = False
            self.held_time = -self._stagger() * p.patience
        if self.held_time > p.patience and not self.detouring:
            lane = self._find_lane(p.detour_offsets, robot_pose, is_free,
                                   p.personal_space, others)
            if lane is not None:
                self.detouring = True
                self.detour_offset = lane
                self.detour_progress = 0.0
                self.held_time = 0.0
        if self.stuck_time > (3.0 + self._stagger()) * p.patience:
            # No real progress for a while, whatever the cause (the robot,
            # another person, or both): give way instead of waiting forever.
            # Staggered, so two people blocking each other do not both turn.
            if robot_pose is not None and footprint_clearance(robot_pose, (tx, ty)) < 0.3:
                self._arrive(0.0)  # the robot is standing on our waypoint
            else:
                self._turn_back()  # no way past (narrow aisle): give way
            return

        if blocked:
            self.speed = 0.0
            # A pure sidestep can still be taken while forward is blocked.
            sidestep = (self.nominal[0] + right[0] * new_offset,
                        self.nominal[1] + right[1] * new_offset)
            if new_offset != self.offset and not self._blocked(
                    sidestep, robot_pose, others, is_free):
                self.offset = new_offset
            return
        self.nominal = [self.nominal[0] + dx / distance * step_len,
                        self.nominal[1] + dy / distance * step_len]
        self.offset = new_offset
        if self.detouring:
            self.detour_progress += step_len
