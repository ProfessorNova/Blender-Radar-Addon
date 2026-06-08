"""Doppler-domain evaluation for the FMCW radar.

Blender-independent helpers that convert between Doppler frequency and radial
velocity and build the velocity axis of the Range-Doppler map. The Doppler FFT
itself lives in :mod:`core.range_doppler`; this module owns the interpretation
of its slow-time axis.

Sign convention (matches :mod:`core.signal_model` and :mod:`core.raytracing`):
positive velocity means the target is receding and maps to a positive Doppler
frequency.
"""

from __future__ import annotations

import numpy as np

from .signal_model import RadarConfig


def doppler_frequency_axis(config: RadarConfig) -> np.ndarray:
    """Centred Doppler frequency bins in Hz, one per chirp.

    The axis is ``fftshift``-ed so that zero Doppler is at the centre and the
    values increase monotonically, matching the Doppler FFT produced by
    :func:`core.range_doppler.range_doppler_map`.
    """
    return np.fft.fftshift(
        np.fft.fftfreq(config.n_chirps, d=config.chirp_period)
    )


def frequency_to_velocity(frequency, wavelength: float) -> np.ndarray:
    """Convert Doppler frequency (Hz) to radial velocity (m/s)."""
    return np.asarray(frequency, dtype=np.float64) * wavelength / 2.0


def velocity_to_frequency(velocity, wavelength: float) -> np.ndarray:
    """Convert radial velocity (m/s) to Doppler frequency (Hz)."""
    return 2.0 * np.asarray(velocity, dtype=np.float64) / wavelength


def velocity_axis(config: RadarConfig) -> np.ndarray:
    """Centred radial-velocity bins in m/s, one per chirp.

    Monotonically increasing and (for an even chirp count) spanning
    ``[-max_velocity, +max_velocity)``.
    """
    return frequency_to_velocity(
        doppler_frequency_axis(config), config.wavelength
    )
