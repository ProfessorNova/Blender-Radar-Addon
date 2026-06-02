"""Radar operators.

Milestone 0 ships a single no-op operator so the panel button does something
visible and the register path is exercised. The real compute operators
(raytracing, RDM generation) arrive in milestones 1 and 2.
"""

import bpy
from bpy.types import Operator


class RADAR_OT_compute_rdm(Operator):
    """Placeholder operator for the Range-Doppler computation."""

    bl_idname = "radar.compute_rdm"
    bl_label = "Compute Range-Doppler Map"
    bl_description = "Placeholder. Real computation is added in milestone 2"
    bl_options = {"REGISTER"}

    def execute(self, context):
        settings = context.scene.radar_settings
        # Report so the user sees the wiring works end to end.
        self.report(
            {"INFO"},
            "Radar add-on active. Max range set to "
            f"{settings.max_range:.1f} m. Compute not yet implemented.",
        )
        return {"FINISHED"}


_classes = (RADAR_OT_compute_rdm,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
