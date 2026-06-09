"""Bridge from the scene to a Range-Doppler map and a Blender image.

Milestone 2. Builds a :class:`core.signal_model.RadarConfig` from the scene
settings, turns the extracted scatter points into point targets, synthesizes
the beat data cube, runs the 2D FFT and writes the resulting Range-Doppler map
(RDM) into a Blender image data-block.

This module imports ``bpy`` and is therefore not part of the testable core.
The numerical work all lives in :mod:`core.signal_model`,
:mod:`core.range_doppler` and :mod:`core.doppler`.
"""

from __future__ import annotations

from dataclasses import dataclass

import bpy
import numpy as np

from ..core.colormap import apply_colormap
from ..core.noise import clutter_targets, thermal_noise
from ..core.range_doppler import find_peak, magnitude_db, range_doppler_map
from ..core.signal_model import (
    RadarConfig,
    radar_equation_amplitude,
    reflectivity_to_rcs,
    synthesize_beat_cube,
)
from .preview import update_rdm_preview
from .scene_access import extract_scene_scatter_points

# Name of the image data-block the RDM is written to.
RDM_IMAGE_NAME = "RadarRDM"

# Default displayed dynamic range below the peak, in dB. Cells weaker than this
# are clamped to black. Overridden per scene by ``rdm_dynamic_range_db``.
RDM_DYNAMIC_RANGE_DB = 90.0


def build_radar_config(settings) -> RadarConfig:
    """Build an SI :class:`RadarConfig` from the scene's radar settings.

    Raises:
        ValueError: If the parameters are physically inconsistent (e.g. the
            chirp period is shorter than the active chirp duration).
    """
    return RadarConfig(
        carrier_freq=settings.carrier_freq_ghz * 1e9,
        bandwidth=settings.bandwidth_mhz * 1e6,
        sample_rate=settings.sample_rate_msps * 1e6,
        n_samples=settings.n_samples,
        n_chirps=settings.n_chirps,
        chirp_period=settings.chirp_period_us * 1e-6,
    )


@dataclass
class RDMResult:
    """Outcome of a scene RDM computation."""

    magnitude_db: np.ndarray  # (n_chirps, n_samples), Doppler x range
    n_points: int
    peak_range: float
    peak_velocity: float
    image: object  # bpy.types.Image
    cube: np.ndarray  # complex (n_chirps, n_samples) beat cube (with noise)
    rdm: np.ndarray  # complex (n_chirps, n_samples) Range-Doppler map
    points: list  # core.raytracing.ScatterPoint, the ground-truth returns
    config: RadarConfig  # the waveform config used (for export metadata)


def _targets_from_points(points, radar_origin: np.ndarray):
    """Turn scatter points into (ranges, velocities, complex amplitudes).

    The amplitude follows the radar equation (voltage ~ 1/R**2) modulated by
    the cosine of the local incidence angle as a simple radar-cross-section
    proxy (surfaces facing the radar reflect more strongly than grazing ones)
    and by the surface reflectivity from the material's metallic value, so a
    metallic object outshines a dielectric one.
    """
    ranges = np.array([p.range for p in points], dtype=np.float64)
    velocities = np.array([p.radial_velocity for p in points], dtype=np.float64)

    positions = np.array([p.position for p in points], dtype=np.float64)
    normals = np.array([p.normal for p in points], dtype=np.float64)
    reflectivity = np.array([p.reflectivity for p in points], dtype=np.float64)

    los = positions - radar_origin
    los_norm = np.linalg.norm(los, axis=1, keepdims=True)
    los_unit = np.divide(los, los_norm, out=np.zeros_like(los), where=los_norm > 0)

    normal_norm = np.linalg.norm(normals, axis=1, keepdims=True)
    normal_unit = np.divide(
        normals, normal_norm, out=np.zeros_like(normals), where=normal_norm > 0
    )

    # Incidence factor in [floor, 1]; a small floor keeps grazing hits visible.
    incidence = np.abs(np.sum(normal_unit * los_unit, axis=1))
    rcs = np.maximum(incidence, 0.05) * reflectivity_to_rcs(reflectivity)

    amplitudes = radar_equation_amplitude(ranges, rcs=rcs).astype(np.complex128)
    return ranges, velocities, amplitudes


# Colormap applied to the normalised magnitude map for display.
RDM_COLORMAP = "plasma"


def _normalized_to_rgba(normalized: np.ndarray) -> np.ndarray:
    """Map a (height, width) array in [0, 1] to a coloured RGBA buffer.

    The magnitude is run through the perceptual ``RDM_COLORMAP`` (plasma) so
    weak-to-strong returns read as dark-blue-to-yellow instead of grayscale.
    """
    rgb = apply_colormap(normalized, RDM_COLORMAP)
    height, width = normalized.shape
    rgba = np.empty((height, width, 4), dtype=np.float32)
    rgba[..., :3] = rgb
    rgba[..., 3] = 1.0
    return rgba


def _write_rdm_image(name: str, rgba: np.ndarray):
    """Write an RGBA buffer of shape (height, width, 4) to a Blender image.

    Blender stores pixels bottom-row first, which matches our display
    convention: the vertical axis is range (row 0 at the bottom is zero range,
    the top row is maximum range) and the horizontal axis is velocity (column 0
    on the left is the most negative / approaching, the right is the most
    positive / receding).
    """
    height, width = rgba.shape[:2]

    image = bpy.data.images.get(name)
    if image is not None and tuple(image.size) != (width, height):
        bpy.data.images.remove(image)
        image = None
    if image is None:
        image = bpy.data.images.new(
            name, width=width, height=height, float_buffer=True
        )

    image.pixels.foreach_set(rgba.ravel())
    image.update()
    return image


def _normalize_db(
    mag_db: np.ndarray, dynamic_range_db: float = RDM_DYNAMIC_RANGE_DB
) -> np.ndarray:
    """Map a dB magnitude map to [0, 1] over ``dynamic_range_db`` below peak."""
    dynamic_range_db = max(float(dynamic_range_db), 1e-6)
    peak = float(mag_db.max())
    floor = peak - dynamic_range_db
    normalized = (mag_db - floor) / dynamic_range_db
    return np.clip(normalized, 0.0, 1.0)


def _apply_noise(cube, config, settings, frame: int):
    """Add clutter and thermal noise to the beat cube if enabled.

    The random generator is seeded from ``(noise_seed, frame)`` so a frame is
    reproducible from the seed while different frames get independent noise.
    Clutter is drawn first, then thermal noise, so the consumption order (and
    thus the result) is fixed for a given seed.
    """
    if not (settings.noise_enabled or settings.clutter_enabled):
        return cube

    rng = np.random.default_rng([settings.noise_seed, int(frame)])
    cube = cube.copy()

    if settings.clutter_enabled and settings.clutter_count > 0:
        c_ranges, c_vel, c_amp = clutter_targets(
            settings.clutter_count,
            max_range=config.max_range,
            amplitude_std=settings.clutter_std,
            rng=rng,
            falloff_exp=settings.clutter_falloff,
        )
        cube += synthesize_beat_cube(config, c_ranges, c_vel, c_amp)

    if settings.noise_enabled:
        cube += thermal_noise(cube.shape, settings.noise_std, rng)

    return cube


def compute_scene_rdm(context, settings) -> RDMResult:
    """Compute the Range-Doppler map for the current scene and frame.

    Args:
        context: The Blender context.
        settings: The scene's ``radar_settings``.

    Returns:
        An :class:`RDMResult`. ``n_points`` is zero when no ray hit geometry,
        in which case the image still exists but is empty (all targets absent).

    Raises:
        ValueError: If the waveform parameters are inconsistent.
    """
    radar_obj = settings.radar_object
    config = build_radar_config(settings)

    points = extract_scene_scatter_points(
        context,
        radar_obj,
        fov_az=settings.fov_azimuth,
        fov_el=settings.fov_elevation,
        n_az=settings.rays_azimuth,
        n_el=settings.rays_elevation,
        dt_frames=settings.velocity_dframes,
        max_range=settings.max_range,
    )

    if points:
        radar_origin = np.array(
            radar_obj.matrix_world.translation, dtype=np.float64
        )
        ranges, velocities, amplitudes = _targets_from_points(
            points, radar_origin
        )
        cube = synthesize_beat_cube(config, ranges, velocities, amplitudes)
    else:
        cube = np.zeros((config.n_chirps, config.n_samples), dtype=np.complex128)

    cube = _apply_noise(cube, config, settings, context.scene.frame_current)

    rdm = range_doppler_map(cube, window=settings.rdm_window)
    mag_db = magnitude_db(rdm)
    peak_range, peak_velocity, _ = find_peak(rdm, config)

    # mag_db is indexed [doppler, range]; transpose to display range on the
    # vertical axis and velocity (Doppler) on the horizontal axis, then flip the
    # Doppler axis to the CARRADA convention (approaching target to the right).
    display = _normalize_db(mag_db, settings.rdm_dynamic_range_db).T[:, ::-1]
    rgba = _normalized_to_rgba(np.ascontiguousarray(display))
    height, width = rgba.shape[:2]
    image = _write_rdm_image(RDM_IMAGE_NAME, rgba)
    # Mirror the same pixels into the N-panel preview.
    update_rdm_preview(rgba.ravel(), width, height)

    return RDMResult(
        magnitude_db=mag_db,
        n_points=len(points),
        peak_range=peak_range,
        peak_velocity=peak_velocity,
        image=image,
        cube=cube,
        rdm=rdm,
        points=points,
        config=config,
    )


def show_image_in_editor(image) -> bool:
    """Display ``image`` in an open Image Editor area, if any exists.

    Returns ``True`` if an editor was found and updated.
    """
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "IMAGE_EDITOR":
                area.spaces.active.image = image
                return True
    return False
