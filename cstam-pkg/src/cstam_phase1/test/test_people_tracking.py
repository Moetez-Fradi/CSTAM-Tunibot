import math

import numpy as np

from cstam_phase1.people_tracking import (
    MultiTracker,
    StaticMap,
    cluster_scan_points,
    disc_points,
    merge_detections,
    person_detections,
    predicted_footprints,
    remove_near,
    static_mask,
)


def test_static_mask_dilates_occupied_and_unknown_cells():
    grid = np.zeros((11, 11), dtype=np.int8)
    grid[5, 5] = 100
    grid[0, 10] = -1
    mask = static_mask(grid, 2)
    assert mask[5, 5] and mask[5, 7] and mask[7, 5]
    assert not mask[5, 8]
    assert mask[0, 10] and mask[1, 9]


def test_static_map_filters_wall_points_but_keeps_free_points():
    grid = np.zeros((40, 40), dtype=np.int8)
    grid[:, 20] = 100  # vertical wall at x = 1.0 m
    static = StaticMap(grid, 0.05, 0.0, 0.0, margin=0.2)
    points = np.array([[1.02, 1.0], [1.15, 1.0], [0.4, 1.0], [-1.0, 1.0]])
    assert static.is_static(points).tolist() == [True, True, False, True]


def test_clustering_splits_on_gaps_and_merges_wraparound():
    a = np.array([[1.0, 0.0], [1.0, 0.05], [1.0, 0.1]])
    b = np.array([[3.0, 2.0], [3.0, 2.05]])
    clusters = cluster_scan_points(np.vstack([a, b]), gap=0.25)
    assert [len(c) for c in clusters] == [3, 2]
    wrapped = cluster_scan_points(np.vstack([a[1:], b, a[:1]]), gap=0.25)
    assert sorted(len(c) for c in wrapped) == [2, 3]


def test_person_detection_rejects_walls_and_corrects_surface_bias():
    arc = np.array([[2.0, -0.15], [1.95, -0.05], [1.95, 0.05], [2.0, 0.15]])
    wall = np.column_stack([np.full(40, 3.0), np.linspace(-1.0, 1.0, 40)])
    detections = person_detections([arc, wall], sensor_xy=(0.0, 0.0))
    assert len(detections) == 1
    assert detections[0][0] > arc[:, 0].mean()  # pushed away from the sensor


def test_tracker_estimates_velocity_and_confirms_after_hits():
    tracker = MultiTracker(confirm_hits=3)
    confirmed = []
    for i in range(20):
        t = i * 0.125  # 8 Hz LiDAR
        confirmed = tracker.update([np.array([1.0 * t, 2.0])], t)
    assert len(confirmed) == 1
    vx, vy = confirmed[0].velocity
    assert math.isclose(vx, 1.0, abs_tol=0.1)
    assert abs(vy) < 0.1


def test_tracker_keeps_two_crossing_people_separate_and_expires_lost_ones():
    tracker = MultiTracker()
    for i in range(16):
        t = i * 0.125
        tracker.update([np.array([t, 0.0]), np.array([4.0 - t, 3.0])], t)
    ids = {track.id for track in tracker.confirmed()}
    assert len(ids) == 2
    tracker.update([], 2.0 + tracker.max_age + 0.1)
    assert tracker.tracks == []


def test_predictions_cover_future_path_only_for_moving_tracks():
    tracker = MultiTracker()
    for i in range(16):
        t = i * 0.125
        tracker.update([np.array([t, 0.0]), np.array([5.0, 5.0])], t)
    current, future = predicted_footprints(
        tracker.confirmed(), horizon=2.0, time_step=0.4, radius=0.3,
        growth=0.05, min_speed=0.2, spacing=0.05)
    assert len(current) == 2 * len(disc_points((0, 0), 0.3, 0.05))
    # The 1 m/s walker (now at x~1.9) reaches x~3.9 within 2 s; the stander adds none.
    assert future[:, 0].max() > 3.5
    assert np.all(np.abs(future[:, 1]) < 1.0)


def test_track_hidden_in_blind_zone_is_kept_standing_still():
    tracker = MultiTracker(occluded_max_age=10.0)
    for i in range(16):
        t = i * 0.125
        tracker.update([np.array([1.0 + 0.5 * t, 0.0])], t)
    # The person walks into the blind zone and stops being detected.
    blind = lambda position: position[0] > 1.5  # noqa: E731
    for i in range(1, 40):
        kept = tracker.update([], 2.0 + i * 0.125, blind)
    assert len(kept) == 1
    assert kept[0].speed == 0.0
    # Outside the blind zone the normal 0.8 s expiry still applies.
    tracker.update([], 30.0, blind)
    assert tracker.tracks == []
    for i in range(16):
        tracker.update([np.array([0.0, 5.0])], 40.0 + i * 0.125)
    tracker.update([], 45.0, blind)
    assert tracker.tracks == []


def test_merge_detections_fuses_one_person_seen_by_two_sensors():
    merged = merge_detections(
        [np.array([1.0, 0.0]), np.array([1.2, 0.0]), np.array([3.0, 0.0])], 0.45)
    assert len(merged) == 2
    assert np.allclose(merged[0], [1.1, 0.0])


def test_remove_near_masks_points_around_people_only():
    points = np.array([[0.0, 0.0], [0.3, 0.0], [1.0, 0.0], [5.0, 5.0]])
    keep = remove_near(points, [(0.0, 0.0)], 0.45)
    assert keep.tolist() == [False, False, True, True]
    assert remove_near(points, [], 0.45).all()


def test_occluded_track_freezes_at_last_measurement_not_extrapolation():
    tracker = MultiTracker(occluded_max_age=10.0)
    for i in range(16):
        t = i * 0.125
        tracker.update([np.array([1.0 * t, 0.0])], t)  # walking at 1 m/s
    last = 15 * 0.125
    for i in range(1, 16):
        kept = tracker.update([], last + i * 0.125, lambda position: True)
    assert len(kept) == 1
    assert abs(kept[0].position[0] - last) < 0.1  # not ~0.8 m further on
