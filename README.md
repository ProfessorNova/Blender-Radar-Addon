# Blender Radar Addon

A Blender add-on that simulates a radar from a scene using raytracing and
produces radar maps from the resulting signal.

## Concept: the radar data cube

The central object of the simulation is the **radar data cube**, not a single
map. From the raw signal a series of FFTs yields a volume with up to three
axes — **range**, **Doppler** (radial velocity) and **angle** (direction of
arrival). The familiar radar maps are all 2D views into this one cube:

| Map | Axes | View into the cube |
|-----|------|--------------------|
| **Range-Doppler** (RDM) | range × Doppler | one channel, or summed over channels |
| **Range-Angle** (RAM) | range × angle | one Doppler slice / integrated over Doppler |
| **Angle-Doppler** (ADM) | angle × Doppler | one range slice / integrated over range |

The angle axis only exists once an antenna **array** is modelled (milestone 5).
Until then the cube collapses to its range × Doppler face, so the only view the
add-on can produce is the Range-Doppler map — which is exactly what milestones
1-3 deliver. Concretely the array case is a stack of RDMs across the antenna
channels, with an extra angle FFT across that stack; RAM and ADM are then
slices of the resulting 3D cube.

## Status

Milestones 1-3 complete. On top of the raytracing, the add-on synthesizes an
FMCW beat signal from the scatter points and produces a Range-Doppler map (RDM)
via a 2D FFT, written to a Blender image data-block. This is the single-channel
case of the data cube above; the angle axis (and the RAM/ADM views) arrive with
the antenna array in milestone 5. The detection-volume overlay, the in-panel RDM
preview and the Image-Editor viewing all work, and a modal renderer turns the
whole scene frame range into a PNG image sequence. See the roadmap below for the
full plan.

## Requirements

- Blender 5.0 or newer
- NumPy only (shipped with Blender)

## Installation

The add-on is installed from a ZIP. Either grab a release ZIP or build one from
the source (see [Building the ZIP](#building-the-zip) below).

1. Get the ZIP: download a release, or build it with
   `blender --command extension build` (see [Building the ZIP](#building-the-zip)).
2. In Blender: Edit > Preferences > Get Extensions > Install from Disk.
3. Select the ZIP and enable it.
4. The panel appears in the 3D viewport under N-panel > "Radar" tab.

### Building the ZIP

This add-on uses the Blender extension format (4.2+), so the supported way to
package it is Blender's own builder. Run it from the repository root — the
command is **identical on Windows, macOS and Linux**:

    blender --command extension build

It reads `blender_manifest.toml`, honours the `[build]` exclude list there
(so `.venv`, `.git`, `tests/`, `__pycache__`, `pyproject.toml` and friends are
left out) and writes `radar_addon-0.1.0.zip` next to the manifest. This is the
only method that guarantees a ZIP Blender will accept, so it is the recommended
one.

If `blender` is not on your `PATH`, call the executable directly:

| OS | Command |
|----|---------|
| Windows | `& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --command extension build` |
| macOS | `/Applications/Blender.app/Contents/MacOS/Blender --command extension build` |
| Linux | `/opt/blender/blender --command extension build` |

Adjust the path to match your local Blender install. Inside VS Code with the
Blender Development extension, the command palette entry **Blender: Build and
Install** does the same thing and installs in one step.

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
   Blender executable (e.g. `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`).
   The path is saved in your VS Code user settings and is not committed to the
   repository.

   If VS Code cannot find Blender automatically, create a file
   `.vscode/settings.json` in the project root with the path for your machine:

   ```json
   {
       "blender.executables": [
           {
               "path": "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe"
           }
       ]
   }
   ```

   Adjust the version number to match your local Blender installation.
   `.vscode/` is listed in `.gitignore`, so this file is never committed.

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
            raytracing.py        #   ray fan, range and radial velocity (MS1)
            signal_model.py      #   FMCW config and beat-cube synthesis (MS2)
            range_doppler.py     #   2D FFT, RDM, range axis, peak finder (MS2)
            doppler.py           #   Doppler/velocity conversions, axis (MS2)
        utils/                   # scene access and Blender-side bridges
            scene_access.py      #   scene.ray_cast wrapper, motion sampling
            rdm.py               #   scene -> RDM -> image bridge (MS2)
            preview.py           #   in-panel RDM preview collection (MS3)
            overlay.py           #   viewport detection-volume overlay (MS3)
            animation.py         #   per-frame PNG-sequence save (MS3)
        tests/                   # tests for the Blender-independent core

## Roadmap

The project is organized into milestones. Each milestone builds on the
previous one and yields a testable state.

| MS | Title | Outcome |
|----|-------|---------|
| 0 | Skeleton and toolchain | Runnable, empty add-on (done) |
| 1 | Scene access and raytracing | Scatter points with range and radial velocity (done) |
| 2 | Signal model and first RDM | Plausible Range-Doppler map (done) |
| 3 | Visualization and animation | Overlay, in-panel/Image-Editor viewing, RDM image sequence |
| 4 | Configuration, noise and export | Reproducible dataset with ground truth |
| 5 | Antenna array and angle information | Correct angle estimation, ADM and RAM |
| 6 | Detection and micro-Doppler | CFAR detections and micro-Doppler spectrogram |
| 7 | Adversarial module and plausibilization | Physically back-projected perturbation |
| 8 | Evaluation and robustness analysis | Reproducible evaluation |

### Dependencies between milestones

- MS 0 to 2 and MS 4 form the indispensable base and are done sequentially.
- MS 3 (visualization and animation) is an optional convenience step on top of
  MS 2 and is not required by any later milestone.
- MS 5 and 6 are largely independent and may be swapped. MS 6 is the more
  important one for the research goal.
- MS 7 and 8 require at least the base up to MS 4 and benefit strongly from
  the detection feature from MS 6.

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

- [x] Read geometry and transforms (`utils/scene_access.py`)
- [x] Ray cast against the scene via `scene.ray_cast()` (wrapped for the
      bpy-independent core in `core/raytracing.py`)
- [x] Radar object with position and viewing direction
- [x] Radial velocity of hit points from positional difference across frames

Acceptance: a list of scatter points with range and radial velocity for a
given frame.

The bpy-independent raytracing math (ray-fan generation, range, rigid-body
radial velocity, scatter-point extraction) lives in `core/raytracing.py` and
is fully unit tested. `utils/scene_access.py` wraps `scene.ray_cast` and the
frame stepping needed to sample velocities, and ties both together. In the
viewport N-panel, pick a **Radar Object** (its local -Z axis is the boresight,
matching the camera convention), set the ray fan, and press **Extract Scatter
Points** to report the hits for the current frame.

### Milestone 2 - Signal model and first Range-Doppler map

Goal: the first complete RDM.

- [x] Signal model with FMCW chirp and the radar equation (`core/signal_model.py`)
- [x] Build the data cube in the dimensions sample and chirp
- [x] Two-dimensional FFT for RDM generation (`core/range_doppler.py`)
- [x] Doppler evaluation (`core/doppler.py`)
- [x] Simple RDM visualization in Blender (image data-block)

Acceptance: a plausible RDM for a scene with a few moving objects, targets
appear at the expected range and Doppler positions.

The scatter points from milestone 1 are turned into point targets and fed
through a dechirped FMCW model. `core/signal_model.py` defines `RadarConfig`
(carrier frequency, bandwidth, sample rate, samples per chirp, chirps per
frame, chirp period) with the derived quantities (range/velocity resolution
and the unambiguous range/velocity spans) and synthesizes the complex beat
data cube of shape `(chirps, samples)`. Each target's amplitude follows the
radar equation (voltage ∝ 1/R²) weighted by the cosine of the surface
incidence angle as a simple RCS proxy.

`core/range_doppler.py` applies an optional window (Hann by default) and the
2D FFT — a range FFT along the samples and a Doppler FFT along the chirps —
and exposes the range axis and a peak finder. `core/doppler.py` owns the
velocity axis and the Doppler/velocity conversions. All of this is
bpy-independent and unit tested: a synthesized target is verified to land at
the expected range and velocity cell, with the sign convention that a receding
target (positive radial velocity) appears at a positive velocity bin.

The Blender bridge lives in `utils/rdm.py`. In the viewport N-panel, set the
**Signal Model** parameters (the panel shows the resulting resolutions and
unambiguous spans live) and press **Compute Range-Doppler Map**. The RDM is
written to an image data-block named `RadarRDM` (range on the vertical axis,
velocity / Doppler on the horizontal axis, magnitude in dB normalised over an
80 dB dynamic range). The operator reports the strongest target's range and
velocity. The richer in-panel and Image-Editor viewing is part of milestone 3.

Note: keep the ray-fan **Max Range** at or below the waveform's unambiguous
**Max range** shown in the panel, otherwise distant hits alias into lower
range bins.

Cube perspective: the `(chirps, samples)` beat cube and its 2D FFT are the
single-channel, range × Doppler face of the radar data cube described at the
top. There is no angle axis yet because there is only one antenna. Milestone 5
adds a channel dimension, which turns this 2D cube into a 3D one and makes the
RDM one of three views (alongside RAM and ADM).

### Milestone 3 - Visualization and animation

Goal: make the radar easy to set up and inspect, and extend the single-frame
RDM to whole animations.

- [x] Detection-volume viewport overlay (`utils/overlay.py`): a wireframe
      frustum (corner rays, boresight, the rectangle at max range and a
      cross-hair), like a spotlight's cone, showing the field of view and range
      while posing the radar object
- [x] In-panel RDM preview (`utils/preview.py`): panels cannot draw a raw
      image, so a preview collection is rebuilt from the RDM pixels and drawn
      with `template_icon`, making the result visible in the sidebar
- [x] Native image data-block widget (`template_ID`) bound to the `RadarRDM`
      image plus a **View in Image Editor** button that reuses an open Image
      Editor or opens a new window
- [x] Animation rendering: an operator that iterates the scene frame range and
      computes an RDM per frame, with the ergonomics of *Render Animation*
- [x] Progress feedback in the UI (a modal, cancelable operator with a progress
      bar) so long sequences stay responsive
- [x] Write each frame to an image sequence that plays back in a video player
      or Blender's Image Editor, reusing the single-frame pipeline in
      `utils/rdm.py`

Acceptance: the detection volume and the RDM are visible without leaving the
viewport, and a single button renders the RDM across the frame range, shows
progress while running, and yields an image sequence that plays back as a video
in which targets move in range and Doppler over time.

The **Animation** section of the panel sets the output folder and shows the
scene frame range that will be rendered. **Render RDM Animation** is a modal
operator (`utils/animation.py`): it steps through `frame_start`..`frame_end`
with `frame_step`, runs the single-frame pipeline (`compute_scene_rdm`) per
frame, writes a PNG sequence (`rdm_0001.png`, `rdm_0002.png`, ...) and shows a
progress bar in the status bar plus the current frame in the header; pressing
**Esc** cancels and keeps the frames written so far. The sequence plays back as
an image sequence in Blender's Image Editor or in external viewers, and can be
encoded to a movie with any external tool if needed.

Note: the rendered image sequence here is a convenience visualization, whereas
the scientific data export (raw data cube and ground truth) is owned by
milestone 4.

### Milestone 4 - Configuration, noise and export

Goal: make the results usable for downstream work.

- [ ] Configurable radar parameters via `PropertyGroup` (`properties/radar_settings.py`)
- [ ] Noise model with thermal noise and optional clutter
- [ ] Export data cube and RDM (`.npy` or HDF5) (`core/export.py`)
- [ ] Ground-truth export of object positions and velocities

Acceptance: a reproducible dataset of RDM and matching ground truth, loadable
outside Blender. The base is complete at this point.

### Milestone 5 - Antenna array and angle information

Goal: extend the model by the spatial dimension.

- [ ] Multi-channel array (ULA first) in configuration and signal model
- [ ] Compute phase differences between channels
- [ ] Angle estimation (`core/array_processing.py`)
- [ ] Angle-Doppler map (ADM) and Range-Angle map (RAM)

Acceptance: correct angle estimation for a target with a known angle of
arrival.

Rethinking required here: this is where the project stops being "Range-Doppler
only" and the radar data cube grows its third axis. Concretely:

- The beat cube gains a channel dimension: `(chirps, samples)` becomes
  `(channels, chirps, samples)`. `core/signal_model.py` must synthesize one
  beat signal per antenna, applying the per-channel phase that encodes the
  angle of arrival.
- An angle FFT (or beamforming) across the channel axis produces the third
  axis. The natural shape is to compute one RDM per channel and stack them,
  then transform across the stack — i.e. the array case literally *is* a stack
  of RDMs plus an angle transform.
- RDM, RAM and ADM then become three slices/projections of the same 3D cube,
  so the single-purpose `core/range_doppler.py` should be generalised (e.g. a
  `core/radar_cube.py` that owns the 3D transform, with `to_rdm` / `to_ram` /
  `to_adm` slicing helpers). The current 2D path stays valid as the
  single-channel special case.
- The UI and `utils/rdm.py` move from "compute *the* RDM" to "compute the cube,
  then pick a view to display".

### Milestone 6 - Detection and micro-Doppler

Goal: advanced evaluations that double as assessment tools for the later
attack.

- [ ] CFAR detection (`core/detection.py`), optionally with clustering
- [ ] Micro-Doppler spectrogram across multiple frames (`core/micro_doppler.py`)

Acceptance: extracted detections from the RDM and a recognizable micro-Doppler
pattern for a rotating or vibrating structure.

Cube note: CFAR is described here on the RDM, but once milestone 5 exists it
naturally runs on the full range × Doppler × angle cube, yielding detections
with an angle estimate instead of range/Doppler only. Keep the detector written
against a cube view so the same code serves the 2D (single-channel) and 3D
cases.

### Milestone 7 - Adversarial module and physical plausibilization

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

Cube note: the perturbation interface is phrased in the RD domain because that
is the only view that exists before milestone 5. With an array present the
adversarial target is more generally a perturbation of the full data cube (it
can specify an angle, not just range and Doppler); keep the interface able to
take a cube-domain target so the back-projection can place scatter centres in
angle as well.

### Milestone 8 - Evaluation and robustness analysis

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
