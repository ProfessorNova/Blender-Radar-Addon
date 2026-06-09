"""Bridge from computed scene RDMs to the CARRADA-style dataset on disk.

Milestone 4. Thin glue: turns an :class:`utils.rdm.RDMResult` into the
processed range-Doppler map and assembles the run metadata. The frame
iteration and progress feedback live in the modal export operator; the
numerical and file work lives in :mod:`core.export`.
"""

from __future__ import annotations

from ..core.export import (
    RD_SUBDIR,
    config_to_dict,
    processed_rd_map,
    save_rd_map,
    write_metadata,
)


def save_scene_rd_frame(export_dir: str, index: int, result, db_offset: float) -> str:
    """Write the processed RD map of ``result`` as one sequence frame."""
    processed = processed_rd_map(result.rdm, db_offset)
    return save_rd_map(export_dir, index, processed)


def build_dataset_metadata(settings, config, frame_map: dict) -> dict:
    """Assemble the dataset ``metadata.json`` content for an export run."""
    return {
        "format": "carrada-like",
        "maps": [RD_SUBDIR],
        "rd_shape": [config.n_samples, config.n_chirps],
        "rd_value": "20*log10(|rdm|) + db_offset",
        "db_offset": float(settings.export_db_offset),
        "config": config_to_dict(config),
        "noise": {
            "thermal_enabled": bool(settings.noise_enabled),
            "thermal_std": float(settings.noise_std),
            "clutter_enabled": bool(settings.clutter_enabled),
            "clutter_count": int(settings.clutter_count),
            "clutter_std": float(settings.clutter_std),
            "seed": int(settings.noise_seed),
        },
        "conventions": {
            "rd_axes": "[range, doppler]",
            "range_bin_0": "zero range",
            "doppler": (
                "centre = zero velocity; flipped to the CARRADA convention "
                "(approaching target to the right / higher doppler index)"
            ),
        },
        "frames": frame_map,
    }


def write_dataset_metadata(export_dir: str, settings, config, frame_map: dict) -> str:
    """Write ``metadata.json`` describing the exported sequence."""
    return write_metadata(
        export_dir, build_dataset_metadata(settings, config, frame_map)
    )
