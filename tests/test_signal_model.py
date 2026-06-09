"""Tests for the FMCW signal model.

Runs without Blender. Execute with: python -m pytest tests/
"""

import math

import numpy as np
import pytest

from core.signal_model import (
    SPEED_OF_LIGHT,
    RadarConfig,
    radar_equation_amplitude,
    reflectivity_to_rcs,
    synthesize_beat_cube,
)


def _config():
    """A typical automotive-style 77 GHz FMCW configuration."""
    return RadarConfig(
        carrier_freq=77e9,
        bandwidth=250e6,
        sample_rate=10e6,
        n_samples=256,
        n_chirps=128,
        chirp_period=30e-6,
    )


# --- RadarConfig ------------------------------------------------------------


def test_config_derived_values():
    cfg = _config()
    assert math.isclose(cfg.chirp_duration, 256 / 10e6)
    assert math.isclose(cfg.slope, cfg.bandwidth / cfg.chirp_duration)
    assert math.isclose(cfg.wavelength, SPEED_OF_LIGHT / 77e9)
    assert math.isclose(cfg.range_resolution, SPEED_OF_LIGHT / (2 * 250e6))
    assert math.isclose(cfg.max_range, 256 * cfg.range_resolution)
    assert math.isclose(
        cfg.velocity_resolution, cfg.wavelength / (2 * 128 * 30e-6)
    )
    assert math.isclose(cfg.max_velocity, cfg.wavelength / (4 * 30e-6))


def test_config_rejects_bad_values():
    with pytest.raises(ValueError):
        RadarConfig(0.0, 250e6, 10e6, 256, 128, 30e-6)
    with pytest.raises(ValueError):
        RadarConfig(77e9, 250e6, 10e6, 0, 128, 30e-6)
    # chirp_period shorter than the active chirp duration is invalid.
    with pytest.raises(ValueError):
        RadarConfig(77e9, 250e6, 10e6, 256, 128, 1e-6)


# --- radar_equation_amplitude ----------------------------------------------


def test_radar_equation_inverse_square_voltage():
    amp = radar_equation_amplitude([1.0, 2.0, 4.0])
    # Voltage amplitude scales as 1/R^2: doubling range quarters amplitude.
    assert math.isclose(amp[0] / amp[1], 4.0)
    assert math.isclose(amp[1] / amp[2], 4.0)


def test_radar_equation_scales_with_sqrt_rcs():
    amp = radar_equation_amplitude([10.0, 10.0], rcs=[1.0, 4.0])
    assert math.isclose(amp[1] / amp[0], 2.0)


# --- reflectivity_to_rcs ----------------------------------------------------


def test_reflectivity_to_rcs_endpoints_and_clamp():
    # 0 -> low, 1 -> high, linear in between, clamped outside [0, 1].
    rcs = reflectivity_to_rcs([0.0, 1.0, 0.5], low=1.0, high=100.0)
    assert math.isclose(rcs[0], 1.0)
    assert math.isclose(rcs[1], 100.0)
    assert math.isclose(rcs[2], 50.5)
    clamped = reflectivity_to_rcs([-1.0, 2.0], low=1.0, high=100.0)
    assert math.isclose(clamped[0], 1.0)
    assert math.isclose(clamped[1], 100.0)


# --- synthesize_beat_cube ---------------------------------------------------


def test_beat_cube_shape_and_dtype():
    cfg = _config()
    cube = synthesize_beat_cube(cfg, [30.0], [5.0])
    assert cube.shape == (cfg.n_chirps, cfg.n_samples)
    assert cube.dtype == np.complex128


def test_beat_cube_superposition_is_linear():
    cfg = _config()
    a = synthesize_beat_cube(cfg, [20.0], [3.0], [1.0])
    b = synthesize_beat_cube(cfg, [60.0], [-4.0], [1.0])
    both = synthesize_beat_cube(cfg, [20.0, 60.0], [3.0, -4.0], [1.0, 1.0])
    assert np.allclose(a + b, both)


def test_beat_cube_validates_lengths():
    cfg = _config()
    with pytest.raises(ValueError):
        synthesize_beat_cube(cfg, [1.0, 2.0], [1.0])
    with pytest.raises(ValueError):
        synthesize_beat_cube(cfg, [1.0], [1.0], [1.0, 2.0])
