"""Viewport overlay: draws the radar detection volume as a wireframe cone.

Draws in the 3D viewport as long as a radar object is set in the scene
settings. The visualization shows:

* four corner rays from the radar origin to the corners of the far face,
* one centre boresight ray,
* the rectangular outline at max_range,
* a cross-hair on the far face,
* an "up" triangle on the top edge of the far face, mirroring Blender's
  camera triangle, so the radar's required up direction is obvious (and
  visibly rolls with the object) while posing it.

Uses the camera convention: local -Z is boresight, +Y is up, +X is right.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

_handles: list = []


def _fov_direction(az_rad: float, el_rad: float) -> Vector:
    return Vector((
        math.sin(az_rad) * math.cos(el_rad),
        math.sin(el_rad),
        -math.cos(az_rad) * math.cos(el_rad),
    ))


def _draw() -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader

    context = bpy.context
    if not hasattr(context, 'scene') or not hasattr(context.scene, 'radar_settings'):
        return

    settings = context.scene.radar_settings
    radar_obj = settings.radar_object
    if radar_obj is None:
        return

    max_range = settings.max_range
    half_az = settings.fov_azimuth * 0.5
    half_el = settings.fov_elevation * 0.5

    rot = radar_obj.matrix_world.to_3x3().normalized()
    origin = Vector(radar_obj.matrix_world.translation)
    right_axis = (rot @ Vector((1.0, 0.0, 0.0))).normalized()
    up_axis = (rot @ Vector((0.0, 1.0, 0.0))).normalized()

    def wp(az: float, el: float) -> Vector:
        return origin + rot @ _fov_direction(az, el) * max_range

    corners = [
        wp(+half_az, +half_el),
        wp(+half_az, -half_el),
        wp(-half_az, -half_el),
        wp(-half_az, +half_el),
    ]
    mids = [
        wp(0.0, +half_el),
        wp(+half_az, 0.0),
        wp(0.0, -half_el),
        wp(-half_az, 0.0),
    ]
    boresight = wp(0.0, 0.0)

    verts: list[tuple[float, float, float]] = []

    def line(a: Vector, b: Vector) -> None:
        verts.extend([tuple(a), tuple(b)])

    for c in corners:
        line(origin, c)

    line(origin, boresight)

    for i in range(4):
        line(corners[i], corners[(i + 1) % 4])

    line(mids[0], mids[2])
    line(mids[1], mids[3])

    # "Up" triangle: an isosceles triangle whose base sits on the top edge of
    # the far face (centred at the top mid-point) and whose apex points along
    # the radar's local up axis, like the triangle on a Blender camera. It is
    # sized relative to max_range so it scales with the cone.
    top_mid = mids[0]
    tri_size = max_range * 0.12
    base_half = tri_size * 0.6
    top_edge = corners[0] - corners[3]
    base_dir = top_edge.normalized() if top_edge.length > 0.0 else right_axis
    base_left = top_mid - base_dir * base_half
    base_right = top_mid + base_dir * base_half
    apex = top_mid + up_axis * tri_size
    line(base_left, base_right)
    line(base_right, apex)
    line(apex, base_left)

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": verts})

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(1.0)
    shader.bind()
    shader.uniform_float("color", (0.0, 1.0, 0.5, 0.75))
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def register() -> None:
    handle = bpy.types.SpaceView3D.draw_handler_add(
        _draw, (), 'WINDOW', 'POST_VIEW'
    )
    _handles.append(handle)


def unregister() -> None:
    while _handles:
        bpy.types.SpaceView3D.draw_handler_remove(_handles.pop(), 'WINDOW')
