"""Bridge between the Blender scene and the bpy-independent core.

This module is the only place in milestone 1 that imports ``bpy``. It:

* reads the radar object's transform into a :class:`~core.raytracing.RadarPose`,
* wraps ``scene.ray_cast`` into the plain callable the core expects,
* steps the timeline to sample object transforms at the previous, current and
  next frame so the core can compute radial velocity,
* ties the above together into :func:`extract_scene_scatter_points`.

The radar object follows the Blender camera convention: its local ``-Z`` axis
is the boresight (forward), local ``+Y`` is up and local ``+X`` is right. This
means a plain Camera or Empty works as a radar without extra setup.
"""

from __future__ import annotations

from typing import Optional

import bpy
import numpy as np

from ..core.raytracing import (
    ObjectMotion,
    RadarPose,
    RayHit,
    ScatterPoint,
    extract_scatter_points,
)


def matrix_to_numpy(matrix) -> np.ndarray:
    """Convert a ``mathutils.Matrix`` to a 4x4 ``numpy.float64`` array."""
    return np.array([list(row) for row in matrix], dtype=np.float64)


def get_radar_pose(radar_obj) -> RadarPose:
    """Build a :class:`RadarPose` from a Blender object's world transform.

    Uses the camera convention: forward is local ``-Z``, up is local ``+Y``,
    right is local ``+X``.
    """
    m = matrix_to_numpy(radar_obj.matrix_world)
    origin = m[:3, 3]
    right = m[:3, 0]
    up = m[:3, 1]
    forward = -m[:3, 2]
    return RadarPose(origin=origin, forward=forward, right=right, up=up)


def _material_metallic(mat) -> float:
    """Return a material's metallic value in ``[0, 1]``.

    Prefers the Principled BSDF ``Metallic`` input, falling back to the
    material's viewport ``metallic`` attribute. Returns 0.0 when neither is
    available (a non-metallic, weakly reflecting surface).
    """
    if mat is None:
        return 0.0
    node_tree = getattr(mat, "node_tree", None)
    if getattr(mat, "use_nodes", False) and node_tree is not None:
        for node in node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                inp = node.inputs.get("Metallic")
                if inp is not None:
                    return float(inp.default_value)
    return float(getattr(mat, "metallic", 0.0))


def _hit_metallic(obj, face_index: int, cache: dict) -> float:
    """Metallic value of the material on the hit face of ``obj``.

    Results are cached per material so the per-ray lookup stays cheap.
    """
    if obj is None or getattr(obj, "type", None) != "MESH" or not obj.material_slots:
        return 0.0
    try:
        slot_index = obj.data.polygons[face_index].material_index
        mat = obj.material_slots[slot_index].material
    except (IndexError, AttributeError):
        mat = obj.material_slots[0].material
    key = mat.name if mat is not None else None
    if key not in cache:
        cache[key] = _material_metallic(mat)
    return cache[key]


def make_ray_caster(scene, depsgraph, max_range: Optional[float] = None):
    """Return a callable wrapping ``scene.ray_cast`` for the core.

    The callable takes world-space origin and direction numpy arrays and
    returns a :class:`RayHit` or ``None``. The hit carries the material's
    metallic value as its reflectivity so the signal model can scale the RCS.
    """
    from mathutils import Vector

    distance = max_range if max_range is not None else 1.70141e38
    metallic_cache: dict = {}

    def ray_cast(origin: np.ndarray, direction: np.ndarray) -> Optional[RayHit]:
        result, location, normal, index, obj, _matrix = scene.ray_cast(
            depsgraph,
            Vector(origin.tolist()),
            Vector(direction.tolist()),
            distance=distance,
        )
        if not result:
            return None
        return RayHit(
            location=np.array(location, dtype=np.float64),
            normal=np.array(normal, dtype=np.float64),
            object_name=obj.name if obj is not None else "",
            reflectivity=_hit_metallic(obj, index, metallic_cache),
        )

    return ray_cast


def gather_object_motion(scene, frame: int, dt_frames: int) -> dict[str, ObjectMotion]:
    """Sample every object's world transform at frame-dt, frame and frame+dt.

    The timeline is stepped to each frame so animated and physics-driven
    transforms are evaluated correctly, then restored to ``frame``.

    Args:
        scene: The Blender scene.
        frame: The current frame to extract scatter points for.
        dt_frames: Frame offset used for the finite-difference velocity.

    Returns:
        A mapping of object name to :class:`ObjectMotion`.
    """
    original = scene.frame_current

    def matrices_at(f: int) -> dict[str, np.ndarray]:
        scene.frame_set(f)
        return {
            obj.name: matrix_to_numpy(obj.matrix_world) for obj in scene.objects
        }

    try:
        prev = matrices_at(frame - dt_frames)
        next_ = matrices_at(frame + dt_frames)
        current = matrices_at(frame)
    finally:
        scene.frame_set(original)

    motion: dict[str, ObjectMotion] = {}
    for name, cur in current.items():
        motion[name] = ObjectMotion(
            current=cur,
            previous=prev.get(name),
            next_=next_.get(name),
        )
    return motion


def scene_fps(scene) -> float:
    """Effective playback frames per second of the scene."""
    return scene.render.fps / scene.render.fps_base


def extract_scene_scatter_points(
    context,
    radar_obj,
    *,
    fov_az: float,
    fov_el: float,
    n_az: int,
    n_el: int,
    dt_frames: int = 1,
    max_range: Optional[float] = None,
) -> list[ScatterPoint]:
    """Extract scatter points for the radar object at the current frame.

    Args:
        context: The Blender context (provides scene and depsgraph).
        radar_obj: The object acting as the radar.
        fov_az: Horizontal field of view in radians.
        fov_el: Vertical field of view in radians.
        n_az: Number of rays across azimuth.
        n_el: Number of rays across elevation.
        dt_frames: Frame offset for the velocity finite difference.
        max_range: Discard hits beyond this range.

    Returns:
        A list of :class:`~core.raytracing.ScatterPoint`.
    """
    scene = context.scene
    frame = scene.frame_current

    object_motion = gather_object_motion(scene, frame, dt_frames)

    dt_seconds = dt_frames / scene_fps(scene)

    radar_motion = object_motion.get(radar_obj.name)
    if radar_motion is not None:
        from ..core.raytracing import rigid_point_velocity

        radar_origin = matrix_to_numpy(radar_obj.matrix_world)[:3, 3]
        radar_velocity = rigid_point_velocity(radar_motion, radar_origin, dt_seconds)
    else:
        radar_velocity = None

    # The depsgraph must reflect the current frame for ray casting.
    depsgraph = context.evaluated_depsgraph_get()
    pose = get_radar_pose(radar_obj)
    ray_cast = make_ray_caster(scene, depsgraph, max_range)

    return extract_scatter_points(
        pose,
        ray_cast,
        object_motion,
        fov_az=fov_az,
        fov_el=fov_el,
        n_az=n_az,
        n_el=n_el,
        dt_seconds=dt_seconds,
        radar_velocity=radar_velocity,
        max_range=max_range,
    )
