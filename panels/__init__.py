"""Radar UI panels.

The main panel lives in the 3D viewport N-panel under a "Radar" tab. From
milestone 1 it exposes the radar object and the ray fan settings and a button
to extract scatter points for the current frame.
"""

import bpy
from bpy.types import Panel


class RADAR_PT_main(Panel):
    """Main radar panel in the 3D viewport sidebar."""

    bl_label = "Radar RDM"
    bl_idname = "RADAR_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Radar"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.radar_settings

        col = layout.column()
        col.prop(settings, "radar_object")
        col.prop(settings, "max_range")

        box = layout.box()
        box.label(text="Ray Fan")
        box.prop(settings, "fov_azimuth")
        box.prop(settings, "fov_elevation")
        box.prop(settings, "rays_azimuth")
        box.prop(settings, "rays_elevation")
        box.prop(settings, "velocity_dframes")

        layout.separator()
        layout.operator("radar.extract_scatter_points", icon="TRACKER")
        layout.operator("radar.compute_rdm", icon="PLAY")


_classes = (RADAR_PT_main,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
