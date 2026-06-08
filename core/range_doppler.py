"""Two-dimensional FFT processing for the Range-Doppler map.

Blender-independent. Turns the complex beat data cube from
:mod:`core.signal_model` into a Range-Doppler map (RDM):

* a *range* FFT along fast time (samples) maps beat frequency to range, then
* a *Doppler* FFT along slow time (chirps) maps the chirp-to-chirp phase
  progression to radial velocity.

The Doppler axis is ``fftshift``-ed so zero velocity sits at the centre.
Optional window functions reduce spectral sidelobes. The matching range and
velocity axes are provided so peaks can be read in physical units.
"""

from __future__ import annotations

import numpy as np

from .doppler import velocity_axis
from .signal_model import RadarConfig

# Window functions selectable by name. ``None`` / "none" means no window.
_WINDOWS = {
    "hann": np.hanning,
    "hamming": np.hamming,
    "blackman": np.blackman,
}


def _window(name, length: int) -> np.ndarray:
    """Return a window of ``length`` samples for the given name."""
    if name is None or name == "none":
        return np.ones(length, dtype=np.float64)
    try:
        return _WINDOWS[name](length).astype(np.float64)
    except KeyError:
        raise ValueError(
            f"unknown window '{name}'; choose from "
            f"{['none', *_WINDOWS]}"
        ) from None


def range_doppler_map(cube, window: str = "hann") -> np.ndarray:
    """Compute the complex Range-Doppler map from a beat data cube.

    Args:
        cube: Complex ``(n_chirps, n_samples)`` beat signal.
        window: Window applied along both axes before the FFTs. One of
            ``"none"``, ``"hann"``, ``"hamming"`` or ``"blackman"``.

    Returns:
        A complex ``(n_chirps, n_samples)`` array indexed as
        ``[doppler_bin, range_bin]``. The Doppler axis is shifted so the zero
        velocity bin is at the centre; the range axis is not shifted (bin 0 is
        zero range).
    """
    cube = np.asarray(cube, dtype=np.complex128)
    if cube.ndim != 2:
        raise ValueError("cube must be a 2D (n_chirps, n_samples) array")

    n_chirps, n_samples = cube.shape
    win_range = _window(window, n_samples)[None, :]
    win_doppler = _window(window, n_chirps)[:, None]
    windowed = cube * win_range * win_doppler

    # Range FFT along fast time (samples), then Doppler FFT along slow time
    # (chirps); centre zero Doppler.
    range_spectrum = np.fft.fft(windowed, axis=1)
    rdm = np.fft.fftshift(np.fft.fft(range_spectrum, axis=0), axes=0)
    return rdm


def range_axis(config: RadarConfig) -> np.ndarray:
    """Range value in metres for each range bin."""
    return np.arange(config.n_samples) * config.range_resolution


def range_doppler_axes(config: RadarConfig) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(range_axis, velocity_axis)`` for an RDM of this config."""
    return range_axis(config), velocity_axis(config)


def magnitude_db(rdm) -> np.ndarray:
    """Magnitude of the RDM in decibels, with a floor to avoid ``-inf``."""
    arr = np.abs(np.asarray(rdm, dtype=np.complex128))
    floor = 1e-12
    return 20.0 * np.log10(np.maximum(arr, floor))


def find_peak(rdm, config: RadarConfig) -> tuple[float, float, float]:
    """Locate the strongest cell of the RDM in physical units.

    Args:
        rdm: Complex Range-Doppler map ``[doppler_bin, range_bin]``.
        config: The radar configuration used to build the axes.

    Returns:
        ``(range_m, velocity_mps, magnitude)`` of the cell with the largest
        magnitude.
    """
    mag = np.abs(np.asarray(rdm))
    doppler_bin, range_bin = np.unravel_index(int(np.argmax(mag)), mag.shape)
    rng = range_axis(config)[range_bin]
    vel = velocity_axis(config)[doppler_bin]
    return float(rng), float(vel), float(mag[doppler_bin, range_bin])
