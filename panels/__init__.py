"""Radar UI panels.

Milestone 0 provides a single panel in the 3D viewport N-panel under a
"Radar" tab. It shows the placeholder property and the compute button.
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

        col = layout.column(align=True)
        col.prop(settings, "max_range")

        layout.separator()
        layout.operator("radar.compute_rdm", icon="PLAY")


_classes = (RADAR_PT_main,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
