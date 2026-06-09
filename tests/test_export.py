"""Tests for the CARRADA-style dataset export.

Runs without Blender. Execute with: python -m pytest tests/
"""

import numpy as np

from core.export import (
    RD_SUBDIR,
    config_to_dict,
    frame_npy_name,
    processed_rd_map,
    rd_map_path,
    save_rd_map,
    write_metadata,
)
from core.signal_model import RadarConfig


def _config():
    return RadarConfig(
        carrier_freq=77e9,
        bandwidth=767.5e6,
        sample_rate=10e6,
        n_samples=256,
        n_chirps=64,
        chirp_period=72.5e-6,
    )


# --- processed_rd_map -------------------------------------------------------


def test_processed_rd_map_shape_is_range_doppler():
    # Input is [doppler, range] = (64, 256); output must be (range, doppler).
    rdm = np.ones((64, 256), dtype=np.complex128)
    out = processed_rd_map(rdm)
    assert out.shape == (256, 64)
    assert out.dtype == np.float64


def test_processed_rd_map_offset_and_value():
    rdm = np.full((2, 3), 10.0, dtype=np.complex128)  # |rdm| = 10
    base = processed_rd_map(rdm, db_offset=0.0)
    shifted = processed_rd_map(rdm, db_offset=47.0)
    # 20*log10(10) = 20 dB.
    assert np.allclose(base, 20.0)
    assert np.allclose(shifted, 20.0 + 47.0)


def test_processed_rd_map_transpose_and_doppler_flip():
    rdm = np.zeros((64, 256), dtype=np.complex128)
    rdm[5, 9] = 1000.0  # doppler bin 5, range bin 9
    out = processed_rd_map(rdm)
    # Transposed to [range, doppler] and the Doppler axis flipped for CARRADA:
    # doppler bin 5 of 64 -> column 64 - 1 - 5 = 58.
    assert np.unravel_index(np.argmax(out), out.shape) == (9, 58)


# --- file layout ------------------------------------------------------------


def test_frame_npy_name_zero_padded():
    assert frame_npy_name(0) == "000000.npy"
    assert frame_npy_name(42) == "000042.npy"


def test_rd_map_path_uses_subdir():
    p = rd_map_path("/data/run", 7)
    assert RD_SUBDIR in p
    assert p.endswith("000007.npy")


def test_save_rd_map_round_trip(tmp_path):
    processed = np.arange(256 * 64, dtype=np.float64).reshape(256, 64)
    path = save_rd_map(str(tmp_path), 3, processed)
    assert path.endswith("000003.npy")
    loaded = np.load(path)
    assert np.array_equal(loaded, processed)


def test_write_metadata_round_trip(tmp_path):
    import json

    meta = {"format": "carrada-like", "rd_shape": [256, 64], "db_offset": 47.0}
    path = write_metadata(str(tmp_path), meta)
    with open(path, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded["format"] == "carrada-like"
    assert loaded["rd_shape"] == [256, 64]


# --- config_to_dict ---------------------------------------------------------


def test_config_to_dict_has_derived_and_base_keys():
    d = config_to_dict(_config())
    assert d["carrier_freq_hz"] == 77e9
    assert d["n_samples"] == 256
    assert "range_resolution_m" in d
    assert "max_velocity_mps" in d
