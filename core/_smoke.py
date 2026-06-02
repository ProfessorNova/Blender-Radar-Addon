"""Trivial Blender-independent function to exercise the test setup."""

import numpy as np


def magnitude_db(values):
    """Return magnitude in decibels for an array of complex samples.

    Args:
        values: Array-like of complex or real samples.

    Returns:
        numpy.ndarray of 20*log10(abs(values)) with a small floor to avoid
        log of zero.
    """
    arr = np.abs(np.asarray(values, dtype=np.complex128))
    floor = 1e-12  # avoids -inf for zero samples
    return 20.0 * np.log10(np.maximum(arr, floor))
