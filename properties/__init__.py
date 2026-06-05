"""Scene-level radar properties.

Milestone 1 adds the inputs needed for scene access and raytracing: the
radar object and the ray fan (field of view and ray counts). The full radar
parameter set (carrier frequency, bandwidth, PRF, chirp configuration) is
added in milestone 3.
"""

import math

import bpy
from bpy.props import (
    FloatProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


def _is_radar_candidate(self, obj):
    """Allow any object to act as the radar, excluding the radar's own data."""
    return obj.type in {"EMPTY", "CAMERA", "MESH"}


class RadarSettings(PropertyGroup):
    """Container for radar configuration stored on the scene."""

    radar_object: PointerProperty(
        name="Radar Object",
        description=(
            "Object acting as the radar. Its local -Z axis is the boresight "
            "(camera convention)"
        ),
        type=bpy.types.Object,
        poll=_is_radar_candidate,
    )

    # Placeholder parameter, replaced by the real parameter set in MS3.
    max_range: FloatProperty(
        name="Max Range",
        description="Maximum unambiguous range in meters",
        default=100.0,
        min=1.0,
        soft_max=1000.0,
        unit="LENGTH",
    )

    fov_azimuth: FloatProperty(
        name="FOV Azimuth",
        description="Horizontal field of view of the ray fan",
        default=math.radians(60.0),
        min=math.radians(1.0),
        max=math.radians(179.0),
        subtype="ANGLE",
        unit="ROTATION",
    )

    fov_elevation: FloatProperty(
        name="FOV Elevation",
        description="Vertical field of view of the ray fan",
        default=math.radians(30.0),
        min=math.radians(1.0),
        max=math.radians(179.0),
        subtype="ANGLE",
        unit="ROTATION",
    )

    rays_azimuth: IntProperty(
        name="Rays Azimuth",
        description="Number of rays across azimuth",
        default=64,
        min=1,
        soft_max=512,
    )

    rays_elevation: IntProperty(
        name="Rays Elevation",
        description="Number of rays across elevation",
        default=32,
        min=1,
        soft_max=512,
    )

    velocity_dframes: IntProperty(
        name="Velocity Frame Step",
        description=(
            "Frame offset used to estimate radial velocity from positional "
            "differences across frames"
        ),
        default=1,
        min=1,
        soft_max=10,
    )


_classes = (RadarSettings,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    # Attach settings to the scene so they persist with the .blend file.
    bpy.types.Scene.radar_settings = PointerProperty(type=RadarSettings)


def unregister():
    del bpy.types.Scene.radar_settings
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
