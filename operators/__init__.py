"""Radar operators.

Milestone 1 adds :class:`RADAR_OT_extract_scatter_points`, which casts a fan
of rays from the radar object and reports the resulting scatter points (range
and radial velocity) for the current frame. The Range-Doppler computation
operator remains a placeholder until milestone 2.
"""

import bpy
from bpy.types import Operator

from ..utils.scene_access import extract_scene_scatter_points


class RADAR_OT_extract_scatter_points(Operator):
    """Cast rays into the scene and extract scatter points for this frame."""

    bl_idname = "radar.extract_scatter_points"
    bl_label = "Extract Scatter Points"
    bl_description = (
        "Cast a fan of rays from the radar object and report the range and "
        "radial velocity of each hit for the current frame"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.scene.radar_settings.radar_object is not None

    def execute(self, context):
        settings = context.scene.radar_settings
        radar_obj = settings.radar_object
        if radar_obj is None:
            self.report({"ERROR"}, "No radar object selected")
            return {"CANCELLED"}

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

        if not points:
            self.report(
                {"WARNING"},
                "No scatter points: rays did not hit geometry within max range",
            )
            return {"FINISHED"}

        ranges = [p.range for p in points]
        velocities = [p.radial_velocity for p in points]
        self.report(
            {"INFO"},
            f"{len(points)} scatter points | "
            f"range {min(ranges):.2f}-{max(ranges):.2f} m | "
            f"radial vel {min(velocities):+.2f}..{max(velocities):+.2f} m/s",
        )

        # Print a short sample to the system console for inspection.
        print(f"[radar] frame {context.scene.frame_current}: {len(points)} points")
        for p in points[:5]:
            print(
                f"  {p.object_name:>16s}  r={p.range:7.2f} m  "
                f"v_r={p.radial_velocity:+7.2f} m/s  "
                f"az={p.azimuth:+.3f} el={p.elevation:+.3f} rad"
            )
        return {"FINISHED"}


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


_classes = (RADAR_OT_extract_scatter_points, RADAR_OT_compute_rdm)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
