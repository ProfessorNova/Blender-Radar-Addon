"""Radar UI panels.

The main panel lives in the 3D viewport N-panel under a "Radar" tab. From
milestone 1 it exposes the radar object and the ray fan settings and a button
to extract scatter points for the current frame. Milestone 2 adds the FMCW
signal-model section, the derived resolutions and the Range-Doppler button.
Milestone 4 adds the noise/clutter section and the dataset export section.
"""

import bpy
from bpy.types import Panel

from ..utils.preview import rdm_icon_id
from ..utils.rdm import build_radar_config


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

        box = layout.box()
        box.label(text="Signal Model")
        box.prop(settings, "carrier_freq_ghz")
        box.prop(settings, "bandwidth_mhz")
        box.prop(settings, "sample_rate_msps")
        box.prop(settings, "n_samples")
        box.prop(settings, "n_chirps")
        box.prop(settings, "chirp_period_us")
        box.prop(settings, "rdm_window")
        box.prop(settings, "rdm_dynamic_range_db")

        self._draw_derived(box, settings)

        self._draw_noise(layout, settings)

        layout.separator()
        layout.operator("radar.extract_scatter_points", icon="TRACKER")
        layout.operator("radar.compute_rdm", icon="PLAY")

        self._draw_rdm_preview(layout, settings)
        self._draw_animation(layout, context, settings)
        self._draw_export(layout, settings)

    @staticmethod
    def _draw_noise(layout, settings):
        """Thermal-noise and clutter model (milestone 4)."""
        box = layout.box()
        box.label(text="Noise & Clutter")

        box.prop(settings, "noise_enabled")
        col = box.column(align=True)
        col.enabled = settings.noise_enabled
        col.prop(settings, "noise_std")

        box.prop(settings, "clutter_enabled")
        col = box.column(align=True)
        col.enabled = settings.clutter_enabled
        col.prop(settings, "clutter_count")
        col.prop(settings, "clutter_std")
        col.prop(settings, "clutter_falloff")

        box.prop(settings, "noise_seed")

    @staticmethod
    def _draw_export(layout, settings):
        """CARRADA-style range-Doppler dataset export (milestone 4)."""
        box = layout.box()
        box.label(text="Export")
        box.prop(settings, "export_dir")
        box.prop(settings, "export_db_offset")
        box.operator("radar.export_dataset", icon="EXPORT")

    @staticmethod
    def _draw_animation(layout, context, settings):
        """Animation rendering over the scene frame range."""
        scene = context.scene
        box = layout.box()
        box.label(text="Animation")
        box.prop(settings, "anim_output_dir")
        frame_count = (
            (scene.frame_end - scene.frame_start) // max(scene.frame_step, 1)
        ) + 1
        box.label(
            text=f"Frames {scene.frame_start}-{scene.frame_end} ({frame_count})"
        )
        box.operator("radar.render_animation", icon="RENDER_ANIMATION")

    @staticmethod
    def _draw_rdm_preview(layout, settings):
        """Show the last computed Range-Doppler map inside the panel."""
        icon = rdm_icon_id()
        if icon is None and settings.rdm_image is None:
            return

        box = layout.box()
        box.label(text="Range-Doppler Map")
        if icon is not None:
            row = box.row()
            row.alignment = "CENTER"
            row.template_icon(icon_value=icon, scale=12.0)
            box.label(text="y: range (up = far)")
            box.label(text="x: velocity (right = approaching)")

        # Native image data-block widget (browse / rename / unlink) plus a
        # button to open the map in a full Image Editor.
        box.template_ID(settings, "rdm_image")
        box.operator("radar.view_rdm", icon="IMAGE")

    @staticmethod
    def _draw_derived(layout, settings):
        """Show the resolutions and unambiguous spans derived from the waveform."""
        col = layout.column(align=True)
        col.label(text="Derived:")
        try:
            cfg = build_radar_config(settings)
        except ValueError:
            col.label(text="Chirp period too short", icon="ERROR")
            return
        col.label(text=f"Range res: {cfg.range_resolution:.2f} m")
        col.label(text=f"Max range: {cfg.max_range:.1f} m")
        col.label(text=f"Velocity res: {cfg.velocity_resolution:.2f} m/s")
        col.label(text=f"Max velocity: ±{cfg.max_velocity:.1f} m/s")


_classes = (RADAR_PT_main,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
