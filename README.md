# Blender Radar Addon

A Blender add-on that simulates radar Range-Doppler maps from a scene using
raytracing.

## Status

Milestone 0 complete: project skeleton. A runnable, empty add-on with a panel,
an operator and a property group. See the roadmap below for the full plan.

## Requirements

- Blender 5.0 or newer
- NumPy only (shipped with Blender)

## Installation

1. Package the repository as a ZIP (see Development) or use the provided
   `radar_rdm_generator.zip`.
2. In Blender: Edit > Preferences > Get Extensions > Install from Disk.
3. Select the ZIP and enable it.
4. The panel appears in the 3D viewport under N-panel > "Radar" tab.

## Development

### VS Code with the Blender Development extension

The recommended setup is VS Code with the
[Blender Development](https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development)
extension by Jacques Lucke. It provides hot reload, an integrated debugger,
and a one-command start workflow.

**One-time setup**

1. Install the extension from the VS Code marketplace (`JacquesLucke.blender-development`).
2. Open the repository folder in VS Code.
3. Run the command palette entry **Blender: Start** (`Ctrl+Shift+P` →
   `Blender: Start`). On the first run it will ask for the path to the
   Blender executable (e.g. `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe`).
   The path is saved in your VS Code user settings and is not committed to the
   repository.

**Daily workflow**

| Action | Command |
|--------|---------|
| Launch Blender | **Blender: Start** |
| Reload the add-on after a code change | **Blender: Reload Addons** |
| Stop Blender | **Blender: Stop** |

After **Blender: Start** the add-on is automatically installed into the
running Blender instance. You do not need to create a ZIP or touch
Edit > Preferences. Every time you save a `.py` file and run
**Blender: Reload Addons**, Blender re-imports the changed modules without
restarting.

**Debugging**

The extension launches Blender with `debugpy` attached. To hit a breakpoint:

1. Set a breakpoint in VS Code (click in the gutter or press `F9`).
2. Run **Blender: Start** (or **Blender: Reload Addons** if already running).
3. Trigger the code path in Blender (e.g. click *Compute Range-Doppler Map*
   in the N-panel under the **Radar** tab).
4. VS Code pauses at the breakpoint with the full call stack and locals panel.

**Packaging a ZIP (optional)**

To create an installable `.zip` for distribution or manual installation:

    # Windows PowerShell
    Compress-Archive -Path .\* -DestinationPath radar_rdm_generator.zip `
        -CompressionLevel Optimal

Or use the command palette entry **Blender: Build and Install** which packages
and installs in one step.

### Running tests without Blender

Blender-independent logic lives in `core/` and must not import `bpy`. This
keeps the numerical code testable outside Blender and reusable in a plain
Python pipeline. Tests run without Blender:

    python -m pytest tests/

## Project structure

    blender_radar_addon/
        __init__.py              # entry point, register/unregister
        blender_manifest.toml    # extension manifest (Blender 4.2+ format)
        operators/               # operators that trigger computation
        panels/                  # UI panels
        properties/              # PropertyGroups for radar configuration
        core/                    # Blender-independent signal processing
        utils/                   # scene access and math helpers
        tests/                   # tests for the Blender-independent core

## Roadmap

The project is organized into milestones. Each milestone builds on the
previous one and yields a testable state.

| MS | Title | Outcome |
|----|-------|---------|
| 0 | Skeleton and toolchain | Runnable, empty add-on |
| 1 | Scene access and raytracing | Scatter points with range and radial velocity |
| 2 | Signal model and first RDM | Plausible Range-Doppler map |
| 3 | Configuration, noise and export | Reproducible dataset with ground truth |
| 4 | Antenna array and angle information | Correct angle estimation, ADM and RAM |
| 5 | Detection and micro-Doppler | CFAR detections and micro-Doppler spectrogram |
| 6 | Adversarial module and plausibilization | Physically back-projected perturbation |
| 7 | Evaluation and robustness analysis | Reproducible evaluation |

### Dependencies between milestones

- MS 0 to 3 form the indispensable base and are done sequentially.
- MS 4 and 5 are largely independent and may be swapped. MS 5 is the more
  important one for the research goal.
- MS 6 and 7 require at least the base up to MS 3 and benefit strongly from
  the detection feature from MS 5.

### Milestone 0 - Skeleton and toolchain

Goal: a runnable, empty add-on and a working development environment.

- [x] Package structure with `__init__.py`, `register` and `unregister`
- [x] Minimal UI panel in the N-panel without function
- [ ] VS Code with the Blender Development extension (hot reload, debugging)
- [x] Test setup for the Blender-independent logic in `core/`
- [x] License (GPL-3.0) and `CITATION.cff` added

Acceptance: the add-on installs, enables and reloads, and shows a visible
panel.

### Milestone 1 - Scene access and raytracing

Goal: extract the geometric raw data from the scene.

- [ ] Read geometry and transforms (`utils/scene_access.py`)
- [ ] Ray cast against the scene via `scene.ray_cast()` (`core/raytracing.py`)
- [ ] Radar object with position and viewing direction
- [ ] Radial velocity of hit points from positional difference across frames

Acceptance: a list of scatter points with range and radial velocity for a
given frame.

### Milestone 2 - Signal model and first Range-Doppler map

Goal: the first complete RDM.

- [ ] Signal model with FMCW chirp and the radar equation (`core/signal_model.py`)
- [ ] Build the data cube in the dimensions sample and chirp
- [ ] Two-dimensional FFT for RDM generation (`core/range_doppler.py`)
- [ ] Doppler evaluation (`core/doppler.py`)
- [ ] Simple RDM visualization in Blender (image data-block)

Acceptance: a plausible RDM for a scene with a few moving objects, targets
appear at the expected range and Doppler positions.

### Milestone 3 - Configuration, noise and export

Goal: make the results usable for downstream work.

- [ ] Configurable radar parameters via `PropertyGroup` (`properties/radar_settings.py`)
- [ ] Noise model with thermal noise and optional clutter
- [ ] Export data cube and RDM (`.npy` or HDF5) (`core/export.py`)
- [ ] Ground-truth export of object positions and velocities

Acceptance: a reproducible dataset of RDM and matching ground truth, loadable
outside Blender. The base is complete at this point.

### Milestone 4 - Antenna array and angle information

Goal: extend the model by the spatial dimension.

- [ ] Multi-channel array (ULA first) in configuration and signal model
- [ ] Compute phase differences between channels
- [ ] Angle estimation (`core/array_processing.py`)
- [ ] Angle-Doppler map (ADM) and Range-Angle map (RAM)

Acceptance: correct angle estimation for a target with a known angle of
arrival.

### Milestone 5 - Detection and micro-Doppler

Goal: advanced evaluations that double as assessment tools for the later
attack.

- [ ] CFAR detection (`core/detection.py`), optionally with clustering
- [ ] Micro-Doppler spectrogram across multiple frames (`core/micro_doppler.py`)

Acceptance: extracted detections from the RDM and a recognizable micro-Doppler
pattern for a rotating or vibrating structure.

### Milestone 6 - Adversarial module and physical plausibilization

Goal: the core of the research project, built on the complete pipeline.

- [ ] Interface to accept a target perturbation in the RD domain (`core/adversarial.py`)
- [ ] Decompose the perturbation into scatter centers (range, radial velocity, backscatter strength)
- [ ] Back-project the scatter centers through the existing signal chain
- [ ] Project onto physically admissible perturbations (`core/constraints.py`):
      non-negativity, energy limits, waveform consistency

Acceptance: a perturbation generated through the signal chain together with
the quantified discrepancy from the ideally optimized digital perturbation.

Note: this milestone deliberately ends at simulation and physical
plausibilization, not at a real transmit instruction.

### Milestone 7 - Evaluation and robustness analysis

Goal: the scientific evaluation.

- [ ] Systematic evaluation of the attack against the target model using ground truth
- [ ] Comparison of digital versus physically constrained perturbations
- [ ] Investigate micro-Doppler as a possible detector for decoy targets
- [ ] Batch processing across animation sequences for statistical evaluation

Acceptance: a reproducible evaluation run that contrasts the effectiveness and
the physical realizability of the attack.

## License

GPL-3.0-or-later. Add-ons bind the GPL-licensed `bpy` API and must therefore
be GPL-compatible.
