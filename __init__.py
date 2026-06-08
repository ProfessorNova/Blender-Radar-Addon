"""Blender Radar.

Blender add-on for simulating radar Range-Doppler maps from a scene via
raytracing. This file is the add-on entry point. It registers and
unregisters all submodules.

In the Extensions format (Blender 4.2+) metadata lives in
``blender_manifest.toml`` and not in a ``bl_info`` dict. Submodule imports
use relative imports so the package works under its dynamically assigned
extension module name.

The bpy-dependent submodules are imported lazily inside ``register`` /
``unregister`` rather than at module load. That keeps importing this package
harmless outside Blender (e.g. when pytest collects the repository root as a
package), while the bpy-independent ``core`` package stays directly testable.
"""


def _ordered_modules():
    """Return the submodules in registration order.

    Properties come first because panels and operators reference them.
    Imported here (not at module top level) so this package imports without
    bpy available.
    """
    from . import operators, panels, properties
    from .utils import overlay, preview

    return (properties, preview, operators, panels, overlay)


def register():
    """Register all submodules with Blender."""
    for mod in _ordered_modules():
        mod.register()


def unregister():
    """Unregister all submodules in reverse order."""
    for mod in reversed(_ordered_modules()):
        mod.unregister()
