"""Scene-level radar properties.

For milestone 0 this holds only a minimal placeholder property group so the
panel has something to display. Real radar parameters (carrier frequency,
bandwidth, PRF, chirp configuration) are added in milestone 3.
"""

import bpy
from bpy.props import FloatProperty, PointerProperty
from bpy.types import PropertyGroup


class RadarSettings(PropertyGroup):
    """Container for radar configuration stored on the scene."""

    # Placeholder parameter, replaced by the real parameter set in MS3.
    max_range: FloatProperty(
        name="Max Range",
        description="Maximum unambiguous range in meters",
        default=100.0,
        min=1.0,
        soft_max=1000.0,
        unit="LENGTH",
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
