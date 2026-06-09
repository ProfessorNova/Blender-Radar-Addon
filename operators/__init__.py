"""Radar operators.

Milestone 1 adds :class:`RADAR_OT_extract_scatter_points`, which casts a fan
of rays from the radar object and reports the resulting scatter points (range
and radial velocity) for the current frame. Milestone 2 implements
:class:`RADAR_OT_compute_rdm`, which builds the Range-Doppler map from those
scatter points and writes it to a Blender image. Milestone 3 adds
:class:`RADAR_OT_view_rdm` and the modal
:class:`RADAR_OT_render_animation`, which renders an RDM per frame across the
scene frame range with a progress bar and optional movie encoding. Milestone 4
adds the modal :class:`RADAR_OT_export_dataset`, which renders the frame range
into a CARRADA-style range-Doppler dataset (one ``.npy`` per frame plus a
``metadata.json``) on disk.
"""

import os

import bpy
from bpy.types import Operator

from ..core.export import RD_SUBDIR
from ..utils.animation import frame_filename, save_image_png
from ..utils.export import save_scene_rd_frame, write_dataset_metadata
from ..utils.rdm import (
    RDM_IMAGE_NAME,
    build_radar_config,
    compute_scene_rdm,
    show_image_in_editor,
)
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
    """Build the Range-Doppler map for the current frame and write an image."""

    bl_idname = "radar.compute_rdm"
    bl_label = "Compute Range-Doppler Map"
    bl_description = (
        "Cast rays from the radar object, synthesize the FMCW beat signal and "
        f"write the Range-Doppler map to the '{RDM_IMAGE_NAME}' image"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.scene.radar_settings.radar_object is not None

    def execute(self, context):
        settings = context.scene.radar_settings
        if settings.radar_object is None:
            self.report({"ERROR"}, "No radar object selected")
            return {"CANCELLED"}

        try:
            result = compute_scene_rdm(context, settings)
        except ValueError as exc:
            self.report({"ERROR"}, f"Invalid radar configuration: {exc}")
            return {"CANCELLED"}

        # Expose the image data-block so the panel's image widget can show it.
        settings.rdm_image = result.image

        if result.n_points == 0:
            self.report(
                {"WARNING"},
                "No scatter points: rays did not hit geometry within max "
                f"range. Empty '{RDM_IMAGE_NAME}' image written.",
            )
            return {"FINISHED"}

        show_image_in_editor(result.image)
        # Redraw the N-panel so the embedded RDM preview updates immediately.
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        self.report(
            {"INFO"},
            f"RDM from {result.n_points} points written to "
            f"'{RDM_IMAGE_NAME}' | strongest target r={result.peak_range:.2f} m "
            f"v={result.peak_velocity:+.2f} m/s",
        )
        return {"FINISHED"}


class RADAR_OT_view_rdm(Operator):
    """Open the Range-Doppler image in an Image Editor."""

    bl_idname = "radar.view_rdm"
    bl_label = "View in Image Editor"
    bl_description = (
        "Show the Range-Doppler image in an Image Editor, opening a new window "
        "if none is available"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return bpy.data.images.get(RDM_IMAGE_NAME) is not None

    def execute(self, context):
        image = bpy.data.images.get(RDM_IMAGE_NAME)
        if image is None:
            self.report({"WARNING"}, "No Range-Doppler map computed yet")
            return {"CANCELLED"}

        # Prefer an Image Editor that is already open.
        if show_image_in_editor(image):
            return {"FINISHED"}

        # Otherwise duplicate the current area into a new window and switch it
        # to an Image Editor showing the map.
        try:
            bpy.ops.wm.window_new()
            area = context.window_manager.windows[-1].screen.areas[0]
            area.type = "IMAGE_EDITOR"
            area.spaces.active.image = image
        except (RuntimeError, AttributeError):
            self.report(
                {"WARNING"},
                f"Open an Image Editor and pick the '{RDM_IMAGE_NAME}' image",
            )
            return {"CANCELLED"}
        return {"FINISHED"}


class RADAR_OT_render_animation(Operator):
    """Render a Range-Doppler map for every frame of the scene range."""

    bl_idname = "radar.render_animation"
    bl_label = "Render RDM Animation"
    bl_description = (
        "Compute a Range-Doppler map for each frame of the scene range and "
        "write a PNG sequence to the output folder. Press Esc to cancel"
    )
    bl_options = {"REGISTER"}

    _timer = None

    @classmethod
    def poll(cls, context):
        return context.scene.radar_settings.radar_object is not None

    def invoke(self, context, event):
        scene = context.scene
        settings = scene.radar_settings

        # Fail fast on an inconsistent waveform before touching the timeline.
        try:
            build_radar_config(settings)
        except ValueError as exc:
            self.report({"ERROR"}, f"Invalid radar configuration: {exc}")
            return {"CANCELLED"}

        out_dir = bpy.path.abspath(settings.anim_output_dir)
        if not out_dir or not os.path.isabs(out_dir):
            self.report(
                {"ERROR"},
                "Save the .blend file or set an absolute output folder first",
            )
            return {"CANCELLED"}
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            self.report({"ERROR"}, f"Cannot create output folder: {exc}")
            return {"CANCELLED"}

        step = max(scene.frame_step, 1)
        self._frames = list(range(scene.frame_start, scene.frame_end + 1, step))
        if not self._frames:
            self.report({"WARNING"}, "Empty frame range")
            return {"CANCELLED"}

        self._out_dir = out_dir
        self._index = 0
        self._orig_frame = scene.frame_current
        self._written = []
        self._area = context.area

        wm = context.window_manager
        wm.progress_begin(0, len(self._frames))
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._cleanup(context)
            self.report(
                {"WARNING"},
                f"Cancelled after {len(self._written)} frame(s); "
                f"PNGs kept in {self._out_dir}",
            )
            return {"CANCELLED"}

        if event.type != "TIMER":
            return {"RUNNING_MODAL"}

        if self._index >= len(self._frames):
            return self._complete(context)

        frame = self._frames[self._index]
        if not self._render_frame(context, frame):
            self._cleanup(context)
            return {"CANCELLED"}

        self._index += 1
        context.window_manager.progress_update(self._index)
        if self._area is not None:
            self._area.header_text_set(
                f"Rendering RDM frame {self._index}/{len(self._frames)} "
                "(Esc to cancel)"
            )
        return {"RUNNING_MODAL"}

    def _render_frame(self, context, frame: int) -> bool:
        scene = context.scene
        settings = scene.radar_settings
        scene.frame_set(frame)
        try:
            result = compute_scene_rdm(context, settings)
        except ValueError as exc:
            self.report({"ERROR"}, f"Invalid radar configuration: {exc}")
            return False
        path = os.path.join(self._out_dir, frame_filename(frame))
        try:
            save_image_png(result.image, path)
        except (RuntimeError, OSError) as exc:
            self.report({"ERROR"}, f"Failed to write {path}: {exc}")
            return False
        self._written.append(path)
        return True

    def _complete(self, context):
        count = len(self._written)
        self._cleanup(context)
        self.report(
            {"INFO"},
            f"Rendered {count} RDM frame(s) to {self._out_dir}",
        )
        return {"FINISHED"}

    def _cleanup(self, context):
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        wm.progress_end()
        context.scene.frame_set(self._orig_frame)
        if self._area is not None:
            self._area.header_text_set(None)


class RADAR_OT_export_dataset(Operator):
    """Render the frame range into a CARRADA-style range-Doppler dataset."""

    bl_idname = "radar.export_dataset"
    bl_label = "Export Dataset"
    bl_description = (
        "Render the scene frame range and write a CARRADA-style range-Doppler "
        "dataset (one .npy per frame plus metadata.json) to the export folder. "
        "Press Esc to cancel"
    )
    bl_options = {"REGISTER"}

    _timer = None

    @classmethod
    def poll(cls, context):
        return context.scene.radar_settings.radar_object is not None

    def invoke(self, context, event):
        scene = context.scene
        settings = scene.radar_settings

        # Fail fast on an inconsistent waveform before touching the timeline.
        try:
            self._config = build_radar_config(settings)
        except ValueError as exc:
            self.report({"ERROR"}, f"Invalid radar configuration: {exc}")
            return {"CANCELLED"}

        out_dir = bpy.path.abspath(settings.export_dir)
        if not out_dir or not os.path.isabs(out_dir):
            self.report(
                {"ERROR"},
                "Save the .blend file or set an absolute export folder first",
            )
            return {"CANCELLED"}
        try:
            os.makedirs(os.path.join(out_dir, RD_SUBDIR), exist_ok=True)
        except OSError as exc:
            self.report({"ERROR"}, f"Cannot create export folder: {exc}")
            return {"CANCELLED"}

        step = max(scene.frame_step, 1)
        self._frames = list(range(scene.frame_start, scene.frame_end + 1, step))
        if not self._frames:
            self.report({"WARNING"}, "Empty frame range")
            return {"CANCELLED"}

        self._out_dir = out_dir
        self._index = 0
        self._orig_frame = scene.frame_current
        self._frame_map = {}
        self._area = context.area

        wm = context.window_manager
        wm.progress_begin(0, len(self._frames))
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._write_metadata(context)
            self._cleanup(context)
            self.report(
                {"WARNING"},
                f"Cancelled after {len(self._frame_map)} frame(s); "
                f"dataset kept in {self._out_dir}",
            )
            return {"CANCELLED"}

        if event.type != "TIMER":
            return {"RUNNING_MODAL"}

        if self._index >= len(self._frames):
            return self._complete(context)

        frame = self._frames[self._index]
        if not self._export_frame(context, frame):
            self._cleanup(context)
            return {"CANCELLED"}

        self._index += 1
        context.window_manager.progress_update(self._index)
        if self._area is not None:
            self._area.header_text_set(
                f"Exporting RD frame {self._index}/{len(self._frames)} "
                "(Esc to cancel)"
            )
        return {"RUNNING_MODAL"}

    def _export_frame(self, context, frame: int) -> bool:
        scene = context.scene
        settings = scene.radar_settings
        scene.frame_set(frame)
        try:
            result = compute_scene_rdm(context, settings)
        except ValueError as exc:
            self.report({"ERROR"}, f"Invalid radar configuration: {exc}")
            return False
        try:
            save_scene_rd_frame(
                self._out_dir, self._index, result, settings.export_db_offset
            )
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Failed to write frame {self._index}: {exc}")
            return False
        self._frame_map[f"{self._index:06d}"] = frame
        return True

    def _write_metadata(self, context):
        settings = context.scene.radar_settings
        try:
            write_dataset_metadata(
                self._out_dir, settings, self._config, self._frame_map
            )
        except OSError as exc:
            self.report({"WARNING"}, f"Could not write metadata.json: {exc}")

    def _complete(self, context):
        self._write_metadata(context)
        count = len(self._frame_map)
        self._cleanup(context)
        self.report(
            {"INFO"},
            f"Exported {count} RD frame(s) to {self._out_dir}",
        )
        return {"FINISHED"}

    def _cleanup(self, context):
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        wm.progress_end()
        context.scene.frame_set(self._orig_frame)
        if self._area is not None:
            self._area.header_text_set(None)


_classes = (
    RADAR_OT_extract_scatter_points,
    RADAR_OT_compute_rdm,
    RADAR_OT_view_rdm,
    RADAR_OT_render_animation,
    RADAR_OT_export_dataset,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
