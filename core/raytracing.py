"""Blender-independent raytracing geometry for the radar simulation.

This module must not import ``bpy``. It owns the geometric raw-data
extraction for milestone 1:

* generating a fan of ray directions over a field of view,
* turning ray hits into scatter points with range and radial velocity,
* the rigid-body velocity math used to obtain radial velocity from the
  positional difference of a surface point across frames.

The actual ``scene.ray_cast`` call and frame stepping are Blender specific
and therefore injected from :mod:`utils.scene_access`. The ray caster is
passed in as a plain callable and the per-object motion is passed in as
plain 4x4 transforms, which keeps everything here testable without Blender.

Conventions
-----------
* All vectors are ``numpy.float64`` arrays in world space unless noted.
* The radar boresight is ``RadarPose.forward``. Azimuth rotates toward
  ``RadarPose.right`` (positive to the right), elevation toward
  ``RadarPose.up`` (positive upward). Angles are in radians.
* Radial velocity is the time derivative of range: positive means the
  target is receding (range increasing), negative means approaching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional

import numpy as np


def _unit(vec: np.ndarray) -> np.ndarray:
    """Return ``vec`` normalised to unit length.

    A zero vector is returned unchanged to avoid division by zero.
    """
    arr = np.asarray(vec, dtype=np.float64)
    norm = np.linalg.norm(arr)
    if norm == 0.0:
        return arr
    return arr / norm


@dataclass(frozen=True)
class RadarPose:
    """Position and orientation of the radar in world space.

    The three basis vectors are stored explicitly so the core never needs
    to know how Blender lays out a transform matrix.
    """

    origin: np.ndarray
    forward: np.ndarray
    right: np.ndarray
    up: np.ndarray

    def __post_init__(self) -> None:
        # Normalise defensively; callers may pass a raw matrix column.
        object.__setattr__(self, "origin", np.asarray(self.origin, dtype=np.float64))
        object.__setattr__(self, "forward", _unit(self.forward))
        object.__setattr__(self, "right", _unit(self.right))
        object.__setattr__(self, "up", _unit(self.up))


@dataclass(frozen=True)
class RayHit:
    """Result of a single ray cast against the scene.

    ``location`` and ``normal`` are world-space vectors. ``object_name`` is
    used to look up the object's motion for the velocity computation.
    ``reflectivity`` is a ``[0, 1]`` surface reflectivity (the material's
    metallic value in Blender) used to scale the radar cross section.
    """

    location: np.ndarray
    normal: np.ndarray
    object_name: str
    reflectivity: float = 0.0


# A ray caster takes a world-space origin and direction and returns the hit
# or ``None`` when the ray misses. Injected by the Blender layer.
RayCaster = Callable[[np.ndarray, np.ndarray], Optional[RayHit]]


@dataclass(frozen=True)
class ObjectMotion:
    """Rigid transforms of one object at the previous, current and next frame.

    Each entry is a 4x4 homogeneous transform (object-to-world). ``previous``
    and ``next_`` may be ``None`` when the object only exists at the current
    frame, in which case its velocity is treated as zero.
    """

    current: np.ndarray
    previous: Optional[np.ndarray] = None
    next_: Optional[np.ndarray] = None


@dataclass
class ScatterPoint:
    """A single radar scatter point extracted from the scene."""

    position: np.ndarray
    range: float
    radial_velocity: float
    azimuth: float
    elevation: float
    object_name: str
    normal: np.ndarray = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    # Surface reflectivity in [0, 1] (material metallic), scales the RCS.
    reflectivity: float = 0.0


def fan_directions(
    pose: RadarPose,
    fov_az: float,
    fov_el: float,
    n_az: int,
    n_el: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a grid of world-space ray directions over the field of view.

    Directions are laid out on a spherical grid so the returned azimuth and
    elevation are true angles relative to the boresight.

    Args:
        pose: Radar position and orientation.
        fov_az: Total horizontal field of view in radians.
        fov_el: Total vertical field of view in radians.
        n_az: Number of rays across azimuth (>= 1).
        n_el: Number of rays across elevation (>= 1).

    Returns:
        A tuple ``(directions, azimuth, elevation)`` where ``directions`` is
        an ``(n_az * n_el, 3)`` array of unit vectors in world space and
        ``azimuth`` / ``elevation`` are the matching ``(n_az * n_el,)`` angle
        arrays in radians.
    """
    if n_az < 1 or n_el < 1:
        raise ValueError("n_az and n_el must be at least 1")

    az = _angle_samples(fov_az, n_az)
    el = _angle_samples(fov_el, n_el)

    # Elevation varies slowest so rows of constant elevation are contiguous.
    el_grid, az_grid = np.meshgrid(el, az, indexing="ij")
    az_flat = az_grid.reshape(-1)
    el_flat = el_grid.reshape(-1)

    cos_el = np.cos(el_flat)
    # direction = cos(el)*cos(az)*F + cos(el)*sin(az)*R + sin(el)*U
    directions = (
        (cos_el * np.cos(az_flat))[:, None] * pose.forward
        + (cos_el * np.sin(az_flat))[:, None] * pose.right
        + np.sin(el_flat)[:, None] * pose.up
    )
    # Already unit length by construction, but normalise against float error.
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    return directions, az_flat, el_flat


def _angle_samples(fov: float, n: int) -> np.ndarray:
    """Return ``n`` angle samples spanning ``[-fov/2, fov/2]``.

    A single sample is placed on the boresight (angle zero) rather than at an
    edge of the field of view.
    """
    if n == 1:
        return np.zeros(1, dtype=np.float64)
    return np.linspace(-fov / 2.0, fov / 2.0, n, dtype=np.float64)


def line_of_sight(origin: np.ndarray, point: np.ndarray) -> tuple[np.ndarray, float]:
    """Return the unit line-of-sight vector from ``origin`` to ``point`` and range.

    The unit vector points from the radar toward the target, so projecting a
    target velocity onto it yields the rate of change of range.
    """
    delta = np.asarray(point, dtype=np.float64) - np.asarray(origin, dtype=np.float64)
    rng = float(np.linalg.norm(delta))
    if rng == 0.0:
        return np.zeros(3, dtype=np.float64), 0.0
    return delta / rng, rng


def radial_velocity(
    los_unit: np.ndarray,
    target_velocity: np.ndarray,
    radar_velocity: Optional[np.ndarray] = None,
) -> float:
    """Project a relative velocity onto the line of sight.

    Args:
        los_unit: Unit vector from the radar toward the target.
        target_velocity: World velocity of the scattering point.
        radar_velocity: World velocity of the radar (defaults to zero).

    Returns:
        The radial velocity in world units per second. Positive means the
        range is increasing (target receding).
    """
    target_velocity = np.asarray(target_velocity, dtype=np.float64)
    if radar_velocity is None:
        relative = target_velocity
    else:
        relative = target_velocity - np.asarray(radar_velocity, dtype=np.float64)
    return float(np.dot(relative, los_unit))


def rigid_point_velocity(
    motion: ObjectMotion,
    world_point: np.ndarray,
    dt_seconds: float,
) -> np.ndarray:
    """Velocity of a fixed surface point under a rigid object transform.

    The world point is mapped into the object's local frame using the current
    transform, then re-projected through the previous and next transforms.
    The difference of those world positions gives the velocity. This assumes
    rigid motion (the object transform), which is exact for translating and
    rotating objects and a reasonable approximation for milestone 1; mesh
    deformation (armatures, shape keys) is not captured.

    Args:
        motion: Object transforms at the previous, current and next frame.
        world_point: The hit location in world space at the current frame.
        dt_seconds: Time between adjacent frames in seconds.

    Returns:
        A world-space velocity vector. Zero when no adjacent frame is
        available or ``dt_seconds`` is non-positive.
    """
    if dt_seconds <= 0.0:
        return np.zeros(3, dtype=np.float64)

    point_h = np.append(np.asarray(world_point, dtype=np.float64), 1.0)
    local = np.linalg.inv(motion.current) @ point_h

    has_prev = motion.previous is not None
    has_next = motion.next_ is not None

    if has_prev and has_next:
        p_prev = (motion.previous @ local)[:3]
        p_next = (motion.next_ @ local)[:3]
        return (p_next - p_prev) / (2.0 * dt_seconds)
    if has_next:
        p_cur = (motion.current @ local)[:3]
        p_next = (motion.next_ @ local)[:3]
        return (p_next - p_cur) / dt_seconds
    if has_prev:
        p_prev = (motion.previous @ local)[:3]
        p_cur = (motion.current @ local)[:3]
        return (p_cur - p_prev) / dt_seconds
    return np.zeros(3, dtype=np.float64)


def extract_scatter_points(
    pose: RadarPose,
    ray_cast: RayCaster,
    object_motion: Mapping[str, ObjectMotion],
    *,
    fov_az: float,
    fov_el: float,
    n_az: int,
    n_el: int,
    dt_seconds: float,
    radar_velocity: Optional[np.ndarray] = None,
    max_range: Optional[float] = None,
) -> list[ScatterPoint]:
    """Extract scatter points for the current frame.

    Casts a fan of rays from the radar, and for every hit computes the range,
    the surface point's radial velocity (from its rigid motion across frames)
    and the ray's azimuth and elevation.

    Args:
        pose: Radar position and orientation in world space.
        ray_cast: Callable returning a :class:`RayHit` or ``None`` for a
            world-space ``(origin, direction)`` pair.
        object_motion: Maps object name to its :class:`ObjectMotion`. Objects
            absent from the map are treated as static (zero velocity).
        fov_az: Horizontal field of view in radians.
        fov_el: Vertical field of view in radians.
        n_az: Number of rays across azimuth.
        n_el: Number of rays across elevation.
        dt_seconds: Time between adjacent frames in seconds.
        radar_velocity: World velocity of the radar (defaults to zero).
        max_range: Discard hits beyond this range (no limit when ``None``).

    Returns:
        A list of :class:`ScatterPoint`, one per ray that hit geometry within
        ``max_range``.
    """
    directions, az_angles, el_angles = fan_directions(
        pose, fov_az, fov_el, n_az, n_el
    )

    points: list[ScatterPoint] = []
    for direction, az, el in zip(directions, az_angles, el_angles):
        hit = ray_cast(pose.origin, direction)
        if hit is None:
            continue

        los, rng = line_of_sight(pose.origin, hit.location)
        if max_range is not None and rng > max_range:
            continue

        motion = object_motion.get(hit.object_name)
        if motion is None:
            v_target = np.zeros(3, dtype=np.float64)
        else:
            v_target = rigid_point_velocity(motion, hit.location, dt_seconds)

        v_r = radial_velocity(los, v_target, radar_velocity)

        points.append(
            ScatterPoint(
                position=np.asarray(hit.location, dtype=np.float64),
                range=rng,
                radial_velocity=v_r,
                azimuth=float(az),
                elevation=float(el),
                object_name=hit.object_name,
                normal=np.asarray(hit.normal, dtype=np.float64),
                reflectivity=float(hit.reflectivity),
            )
        )
    return points
