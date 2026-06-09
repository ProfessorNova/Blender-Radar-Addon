"""CARRADA-style dataset export for the radar simulation.

Blender-independent. Writes the range-Doppler maps of a rendered sequence into
the folder layout of the CARRADA dataset, so the output is drop-in compatible
with tooling built for it:

    <export_dir>/
        range_doppler_processed/000000.npy   # (n_range, n_doppler) float64
        range_doppler_processed/000001.npy
        ...
        metadata.json

The stored map is the magnitude in dB (``20*log10|rdm|``) plus a calibration
offset, which lands it in the value range of the reference "processed" maps
(~45..105). Range-angle and angle-Doppler maps and the dense class annotations
follow once the antenna array (milestone 5) provides the angle axis.
"""

from __future__ import annotations

import json
import os

import numpy as np

from .signal_model import RadarConfig

# Sub-folder name for the processed range-Doppler maps (CARRADA naming).
RD_SUBDIR = "range_doppler_processed"


def processed_rd_map(rdm, db_offset: float = 0.0) -> np.ndarray:
    """Magnitude of the RDM in dB plus an offset, as ``(range, doppler)``.

    Args:
        rdm: Complex Range-Doppler map indexed ``[doppler_bin, range_bin]``.
        db_offset: Added to ``20*log10|rdm|`` to match the reference value
            range.

    Returns:
        A ``float64`` array of shape ``(n_range, n_doppler)`` (the reference
        orientation): the transpose of the input's ``[doppler, range]`` layout
        with the Doppler axis flipped to the CARRADA convention, where an
        approaching target sits to the right of the zero-velocity ridge (our
        FFT puts a receding target there, so the axis is reversed).
    """
    arr = np.abs(np.asarray(rdm, dtype=np.complex128))
    mag_db = 20.0 * np.log10(np.maximum(arr, 1e-12)) + float(db_offset)
    return np.ascontiguousarray(mag_db.T[:, ::-1])


def frame_npy_name(index: int) -> str:
    """Six-digit zero-padded ``.npy`` file name for a sequence index."""
    return f"{index:06d}.npy"


def rd_map_path(export_dir: str, index: int) -> str:
    """Full path of the range-Doppler ``.npy`` for a sequence index."""
    return os.path.join(export_dir, RD_SUBDIR, frame_npy_name(index))


def save_rd_map(export_dir: str, index: int, processed) -> str:
    """Write one processed RD map under ``<export_dir>/range_doppler_processed``.

    Creates the sub-folder if needed and returns the written path.
    """
    path = rd_map_path(export_dir, index)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, np.asarray(processed, dtype=np.float64))
    return path


def config_to_dict(config: RadarConfig) -> dict:
    """Flatten a :class:`RadarConfig` (plus its derived spans) to a JSON dict."""
    return {
        "carrier_freq_hz": config.carrier_freq,
        "bandwidth_hz": config.bandwidth,
        "sample_rate_hz": config.sample_rate,
        "n_samples": config.n_samples,
        "n_chirps": config.n_chirps,
        "chirp_period_s": config.chirp_period,
        "wavelength_m": config.wavelength,
        "range_resolution_m": config.range_resolution,
        "max_range_m": config.max_range,
        "velocity_resolution_mps": config.velocity_resolution,
        "max_velocity_mps": config.max_velocity,
    }


def write_metadata(export_dir: str, metadata: dict) -> str:
    """Write the dataset ``metadata.json`` at the export-dir root."""
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, "metadata.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)
    return path
