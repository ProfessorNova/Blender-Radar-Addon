"""Thermal noise and clutter model for the radar beat signal.

Blender-independent (milestone 4). Two effects degrade the otherwise clean
synthetic beat cube from :mod:`core.signal_model`:

* **Thermal noise** -- additive white circularly-symmetric complex Gaussian
  noise on every cube sample, the receiver noise floor.
* **Clutter** -- returns from many stationary scatterers (ground, walls,
  background). It is modelled as a set of extra *stationary* point targets at
  random ranges with random complex amplitudes, fed through the very same
  :func:`core.signal_model.synthesize_beat_cube` as the real targets. Because
  the scatterers are stationary they pile up in the zero-velocity (zero
  Doppler) column of the Range-Doppler map, exactly where real clutter sits.

All randomness goes through an explicit ``numpy.random.Generator`` so a given
seed reproduces the dataset bit-for-bit, which is the point of milestone 4.
"""

from __future__ import annotations

import numpy as np


def thermal_noise(shape, std, rng=None) -> np.ndarray:
    """Additive white complex Gaussian noise.

    The noise is circularly symmetric: the real and imaginary parts are
    independent zero-mean Gaussians each with standard deviation
    ``std / sqrt(2)``, so the expected noise power ``E[|n|^2]`` equals
    ``std**2``. ``std`` is therefore the RMS noise voltage in the same
    arbitrary units as the beat cube.

    Args:
        shape: Output shape (anything accepted by ``numpy``; an int gives a
            1D array).
        std: RMS noise voltage. A non-positive value yields all-zero noise.
        rng: Optional ``numpy.random.Generator``. A fresh default generator is
            used when omitted (non-reproducible).

    Returns:
        A complex ``numpy.ndarray`` of the requested shape.
    """
    if rng is None:
        rng = np.random.default_rng()
    std = float(std)
    if std <= 0.0:
        return np.zeros(shape, dtype=np.complex128)
    sigma = std / np.sqrt(2.0)
    real = rng.normal(0.0, sigma, size=shape)
    imag = rng.normal(0.0, sigma, size=shape)
    return (real + 1j * imag).astype(np.complex128)


def clutter_targets(
    n,
    max_range: float,
    amplitude_std: float,
    rng=None,
    min_range: float = 0.0,
    falloff_exp: float = 0.0,
):
    """Generate stationary clutter scatterers as point targets.

    The returned arrays plug straight into
    :func:`core.signal_model.synthesize_beat_cube`. Ranges are uniform in
    ``[min_range, max_range]``, velocities are all zero (stationary) and the
    complex amplitudes are circularly-symmetric Gaussian with RMS
    ``amplitude_std`` (so the clutter strength is set in the same voltage units
    as a unit-RCS target at the reference range).

    With ``falloff_exp > 0`` the amplitude is weighted by ``1 / R**falloff_exp``
    (clamped near zero range) and the weights are normalised to unit mean, so
    the *shape* of the clutter ridge fades from bright near to dim far while its
    overall level stays controlled by ``amplitude_std``.

    Args:
        n: Number of clutter scatterers.
        max_range: Upper bound of the random clutter ranges in metres.
        amplitude_std: RMS magnitude of the clutter amplitudes.
        rng: Optional ``numpy.random.Generator`` for reproducibility.
        min_range: Lower bound of the random clutter ranges in metres.
        falloff_exp: Range falloff exponent (0 = uniform).

    Returns:
        ``(ranges, velocities, amplitudes)`` arrays of length ``n``;
        ``velocities`` is all zeros and ``amplitudes`` is complex. All three
        are empty when ``n <= 0``.
    """
    if rng is None:
        rng = np.random.default_rng()
    n = int(n)
    if n <= 0:
        empty = np.zeros(0, dtype=np.float64)
        return empty, empty.copy(), np.zeros(0, dtype=np.complex128)

    ranges = rng.uniform(float(min_range), float(max_range), size=n)
    velocities = np.zeros(n, dtype=np.float64)
    amplitudes = thermal_noise(n, amplitude_std, rng)

    if falloff_exp:
        weight = np.maximum(ranges, 1.0) ** (-float(falloff_exp))
        weight /= weight.mean()
        amplitudes = amplitudes * weight

    return ranges, velocities, amplitudes
