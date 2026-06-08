"""Tests for the Range-Doppler processing and Doppler evaluation.

Runs without Blender. Execute with: python -m pytest tests/

These tests synthesize a known beat cube and confirm that targets appear at
the expected range and velocity in the RDM, which is the acceptance criterion
for milestone 2.
"""

import math

import numpy as np
import pytest

from core.doppler import (
    frequency_to_velocity,
    velocity_axis,
    velocity_to_frequency,
)
from core.range_doppler import (
    find_peak,
    magnitude_db,
    range_axis,
    range_doppler_map,
)
from core.signal_model import RadarConfig, synthesize_beat_cube


def _config():
    return RadarConfig(
        carrier_freq=77e9,
        bandwidth=250e6,
        sample_rate=10e6,
        n_samples=256,
        n_chirps=128,
        chirp_period=30e-6,
    )


def _nearest(axis, value):
    return int(np.argmin(np.abs(axis - value)))


# --- axes -------------------------------------------------------------------


def test_range_axis():
    cfg = _config()
    axis = range_axis(cfg)
    assert axis.shape == (cfg.n_samples,)
    assert axis[0] == 0.0
    assert math.isclose(axis[1], cfg.range_resolution)


def test_velocity_axis_centered_and_monotonic():
    cfg = _config()
    axis = velocity_axis(cfg)
    assert axis.shape == (cfg.n_chirps,)
    assert np.all(np.diff(axis) > 0)
    # Even chirp count: spans [-max_velocity, +max_velocity).
    assert math.isclose(axis[0], -cfg.max_velocity, rel_tol=1e-9)


def test_velocity_frequency_roundtrip():
    lam = 0.0039
    v = np.array([-12.0, -3.0, 0.0, 7.5])
    f = velocity_to_frequency(v, lam)
    assert np.allclose(frequency_to_velocity(f, lam), v)


# --- RDM peak location ------------------------------------------------------


def test_single_target_peak_location():
    cfg = _config()
    true_range, true_velocity = 30.0, 5.0
    cube = synthesize_beat_cube(cfg, [true_range], [true_velocity], [1.0])
    rdm = range_doppler_map(cube, window="hann")

    rng, vel, _ = find_peak(rdm, cfg)
    assert abs(rng - true_range) <= cfg.range_resolution
    assert abs(vel - true_velocity) <= cfg.velocity_resolution


def test_receding_target_has_positive_velocity():
    cfg = _config()
    cube = synthesize_beat_cube(cfg, [40.0], [8.0], [1.0])
    _, vel, _ = find_peak(range_doppler_map(cube), cfg)
    assert vel > 0.0


def test_approaching_target_has_negative_velocity():
    cfg = _config()
    cube = synthesize_beat_cube(cfg, [40.0], [-8.0], [1.0])
    _, vel, _ = find_peak(range_doppler_map(cube), cfg)
    assert vel < 0.0


def test_zero_velocity_static_target():
    cfg = _config()
    cube = synthesize_beat_cube(cfg, [50.0], [0.0], [1.0])
    _, vel, _ = find_peak(range_doppler_map(cube), cfg)
    assert abs(vel) <= cfg.velocity_resolution


def test_two_targets_appear_at_their_cells():
    cfg = _config()
    ranges = [20.0, 60.0]
    velocities = [-6.0, 9.0]
    cube = synthesize_beat_cube(cfg, ranges, velocities, [1.0, 1.0])
    rdm = range_doppler_map(cube, window="hann")
    mag = np.abs(rdm)
    peak = mag.max()

    r_axis = range_axis(cfg)
    v_axis = velocity_axis(cfg)
    for r, v in zip(ranges, velocities):
        ri = _nearest(r_axis, r)
        vi = _nearest(v_axis, v)
        # Each target's expected cell carries near-peak energy.
        assert mag[vi, ri] >= 0.5 * peak


# --- magnitude_db -----------------------------------------------------------


def test_magnitude_db_floor_is_finite():
    rdm = np.zeros((4, 4), dtype=np.complex128)
    assert np.isfinite(magnitude_db(rdm)).all()


# --- window validation ------------------------------------------------------


def test_unknown_window_raises():
    cfg = _config()
    cube = synthesize_beat_cube(cfg, [10.0], [0.0])
    with pytest.raises(ValueError):
        range_doppler_map(cube, window="triangle")
