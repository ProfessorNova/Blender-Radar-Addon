"""Viewport overlay: draws the radar detection volume as a wireframe cone.

Draws in the 3D viewport as long as a radar object is set in the scene
settings. The visualization shows:

* four corner rays from the radar origin to the corners of the far face,
* one centre boresight ray,
* the rectangular outline at max_range,
* a cross-hair on the far face.

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
