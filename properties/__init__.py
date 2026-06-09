"""Scene-level radar properties.

Milestone 1 adds the inputs needed for scene access and raytracing: the
radar object and the ray fan (field of view and ray counts). Milestone 2 adds
the FMCW waveform parameters needed to build the Range-Doppler map (carrier
frequency, bandwidth, sample rate, chirp counts and the FFT window). The full
configurable parameter set together with noise and export lands in milestone 3.

Waveform values are stored in human-friendly units (GHz, MHz, MSPS, us) and
converted to SI when a :class:`core.signal_model.RadarConfig` is built in
``utils/rdm.py``.

Milestone 4 completes the configurable parameter set with the noise and clutter
model and the dataset export path, all reproducible through a single seed.
"""

import math

import bpy
from bpy.props import (
    BoolProperty,
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

    # Ray-fan range clip. Default matches the Carradar reference (50 m); keep
    # it at or below the waveform's unambiguous max range (shown in the panel).
    max_range: FloatProperty(
        name="Max Range",
        description="Maximum unambiguous range in meters",
        default=50.0,
        min=1.0,
        soft_max=1000.0,
        unit="LENGTH",
    )

    fov_azimuth: FloatProperty(
        name="FOV Azimuth",
        description="Horizontal field of view of the ray fan",
        default=math.radians(180.0),
        min=math.radians(1.0),
        max=math.radians(180.0),
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
        description=(
            "Number of rays across azimuth. The Carradar default of 256 over a "
            "180 deg FOV samples the scene at ~0.70 deg; note this is geometric "
            "scene sampling, not the radar's angular resolution (an array "
            "feature, milestone 5)"
        ),
        default=256,
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

    # 767.5 MHz with 256 samples gives max_range = 256 * c/(2*B) = 50 m at a
    # 0.1953 m (~0.20 m) range resolution, matching the Carradar max range,
    # resolution and sample count. The reference table's 4 GHz would force
    # either a 9.6 m max range or 1334 samples (a 64x1334 RDM image), so the
    # bandwidth is the one value traded away to keep all three others.
    bandwidth_mhz: FloatProperty(
        name="Bandwidth",
        description=(
            "Swept bandwidth in MHz. Sets the range resolution "
            "(c / (2 * bandwidth))"
        ),
        default=767.5,
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

    # 256 range bins -> a 64 x 256 RDM image. With the 767.5 MHz bandwidth this
    # spans the Carradar 50 m max range at ~0.20 m resolution.
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

    # 72.5 us with 64 chirps reproduces the Carradar velocity figures:
    # max +-13.43 m/s and 0.42 m/s resolution at 77 GHz.
    chirp_period_us: FloatProperty(
        name="Chirp Period",
        description=(
            "Slow-time spacing between chirps in microseconds. Must be at "
            "least the active chirp duration (samples / sample rate)"
        ),
        default=72.5,
        min=0.1,
        soft_max=1000.0,
    )

    rdm_window: EnumProperty(
        name="FFT Window",
        description="Window applied before the range and Doppler FFTs",
        items=(
            ("none", "None",
             "No window: sharp/thin peaks and strong sinc sidelobes "
             "(the 'sparks' of real data)"),
            ("hann", "Hann", "Hann window: wide main lobe, low sidelobes"),
            ("hamming", "Hamming", "Hamming window"),
            ("blackman", "Blackman", "Blackman window (low sidelobes)"),
        ),
        default="none",
    )

    rdm_dynamic_range_db: FloatProperty(
        name="Display Range",
        description=(
            "Dynamic range in dB shown in the RDM image and preview: the "
            "magnitude is mapped from (peak - this) to peak. Smaller compresses "
            "the floor and brightens the noise background, larger darkens it"
        ),
        default=90.0,
        min=10.0,
        soft_max=120.0,
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

    # --- Noise and clutter (milestone 4) -----------------------------------
    # Strengths are in the same voltage units as the synthesized targets, where
    # a unit-RCS target at 1 m has amplitude 1.

    # Noise and clutter default to on: the reference dataset has a clear noise
    # floor and a strong static-clutter ridge, and our coherent FFT gain keeps
    # targets visible well above this level.
    noise_enabled: BoolProperty(
        name="Thermal Noise",
        description="Add white complex Gaussian receiver noise to the beat cube",
        default=True,
    )

    noise_std: FloatProperty(
        name="Noise Std",
        description=(
            "RMS thermal noise voltage added to every beat sample (same units "
            "as a unit-RCS target at 1 m)"
        ),
        default=0.1,
        min=0.0,
        soft_max=1.0,
        precision=4,
    )

    clutter_enabled: BoolProperty(
        name="Clutter",
        description=(
            "Add stationary background scatterers; they pile up in the "
            "zero-velocity column of the map"
        ),
        default=True,
    )

    clutter_count: IntProperty(
        name="Clutter Points",
        description=(
            "Number of random stationary clutter scatterers. Enough to fill "
            "most range bins gives the connected zero-velocity ridge seen in "
            "real data (~2x the range bins works well)"
        ),
        default=512,
        min=0,
        soft_max=4000,
    )

    clutter_std: FloatProperty(
        name="Clutter Std",
        description="RMS amplitude of the clutter scatterers",
        default=0.05,
        min=0.0,
        soft_max=1.0,
        precision=4,
    )

    clutter_falloff: FloatProperty(
        name="Clutter Falloff",
        description=(
            "Range falloff exponent of the clutter amplitude (1/R**exp): 0 is "
            "uniform, 1 fades the ridge from bright near to dim far like real "
            "ground clutter"
        ),
        default=1.0,
        min=0.0,
        soft_max=3.0,
    )

    noise_seed: IntProperty(
        name="Seed",
        description=(
            "Random seed for noise and clutter. The same seed reproduces the "
            "dataset; the seed is combined with the frame so animation frames "
            "differ while staying reproducible"
        ),
        default=0,
        min=0,
    )

    # --- Dataset export (milestone 4) --------------------------------------

    export_dir: StringProperty(
        name="Dataset Folder",
        description=(
            "Folder filled with the CARRADA-style range-Doppler dataset "
            "(range_doppler_processed/000000.npy, ..., metadata.json). "
            "'//' is relative to the saved .blend file"
        ),
        default="//radar_dataset/",
        subtype="DIR_PATH",
    )

    export_db_offset: FloatProperty(
        name="dB Offset",
        description=(
            "Added to the exported 20*log10|RDM| so values land in the "
            "reference range (~45..105 dB). Tune to match the reference look"
        ),
        default=47.0,
        soft_min=0.0,
        soft_max=120.0,
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
