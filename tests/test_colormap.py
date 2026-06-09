"""Tests for the plasma colormap.

Runs without Blender. Execute with: python -m pytest tests/
"""

import numpy as np
import pytest

from core.colormap import apply_colormap


def test_plasma_endpoints():
    rgb = apply_colormap(np.array([0.0, 1.0]))
    # Plasma runs from dark blue to yellow.
    assert np.allclose(rgb[0], (0.05038, 0.02980, 0.52797), atol=1e-4)
    assert np.allclose(rgb[1], (0.94002, 0.97516, 0.13133), atol=1e-4)


def test_shape_preserved_with_rgb_axis():
    vals = np.zeros((4, 7))
    rgb = apply_colormap(vals)
    assert rgb.shape == (4, 7, 3)


def test_values_are_clamped():
    rgb = apply_colormap(np.array([-1.0, 2.0]))
    # Out-of-range values clamp to the colormap endpoints.
    assert np.allclose(rgb[0], apply_colormap(np.array([0.0]))[0])
    assert np.allclose(rgb[1], apply_colormap(np.array([1.0]))[0])


def test_monotonic_brightness_increase():
    # Plasma luminance rises with the value; check the mean channel increases.
    samples = apply_colormap(np.linspace(0.0, 1.0, 16))
    means = samples.mean(axis=1)
    assert np.all(np.diff(means) > 0)


def test_unknown_colormap_raises():
    with pytest.raises(ValueError):
        apply_colormap(np.array([0.5]), name="does-not-exist")
