"""Blender-independent signal processing core.

Modules in this package must not import bpy. This keeps the numerical code
testable outside Blender and reusable in a plain Python pipeline. Real
modules (raytracing, signal_model, range_doppler, doppler) are added from
milestone 1 onward.
"""
