"""Custom image preview so the RDM can be shown inside the N-panel.

Blender panels cannot draw a raw image, but they can draw an icon from a
preview. We keep one preview collection and rebuild its ``rdm`` entry from the
normalised Range-Doppler pixels every time the map is computed, then draw it
with ``layout.template_icon``. Rebuilding (rather than mutating) the entry
gives a fresh ``icon_id`` so the panel always shows the latest result.
"""

from __future__ import annotations

import bpy.utils.previews

_collection = None
_RDM_KEY = "rdm"


def update_rdm_preview(rgba_flat, width: int, height: int):
    """Replace the RDM preview with new pixels.

    Args:
        rgba_flat: Flat RGBA float buffer of length ``width * height * 4`` in
            [0, 1], same bottom-row-first layout as a Blender image.
        width: Image width in pixels (range bins).
        height: Image height in pixels (Doppler bins).
    """
    if _collection is None:
        return None
    if _RDM_KEY in _collection:
        del _collection[_RDM_KEY]
    preview = _collection.new(_RDM_KEY)
    preview.image_size = (width, height)
    preview.image_pixels_float.foreach_set(rgba_flat)
    return preview


def rdm_icon_id():
    """Icon id of the current RDM preview, or ``None`` if none computed yet."""
    if _collection is None or _RDM_KEY not in _collection:
        return None
    return _collection[_RDM_KEY].icon_id


def register():
    global _collection
    _collection = bpy.utils.previews.new()


def unregister():
    global _collection
    if _collection is not None:
        bpy.utils.previews.remove(_collection)
        _collection = None
