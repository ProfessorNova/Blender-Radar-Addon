"""Blender Radar.

Blender add-on for simulating radar Range-Doppler maps from a scene via
raytracing. This file is the add-on entry point. It registers and
unregisters all submodules.

In the Extensions format (Blender 4.2+) metadata lives in
``blender_manifest.toml`` and not in a ``bl_info`` dict. Submodule imports
use relative imports so the package works under its dynamically assigned
extension module name.
"""

from . import operators, panels, properties

# Registration order matters. Properties first, since panels and operators
# reference them. Unregistration runs in reverse.
_modules = (properties, operators, panels)


def register():
    """Register all submodules with Blender."""
    for mod in _modules:
        mod.register()


def unregister():
    """Unregister all submodules in reverse order."""
    for mod in reversed(_modules):
        mod.unregister()
