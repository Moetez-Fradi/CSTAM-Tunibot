"""Pure dynamic-obstacle detection and tracking; numpy only, no ROS.

Pipeline per LiDAR scan (all in the map frame):
1. drop returns that lie on or near the static map (walls, tables);
2. split the remaining returns into clusters by scan-order gaps;
3. keep person-sized clusters and correct the visible-surface bias;
4. associate clusters with constant-velocity Kalman tracks; a confirmed
   track that vanishes inside the robot's own blind zone is kept, standing
   still, for occluded_max_age instead of being dropped;
5. predict where each confirmed moving track will be over a short horizon.
"""

import math

import numpy as np


def static_mask(grid, margin_cells, unknown_is_static=True):
    """Boolean mask of map cells within margin_cells of an occupied cell.

    grid: int8 array [rows=y, cols=x] with OccupancyGrid semantics.
    """
    occupied = grid >= 50
    if unknown_is_static:
        occupied |= grid < 0
    rows, cols = occupied.shape
    padded = np.zeros((rows + 2 * margin_cells, cols + 2 * margin_cells), dtype=bool)
    padded[margin_cells:margin_cells + rows, margin_cells:margin_cells + cols] = occupied
    mask = np.zeros_like(occupied)
    for dy in range(-margin_cells, margin_cells + 1):
        for dx in range(-margin_cells, margin_cells + 1):
            if dx * dx + dy * dy > margin_cells * margin_cells:
                continue
            mask |= padded[margin_cells + dy:margin_cells + dy + rows,
                           margin_cells + dx:margin_cells + dx + cols]
    return mask


class StaticMap:
    def __init__(self, grid, resolution, origin_x, origin_y, margin):
        self.resolution = resolution
        self.origin = (origin_x, origin_y)
        self.mask = static_mask(grid, max(0, int(round(margin / resolution))))

    def is_static(self, points):
        """Vectorised lookup; points outside the map count as static."""
        cols = np.floor((points[:, 0] - self.origin[0]) / self.resolution).astype(int)
        rows = np.floor((points[:, 1] - self.origin[1]) / self.resolution).astype(int)
        rows_n, cols_n = self.mask.shape
        inside = (cols >= 0) & (cols < cols_n) & (rows >= 0) & (rows < rows_n)
        result = np.ones(len(points), dtype=bool)
        result[inside] = self.mask[rows[inside], cols[inside]]
        return result


def cluster_scan_points(points, gap):
    """Split points (in scan order) wherever consecutive points are > gap apart.

    The first and last clusters are merged if the scan wraps around.
    """
    if len(points) == 0:
        return []
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    breaks = np.nonzero(steps > gap)[0] + 1
    clusters = np.split(points, breaks)
    if (len(clusters) > 1
            and np.linalg.norm(clusters[0][0] - clusters[-1][-1]) <= gap):
        clusters[0] = np.vstack([clusters[-1], clusters[0]])
        clusters.pop()
    return clusters


def person_detections(clusters, sensor_xy, min_points=2, min_width=0.08,
                      max_width=1.0, surface_offset=0.10):
    """Centroids of person-sized clusters, pushed away from the sensor.

    The LiDAR only sees the near surface of a body, so the true centre lies
    roughly surface_offset further along the viewing ray.
    """
    detections = []
    sensor = np.asarray(sensor_xy, dtype=float)
    for cluster in clusters:
        if len(cluster) < min_points:
            continue
        width = float(np.linalg.norm(cluster.max(axis=0) - cluster.min(axis=0)))
        if not min_width <= width <= max_width:
            continue
        centre = cluster.mean(axis=0)
        ray = centre - sensor
        norm = float(np.linalg.norm(ray))
        if norm > 1e-6:
            centre = centre + ray / norm * surface_offset
        detections.append(centre)
    return detections


def remove_near(points_xy, centres, radius):
    """Boolean keep-mask: False for points within radius of any centre."""
    keep = np.ones(len(points_xy), dtype=bool)
    for centre in centres:
        keep &= np.hypot(points_xy[:, 0] - centre[0], points_xy[:, 1] - centre[1]) > radius
    return keep


def merge_detections(detections, radius):
    """Average detections closer than radius (one person seen by two sensors)."""
    merged = []
    for detection in detections:
        for group in merged:
            if np.linalg.norm(group[0] / group[1] - detection) < radius:
                group[0] += detection
                group[1] += 1
                break
        else:
            merged.append([np.array(detection, dtype=float), 1])
    return [total / count for total, count in merged]


class Track:
    """Constant-velocity Kalman filter on state [x, y, vx, vy]."""

    def __init__(self, track_id, position, stamp, accel_noise, measurement_noise):
        self.id = track_id
        self.x = np.array([position[0], position[1], 0.0, 0.0])
        self.P = np.diag([0.05, 0.05, 1.0, 1.0])
        self.stamp = stamp
        self.last_seen = stamp
        self.last_measurement = np.array(position, dtype=float)
        self.hits = 1
        self.accel_noise = accel_noise
        self.R = np.eye(2) * measurement_noise ** 2

    def predict(self, stamp):
        dt = max(0.0, stamp - self.stamp)
        self.stamp = stamp
        if dt == 0.0:
            return
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        q = self.accel_noise ** 2
        dt2, dt3, dt4 = dt * dt, dt ** 3, dt ** 4
        Q = q * np.array([
            [dt4 / 4, 0, dt3 / 2, 0],
            [0, dt4 / 4, 0, dt3 / 2],
            [dt3 / 2, 0, dt2, 0],
            [0, dt3 / 2, 0, dt2]])
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q

    def update(self, position, stamp):
        H = np.zeros((2, 4))
        H[0, 0] = H[1, 1] = 1.0
        innovation = np.asarray(position) - H @ self.x
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ innovation
        self.P = (np.eye(4) - K @ H) @ self.P
        self.last_seen = stamp
        self.last_measurement = np.array(position, dtype=float)
        self.hits += 1

    @property
    def position(self):
        return self.x[:2].copy()

    @property
    def velocity(self):
        return self.x[2:].copy()

    @property
    def speed(self):
        return float(np.linalg.norm(self.x[2:]))


class MultiTracker:
    def __init__(self, gate=0.7, max_age=0.8, confirm_hits=3,
                 accel_noise=2.0, measurement_noise=0.08, max_speed=2.0,
                 occluded_max_age=10.0, standing_max_age=3.0, standing_speed=0.2):
        self.gate = gate
        self.max_age = max_age
        # A standing person (e.g. in a doorway, half hidden by the jambs and
        # partly removed by the static-map filter) is kept longer, so the
        # track does not flicker and the planner does not flip routes.
        self.standing_max_age = standing_max_age
        self.standing_speed = standing_speed
        self.occluded_max_age = occluded_max_age
        self.confirm_hits = confirm_hits
        self.accel_noise = accel_noise
        self.measurement_noise = measurement_noise
        self.max_speed = max_speed
        self.tracks = []
        self._next_id = 1

    def update(self, detections, stamp, is_occluded=None):
        """is_occluded(position) -> True where the sensor cannot see."""
        for track in self.tracks:
            track.predict(stamp)
        # Greedy nearest-neighbour association inside the gate.
        pairs = []
        for ti, track in enumerate(self.tracks):
            for di, detection in enumerate(detections):
                distance = float(np.linalg.norm(track.position - detection))
                if distance <= self.gate:
                    pairs.append((distance, ti, di))
        pairs.sort()
        used_tracks, used_detections = set(), set()
        for _, ti, di in pairs:
            if ti in used_tracks or di in used_detections:
                continue
            self.tracks[ti].update(detections[di], stamp)
            used_tracks.add(ti)
            used_detections.add(di)
        for di, detection in enumerate(detections):
            if di not in used_detections:
                self.tracks.append(Track(
                    self._next_id, detection, stamp,
                    self.accel_noise, self.measurement_noise))
                self._next_id += 1
        # Clamp implausible velocities (association jumps) and expire tracks.
        survivors = []
        for ti, track in enumerate(self.tracks):
            speed = track.speed
            if speed > self.max_speed:
                track.x[2:] *= self.max_speed / speed
            age = stamp - track.last_seen
            standing = track.hits >= self.confirm_hits and track.speed < self.standing_speed
            if age <= self.max_age or (standing and age <= self.standing_max_age):
                survivors.append(track)
            elif (is_occluded is not None and track.hits >= self.confirm_hits
                  and age <= self.occluded_max_age
                  and is_occluded(track.position)):
                # Unseen but plausibly still there: assume they stopped where
                # last measured. Extrapolating at the old velocity for
                # max_age would park the memory up to ~1 m from the person.
                track.x[:2] = track.last_measurement
                track.x[2:] = 0.0
                survivors.append(track)
        self.tracks = survivors
        return self.confirmed()

    def confirmed(self):
        return [t for t in self.tracks if t.hits >= self.confirm_hits]


def disc_points(centre, radius, spacing):
    """Grid samples filling a disc, so a costmap marks the full area."""
    steps = int(math.ceil(radius / spacing))
    offsets = np.arange(-steps, steps + 1) * spacing
    xs, ys = np.meshgrid(offsets, offsets)
    inside = xs ** 2 + ys ** 2 <= radius ** 2 + 1e-9
    return np.column_stack([xs[inside] + centre[0], ys[inside] + centre[1]])


def predicted_footprints(tracks, horizon, time_step, radius, growth,
                         min_speed, spacing):
    """(current, future) disc samples: every track now, moving ones ahead.

    The future discs grow with time to cover the prediction uncertainty.
    """
    current, future = [], []
    for track in tracks:
        position, velocity = track.position, track.velocity
        current.append(disc_points(position, radius, spacing))
        if track.speed < min_speed:
            continue
        t = time_step
        while t <= horizon + 1e-9:
            future.append(disc_points(position + velocity * t, radius + growth * t, spacing))
            t += time_step
    empty = np.zeros((0, 2))
    return (np.vstack(current) if current else empty,
            np.vstack(future) if future else empty)


def clearing_ring(radius, count):
    angles = np.linspace(-math.pi, math.pi, count, endpoint=False)
    return np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])
