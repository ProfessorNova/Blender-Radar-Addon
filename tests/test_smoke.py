"""Smoke test for the Blender-independent core.

Runs without Blender. Execute with: python -m pytest tests/
"""

import numpy as np

from core._smoke import magnitude_db


def test_magnitude_db_unit_amplitude():
    result = magnitude_db([1.0, 1.0])
    assert np.allclose(result, 0.0)


def test_magnitude_db_handles_zero():
    result = magnitude_db([0.0])
    assert np.isfinite(result).all()
