"""Tests for the thermal-noise and clutter model.

Runs without Blender. Execute with: python -m pytest tests/
"""

import numpy as np

from core.noise import clutter_targets, thermal_noise


# --- thermal_noise ----------------------------------------------------------


def test_thermal_noise_shape_and_dtype():
    n = thermal_noise((4, 8), 1.0, np.random.default_rng(0))
    assert n.shape == (4, 8)
    assert n.dtype == np.complex128


def test_thermal_noise_zero_std_is_zero():
    n = thermal_noise((3, 3), 0.0, np.random.default_rng(0))
    assert np.all(n == 0.0)


def test_thermal_noise_reproducible_with_same_seed():
    a = thermal_noise((16, 16), 0.5, np.random.default_rng(42))
    b = thermal_noise((16, 16), 0.5, np.random.default_rng(42))
    assert np.array_equal(a, b)


def test_thermal_noise_power_matches_std():
    # E[|n|^2] should approach std**2 over many samples.
    std = 2.0
    n = thermal_noise(200_000, std, np.random.default_rng(1))
    measured = np.mean(np.abs(n) ** 2)
    assert np.isclose(measured, std**2, rtol=0.05)


# --- clutter_targets --------------------------------------------------------


def test_clutter_targets_count_and_stationary():
    ranges, velocities, amps = clutter_targets(
        50, max_range=100.0, amplitude_std=0.1, rng=np.random.default_rng(0)
    )
    assert ranges.shape == velocities.shape == amps.shape == (50,)
    # Clutter is stationary: zero radial velocity, so it lands at zero Doppler.
    assert np.all(velocities == 0.0)
    assert amps.dtype == np.complex128


def test_clutter_targets_ranges_within_bounds():
    ranges, _, _ = clutter_targets(
        1000, max_range=80.0, amplitude_std=0.1,
        rng=np.random.default_rng(0), min_range=5.0,
    )
    assert ranges.min() >= 5.0
    assert ranges.max() <= 80.0


def test_clutter_targets_empty_when_count_zero():
    ranges, velocities, amps = clutter_targets(
        0, max_range=100.0, amplitude_std=0.1, rng=np.random.default_rng(0)
    )
    assert ranges.shape == velocities.shape == amps.shape == (0,)


def test_clutter_targets_reproducible_with_same_seed():
    a = clutter_targets(20, 100.0, 0.1, np.random.default_rng(7))
    b = clutter_targets(20, 100.0, 0.1, np.random.default_rng(7))
    for x, y in zip(a, b):
        assert np.array_equal(x, y)


def test_clutter_falloff_fades_amplitude_with_range():
    n = 4000
    ranges, _, amps = clutter_targets(
        n, max_range=100.0, amplitude_std=1.0,
        rng=np.random.default_rng(0), min_range=5.0, falloff_exp=1.0,
    )
    near = np.abs(amps[ranges < 30.0])
    far = np.abs(amps[ranges > 70.0])
    # With a 1/R falloff, near clutter is on average stronger than far clutter.
    assert near.mean() > far.mean()


def test_clutter_falloff_zero_matches_uniform():
    # falloff_exp=0 must leave the amplitudes untouched (same RNG stream).
    a = clutter_targets(100, 100.0, 0.5, np.random.default_rng(3), falloff_exp=0.0)
    b = clutter_targets(100, 100.0, 0.5, np.random.default_rng(3))
    assert np.array_equal(a[2], b[2])
