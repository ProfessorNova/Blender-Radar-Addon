"""Scene-level radar properties.

Milestone 1 adds the inputs needed for scene access and raytracing: the
radar object and the ray fan (field of view and ray counts). Milestone 2 adds
the FMCW waveform parameters needed to build the Range-Doppler map (carrier
frequency, bandwidth, sample rate, chirp counts and the FFT window). The full
configurable parameter set together with noise and export lands in milestone 3.

Waveform values are stored in human-friendly units (GHz, MHz, MSPS, us) and
converted to SI when a :class:`core.signal_model.RadarConfig` is built in
``utils/rdm.py``.
"""

import math

import bpy
from bpy.props import (
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
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

    # --- FMCW waveform (milestone 2) ---------------------------------------
    # Stored in convenient units; converted to SI in utils/rdm.py.

    carrier_freq_ghz: FloatProperty(
        name="Carrier Frequency",
        description="FMCW carrier (centre) frequency in GHz",
        default=77.0,
        min=1.0,
        soft_max=300.0,
    )

    bandwidth_mhz: FloatProperty(
        name="Bandwidth",
        description=(
            "Swept bandwidth in MHz. Sets the range resolution "
            "(c / (2 * bandwidth))"
        ),
        default=250.0,
        min=1.0,
        soft_max=5000.0,
    )

    sample_rate_msps: FloatProperty(
        name="Sample Rate",
        description="Fast-time ADC sample rate in mega-samples per second",
        default=10.0,
        min=0.1,
        soft_max=100.0,
    )

    n_samples: IntProperty(
        name="Samples / Chirp",
        description="Fast-time samples per chirp (number of range bins)",
        default=256,
        min=8,
        soft_max=2048,
    )

    n_chirps: IntProperty(
        name="Chirps / Frame",
        description="Slow-time chirps per frame (number of Doppler bins)",
        default=64,
        min=8,
        soft_max=1024,
    )

    chirp_period_us: FloatProperty(
        name="Chirp Period",
        description=(
            "Slow-time spacing between chirps in microseconds. Must be at "
            "least the active chirp duration (samples / sample rate)"
        ),
        default=30.0,
        min=0.1,
        soft_max=1000.0,
    )

    rdm_window: EnumProperty(
        name="FFT Window",
        description="Window applied before the range and Doppler FFTs",
        items=(
            ("none", "None", "No window (rectangular)"),
            ("hann", "Hann", "Hann window (good general default)"),
            ("hamming", "Hamming", "Hamming window"),
            ("blackman", "Blackman", "Blackman window (low sidelobes)"),
        ),
        default="hann",
    )

    rdm_image: PointerProperty(
        name="RDM Image",
        description=(
            "Image data-block holding the most recent Range-Doppler map. Set "
            "automatically by Compute Range-Doppler Map"
        ),
        type=bpy.types.Image,
    )

    # --- Animation rendering (milestone 3) ---------------------------------

    anim_output_dir: StringProperty(
        name="Output Folder",
        description=(
            "Folder for the rendered Range-Doppler PNG sequence (rdm_0001.png, "
            "...). '//' is relative to the saved .blend file"
        ),
        default="//rdm_render/",
        subtype="DIR_PATH",
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
