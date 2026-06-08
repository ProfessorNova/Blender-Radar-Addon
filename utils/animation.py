"""Animation rendering helpers for the Range-Doppler map.

Milestone 3. Saving a single RDM frame to a PNG. The frame iteration, progress
bar and cancellation live in the modal operator
``RADAR_OT_render_animation``; this module only owns the per-frame file output
so the operator stays focused on control flow.

The rendered PNG sequence (``rdm_0001.png``, ``rdm_0002.png``, ...) plays back
as an image sequence in Blender's Image Editor and in external viewers that
support numbered image sequences.
"""

from __future__ import annotations


def frame_filename(frame: int) -> str:
    """Return the zero-padded PNG file name for a given frame number."""
    return f"rdm_{frame:04d}.png"


def save_image_png(image, filepath: str) -> None:
    """Write an image data-block's raw pixels to ``filepath`` as PNG.

    Uses ``Image.save`` (raw buffer) rather than ``save_render`` so the stored
    pixels match what the Image Editor shows, without a view transform applied.
    """
    image.filepath_raw = filepath
    image.file_format = "PNG"
    image.save()
