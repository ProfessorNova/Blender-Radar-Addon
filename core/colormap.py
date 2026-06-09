"""Perceptual colormaps for visualizing the Range-Doppler map.

Blender-independent. Blender ships only NumPy, so a colormap is provided as a
small embedded lookup table interpolated with NumPy rather than as a matplotlib
runtime dependency. The plasma table is a 64-point sampling of matplotlib's
``plasma`` colormap (maximum 8-bit interpolation error ~1.3, i.e. visually
identical for a magnitude heatmap). The values were generated from matplotlib,
not hand-authored.
"""

from __future__ import annotations

import numpy as np

# 64 evenly spaced RGB anchors of matplotlib's "plasma" colormap, running from
# dark blue (low) through magenta and orange to yellow (high).
_PLASMA = np.array(
    [
        (0.05038, 0.02980, 0.52797),
        (0.09638, 0.02516, 0.54710),
        (0.13238, 0.02226, 0.56325),
        (0.16407, 0.02017, 0.57748),
        (0.19337, 0.01835, 0.59033),
        (0.22120, 0.01650, 0.60208),
        (0.24803, 0.01444, 0.61287),
        (0.27419, 0.01211, 0.62272),
        (0.29985, 0.00956, 0.63162),
        (0.32515, 0.00692, 0.63951),
        (0.35015, 0.00438, 0.64630),
        (0.37490, 0.00225, 0.65188),
        (0.39941, 0.00086, 0.65613),
        (0.42369, 0.00065, 0.65896),
        (0.44771, 0.00208, 0.66024),
        (0.47146, 0.00568, 0.65990),
        (0.50068, 0.01405, 0.65709),
        (0.52363, 0.02453, 0.65290),
        (0.54616, 0.03895, 0.64701),
        (0.56820, 0.05578, 0.63948),
        (0.58972, 0.07288, 0.63041),
        (0.61067, 0.09020, 0.61995),
        (0.63102, 0.10770, 0.60829),
        (0.65075, 0.12531, 0.59562),
        (0.66985, 0.14299, 0.58215),
        (0.68832, 0.16071, 0.56810),
        (0.70618, 0.17844, 0.55366),
        (0.72344, 0.19616, 0.53898),
        (0.74014, 0.21386, 0.52422),
        (0.75630, 0.23156, 0.50947),
        (0.77196, 0.24924, 0.49481),
        (0.78713, 0.26692, 0.48031),
        (0.80547, 0.28906, 0.46242),
        (0.81965, 0.30681, 0.44831),
        (0.83342, 0.32464, 0.43437),
        (0.84679, 0.34255, 0.42058),
        (0.85975, 0.36059, 0.40692),
        (0.87230, 0.37877, 0.39336),
        (0.88444, 0.39714, 0.37986),
        (0.89613, 0.41571, 0.36641),
        (0.90736, 0.43452, 0.35297),
        (0.91811, 0.45360, 0.33953),
        (0.92833, 0.47297, 0.32607),
        (0.93799, 0.49267, 0.31257),
        (0.94705, 0.51270, 0.29905),
        (0.95547, 0.53309, 0.28549),
        (0.96320, 0.55387, 0.27191),
        (0.97020, 0.57503, 0.25833),
        (0.97786, 0.60205, 0.24139),
        (0.98304, 0.62413, 0.22794),
        (0.98733, 0.64663, 0.21465),
        (0.99068, 0.66956, 0.20164),
        (0.99303, 0.69291, 0.18908),
        (0.99432, 0.71668, 0.17721),
        (0.99450, 0.74088, 0.16634),
        (0.99348, 0.76550, 0.15689),
        (0.99121, 0.79054, 0.14938),
        (0.98762, 0.81598, 0.14436),
        (0.98265, 0.84181, 0.14230),
        (0.97627, 0.86802, 0.14335),
        (0.96844, 0.89456, 0.14701),
        (0.95928, 0.92141, 0.15157),
        (0.94915, 0.94844, 0.15218),
        (0.94002, 0.97516, 0.13133),
    ],
    dtype=np.float64,
)

COLORMAPS = {"plasma": _PLASMA}


def apply_colormap(normalized, name: str = "plasma") -> np.ndarray:
    """Map values in ``[0, 1]`` to RGB through a named colormap.

    Args:
        normalized: Array of values in ``[0, 1]`` (any shape). Values outside
            the range are clamped.
        name: Colormap name; currently only ``"plasma"``.

    Returns:
        A ``float64`` array of shape ``(*normalized.shape, 3)`` with RGB
        channels in ``[0, 1]``.

    Raises:
        ValueError: If ``name`` is not a known colormap.
    """
    try:
        table = COLORMAPS[name]
    except KeyError:
        raise ValueError(
            f"unknown colormap '{name}'; choose from {list(COLORMAPS)}"
        ) from None

    values = np.clip(np.asarray(normalized, dtype=np.float64), 0.0, 1.0)
    positions = np.linspace(0.0, 1.0, len(table))
    rgb = np.empty(values.shape + (3,), dtype=np.float64)
    for c in range(3):
        rgb[..., c] = np.interp(values, positions, table[:, c])
    return rgb
