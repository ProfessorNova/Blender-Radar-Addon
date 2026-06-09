"""FMCW signal model and beat-signal synthesis.

Blender-independent. This module owns the radar waveform description and the
synthesis of the complex IF (beat) data cube for a set of point targets,
using the standard dechirped FMCW signal model and the radar range equation
for amplitudes.

Background
----------
An FMCW radar transmits a train of linear frequency chirps and mixes each
echo with the transmitted ramp. The result is a complex *beat* (IF) signal
whose

* frequency along fast time (samples within one chirp) is proportional to the
  target range, and
* phase progression along slow time (from chirp to chirp) is proportional to
  the target's radial velocity (Doppler).

For a single target at range ``R`` with radial velocity ``v`` the model used
here is, for fast-time sample ``n`` and chirp index ``m``::

    s[m, n] = a * exp(j * 2*pi * (f_b * t_n + f_d * m*T_c)) * exp(j * phi0)

with::

    t_n  = n / sample_rate                (fast-time within a chirp)
    f_b  = 2 * slope * R / c              (range beat frequency)
    f_d  = 2 * v / wavelength             (Doppler frequency)
    phi0 = 4*pi * R / wavelength          (absolute range phase)

The constant ``phi0`` does not affect the magnitude of a single target in the
Range-Doppler map but gives each scatterer its own phase, which is physically
correct.

Sign convention (matches :mod:`core.raytracing`): a *positive* radial velocity
means the target is *receding* (range increasing) and lands at a *positive*
Doppler / velocity bin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Speed of light in vacuum, m/s.
SPEED_OF_LIGHT = 299_792_458.0


@dataclass(frozen=True)
class RadarConfig:
    """FMCW radar waveform configuration.

    All values are SI units (Hz, s). The fast-time / slow-time grid is
    ``(n_chirps, n_samples)``: ``n_samples`` samples are taken during each
    chirp's active ramp and ``n_chirps`` chirps make up one coherent frame.

    Attributes:
        carrier_freq: Carrier (centre) frequency in Hz.
        bandwidth: Swept bandwidth in Hz.
        sample_rate: Fast-time ADC sample rate in Hz.
        n_samples: Samples per chirp (number of range bins).
        n_chirps: Chirps per frame (number of Doppler bins).
        chirp_period: Slow-time spacing between consecutive chirps in s
            (the chirp repetition interval). Must be at least the active
            chirp duration ``n_samples / sample_rate``.
    """

    carrier_freq: float
    bandwidth: float
    sample_rate: float
    n_samples: int
    n_chirps: int
    chirp_period: float

    def __post_init__(self) -> None:
        if self.carrier_freq <= 0.0:
            raise ValueError("carrier_freq must be positive")
        if self.bandwidth <= 0.0:
            raise ValueError("bandwidth must be positive")
        if self.sample_rate <= 0.0:
            raise ValueError("sample_rate must be positive")
        if self.n_samples < 1 or self.n_chirps < 1:
            raise ValueError("n_samples and n_chirps must be at least 1")
        if self.chirp_period < self.chirp_duration - 1e-12:
            raise ValueError(
                "chirp_period must be at least the active chirp duration "
                f"({self.chirp_duration:.3e} s)"
            )

    @property
    def chirp_duration(self) -> float:
        """Active ramp time of one chirp in seconds (``n_samples / sample_rate``)."""
        return self.n_samples / self.sample_rate

    @property
    def slope(self) -> float:
        """Chirp frequency slope in Hz/s (``bandwidth / chirp_duration``)."""
        return self.bandwidth / self.chirp_duration

    @property
    def wavelength(self) -> float:
        """Carrier wavelength in metres."""
        return SPEED_OF_LIGHT / self.carrier_freq

    @property
    def range_resolution(self) -> float:
        """Range resolution in metres (``c / (2 * bandwidth)``)."""
        return SPEED_OF_LIGHT / (2.0 * self.bandwidth)

    @property
    def max_range(self) -> float:
        """Unambiguous range span in metres.

        With complex (I/Q) sampling the ``n_samples`` range bins span the full
        beat-frequency band, so this equals ``n_samples * range_resolution``.
        """
        return self.n_samples * self.range_resolution

    @property
    def velocity_resolution(self) -> float:
        """Radial-velocity resolution in m/s."""
        return self.wavelength / (2.0 * self.n_chirps * self.chirp_period)

    @property
    def max_velocity(self) -> float:
        """Maximum unambiguous radial velocity (one-sided) in m/s.

        The unambiguous Doppler span is ``[-max_velocity, +max_velocity)``.
        """
        return self.wavelength / (4.0 * self.chirp_period)


def reflectivity_to_rcs(reflectivity, low: float = 1.0, high: float = 100.0):
    """Map a surface reflectivity in ``[0, 1]`` to a relative RCS factor.

    The reflectivity is the material's metallic value: metal reflects radar
    strongly, dielectrics (cloth, skin, plastic) weakly. The mapping is linear,
    ``0 -> low`` and ``1 -> high``, and the input is clamped to ``[0, 1]``.

    Args:
        reflectivity: Reflectivity value(s) in ``[0, 1]`` (array-like).
        low: RCS factor for a non-metallic surface.
        high: RCS factor for a fully metallic surface.

    Returns:
        ``numpy.ndarray`` of relative RCS factors.
    """
    r = np.clip(np.asarray(reflectivity, dtype=np.float64), 0.0, 1.0)
    return low + (high - low) * r


def radar_equation_amplitude(
    ranges,
    rcs=1.0,
    reference_range: float = 1.0,
):
    """Relative received voltage amplitude from the radar range equation.

    Received power falls off as ``1 / R**4``; the voltage amplitude therefore
    scales as ``sqrt(rcs) / R**2``. The result is normalised so that a
    unit-RCS target at ``reference_range`` has amplitude 1.

    Args:
        ranges: Target range(s) in metres (array-like).
        rcs: Radar cross section(s), same shape as ``ranges`` or a scalar.
        reference_range: Range at which a unit-RCS target has amplitude 1.

    Returns:
        ``numpy.ndarray`` of relative voltage amplitudes.
    """
    ranges = np.asarray(ranges, dtype=np.float64)
    rcs = np.asarray(rcs, dtype=np.float64)
    safe = np.maximum(ranges, 1e-6)
    return np.sqrt(rcs) * (reference_range**2) / (safe**2)


def synthesize_beat_cube(
    config: RadarConfig,
    ranges,
    velocities,
    amplitudes=None,
) -> np.ndarray:
    """Synthesize the complex beat (IF) data cube for a set of point targets.

    Each target contributes a separable fast-time / slow-time complex
    exponential (see the module docstring). Contributions are summed
    coherently.

    Args:
        config: The radar waveform configuration.
        ranges: Target ranges in metres, shape ``(T,)``.
        velocities: Radial velocities in m/s, shape ``(T,)`` (positive =
            receding).
        amplitudes: Optional complex amplitudes per target, shape ``(T,)``.
            Defaults to unit amplitude for every target.

    Returns:
        A complex ``(n_chirps, n_samples)`` array: the beat signal sampled
        over slow time (chirps) and fast time (samples).
    """
    ranges = np.asarray(ranges, dtype=np.float64).reshape(-1)
    velocities = np.asarray(velocities, dtype=np.float64).reshape(-1)
    if ranges.shape != velocities.shape:
        raise ValueError("ranges and velocities must have the same length")

    if amplitudes is None:
        amplitudes = np.ones(ranges.shape, dtype=np.complex128)
    else:
        amplitudes = np.asarray(amplitudes, dtype=np.complex128).reshape(-1)
        if amplitudes.shape != ranges.shape:
            raise ValueError("amplitudes must match the number of targets")

    n_samples = config.n_samples
    n_chirps = config.n_chirps

    fast_time = np.arange(n_samples) / config.sample_rate          # (N,)
    slow_time = np.arange(n_chirps) * config.chirp_period          # (M,)

    f_beat = 2.0 * config.slope * ranges / SPEED_OF_LIGHT          # (T,)
    f_doppler = 2.0 * velocities / config.wavelength              # (T,)
    phi0 = 4.0 * np.pi * ranges / config.wavelength               # (T,)

    cube = np.zeros((n_chirps, n_samples), dtype=np.complex128)
    two_pi = 2.0 * np.pi
    for amp, fb, fd, p0 in zip(amplitudes, f_beat, f_doppler, phi0):
        fast = np.exp(1j * two_pi * fb * fast_time)               # (N,)
        slow = np.exp(1j * (two_pi * fd * slow_time + p0))        # (M,)
        cube += amp * np.outer(slow, fast)
    return cube
