# Build Editor

The build editor is a one-screen workbench, powered by Viser: configure a creature, run it, and
read its metrics without leaving the browser tab. It uses the same dependency as the replay
viewer, so there is no separate web app, server framework, or frontend build step.

## Layout

The panel follows the product loop instead of stacking every control in one list:

- **Project** and **History** sit at the top and are always available.
  - *Project*: creature name, Open/Save paths, and (in project mode) explicit Reload/Overwrite
    conflict actions.
  - *History*: **Undo**/**Redo**, **Reset to template**, named **snapshots** (Save/Restore), and
    the **Advanced mode** switch.
- An always-visible phase selector holds the workflow: **Design** → **Motion** → **Test**.
  - *Design*: pick a template, tune body proportions, browse the part hierarchy, and edit the
    selected part.
  - *Motion*: gait preset plus the selected joint motor's range/speed (and center offset, phase,
    and maximum torque in Advanced).
  - *Test*: choose a task, **Simulate**, scrub the **Playback**, read the **Result** (score +
    diagnosis), run a **Robustness** sweep, **Qualify** against a profile, and browse
    **Run History**.

**Basic vs. Advanced.** Basic mode (the default) shows only the ~handful of controls needed for a
first successful run. Flip **Advanced mode** in History to reveal exact dimensions, mass, colours,
raw motor center/phase/torque, terrain friction, and robustness jitter sliders.

**Undo is always available.** Every design change (body sliders, part/motor edits, gait, mirror,
add/delete limb, template swap, snapshot restore, applied diagnosis fix, restored run) is a single
undo step. Deleting a part that has children asks for confirmation first and lists exactly what
will be removed; reloading a project with unsaved edits also confirms. A status line note tracks
whether the current design has unsaved changes.

**First run.** Launching `build` fresh (no path, no `--project`) shows a **Get started** panel at
the top of the side panel — a *choose a creature × choose a goal* picker; Start applies the
choice, Skip leaves the default quadruped/crawl-forward. Reopening an existing creature or project
skips it. (It is an inline panel, not a pop-up modal: a Viser modal traps keyboard focus onto its
first control, which auto-opened the creature dropdown over the Start/Skip buttons and made the
first run unclickable — see `docs/KNOWN_ISSUES.md`.)

## Start

```bash
uv sync --inexact --extra sim --extra viz
uv run creature-lab build
```

Edit an existing creature (JSON or URDF, see [Import/Export](#importexport-urdf--mjcf)):

```bash
uv run creature-lab build mydude.json --out mydude.json
uv run creature-lab build mydude.urdf --out mydude.json
```

Use a different preset:

```bash
uv run creature-lab build --preset humanoid
uv run creature-lab build --preset worm
```

## Project Mode: Live-Synced Config Files

```bash
uv run creature-lab build --project outputs/mydude
```

Binds the editor to a directory holding `creature.json` + `task.json`:

- **First run**: if the files don't exist yet, they're created from `--preset`/`--task-preset`.
- **UI → disk**: every accepted edit (slider, part/motor change, gizmo drag, gait, mirror) writes
  straight back to `creature.json`/`task.json` — no separate Save step, and the files are always
  a valid, current snapshot you can `git diff`.
- **Disk → UI**: edit `creature.json` by hand, restore it with Git, or have another
  tool write it — the editor detects the change and shows a banner with a **Reload from disk**
  button. Autosave pauses during a conflict. Choose **Reload from disk** or explicitly
  **Overwrite disk with editor**; selecting a part or changing a run setting cannot destroy the
  external edit. File deletion and same-timestamp content changes are detected too.

Without `--project`, the editor works exactly as before: a one-shot **Open**/**Save** pair you
point at any path.

## Simulate: Async, With Progress and Cancel

The Test phase's **Run** section has a **Controller** dropdown — `curated` (default), `sinusoid`, `cpg`,
`target_seek`, or `posture` — before the Simulate button (a portable `controller.json` spec, see
`docs/CLI_REFERENCE.md`'s `controller` command, is a CLI-only `--controller` option; the
dropdown offers the stable named controllers). `curated` uses a measured packaged gait when the
body matches one—including the 12-DOF humanoid walker—posture for edited humanoids, or a safe
fallback. `target_seek` steers toward the current
task's target (heading-error steering, slowing and stopping near it); the status line shows an
error and disables Simulate if the current task has no target, and a warning if the current
creature has no motored joint ending in `l`/`r` (so it has nothing to steer with, and will just
walk straight). `posture` is a closed-loop PD balance controller (it senses the previous frame's
lean and corrects it, rather than blindly playing a waveform) — it holds a standing pose and
resists forward/backward pushes, but does not walk toward any objective and cannot correct
sideways tipping (no creature here has a side-to-side balance joint — see `docs/KNOWN_ISSUES.md`);
the status line shows a warning explaining this whenever it's selected.

When the selected task has a target, the Task panel exposes X/Y/Z/radius controls and the 3D
scene shows a draggable target gizmo. Both paths update the same validated `TaskSpec` and are
single undo steps.

Clicking **Simulate** starts the episode on a background thread instead of freezing the panel: a
progress bar and elapsed time appear above the phases, and **Cancel** stops it between physics steps
(the run is discarded, not saved). The **Robustness** sweep runs the same way, with progress
reported per trial, using whichever controller is currently selected. Only one job runs at a
time; Simulate and the sweep button are disabled while one is in flight.

## Playback: Separate From Simulation

A finished run loads into the **Playback** section instead of auto-replaying inline:
**Play/Pause**, a frame scrubber, **Step -1**/**Step +1**, and **Restart** (loop and speed live in
Advanced mode). Dragging the scrubber updates the 3D scene immediately, whether or not playback is
running.

## Result (After Simulate)

The **Result** section shows:

- Score, forward/net displacement, joint motion, duration, target progress, fall — as a compact
  scorecard headline, not a raw metrics dump.
- The same root-cause diagnosis `creature-lab diagnose` produces — matched failure patterns
  (e.g. `early_fall`, `lateral_drift`, `knee_hyperextension`), each tagged by severity
  (`[CRITICAL]`/`[WARNING]`/`[INFO]`) with a plain-language explanation and a suggested edit.
  Patterns with a safe, bounded fix (reduce motor amplitude, reverse the gait, apply a named gait
  preset, widen the stance) show an **Apply fix** button — applying is one undo step; re-simulate
  afterward to see the effect.
- Any validation warnings carried in the trace.

So the loop is: tweak a slider (or apply a suggested fix) → Simulate → read *why* it failed →
tweak again, all in one phase. **Back to Design** pauses playback, restores the editable pose, and
shows the body controls; it does not rely on browser-local tab state.

## Robustness Panel: Is This Gait Actually Robust?

A single simulated score is one seed's lucky-or-unlucky roll against one exact body. The
**Robustness** section of the Test phase (collapsed by default) re-simulates the current
creature/task under small seeded mass/friction perturbations and reports the score distribution:

- Basic mode offers a **Level**: Quick (5 trials), Standard (10), or Thorough (25). Advanced mode
  exposes raw **Trials**/**Mass jitter**/**Friction jitter** sliders instead.
- **Run robustness sweep** runs that many perturbed episodes (real physics each time, so Thorough
  takes a while — cancel it if needed) and leads with a plain-language verdict ("Robust",
  "Moderately robust", "Fragile") before the mean/std, min–max range, and fail rate.
- A wide spread or a high fail rate means the gait only works for the exact recorded body/terrain
  — not a robust result. This is the same engine behind the `creature-lab robustness <run>` CLI
  command (see `docs/CLI_REFERENCE.md`), run directly against the in-editor creature instead of a
  saved run.

## Qualify Panel: Pass/Fail Against a Profile

The **Qualify** section of the Test phase (collapsed by default) runs the same check
`creature-lab qualify` does — a baseline run, a robustness sweep, and (for `backend-portable`) a
cross-backend comparison — against the in-editor creature/task, without saving a run first:

- Pick a **Profile** (`basic-locomotion`, `target-reach`, `push-recovery`, `backend-portable`)
  and click **Run qualification**. Like Simulate/Robustness, it runs as a background job with
  progress and Cancel.
- The result shows **PASS**/**FAIL** per check, plus — when it fails — a named **primary
  blocker** and a **recommended next test**, so you know what to fix and how to re-check it.
  `target-reach`/`push-recovery` fail immediately on a task that doesn't have what the profile
  needs (a target, or a damage/impulse event), before running any physics.
- Only one job (Simulate, Robustness, or Qualify) runs at a time; the others are disabled while
  one is in flight.

## Run History

The Test phase's **Run History** section lists recent saved runs (creature, task, score, backend,
how long ago), newest first:

- **Restore design** loads that run's creature/task back into the editor as one undo step.
- **Replay** loads that run's trace into Playback without touching the current design — use it to
  look at an old result while still editing the current one.

## Import/Export: URDF & MJCF

The **Open**/**Save** path fields pick their format from the file extension:

| Extension | Open | Save |
| --- | --- | --- |
| `.json` | Loads a `CreatureSpec` | Writes a `CreatureSpec` |
| `.urdf` | Best-effort import (primitives + revolute/continuous/fixed joints; meshes, materials, and sensors are skipped and reported as a warning) | Full export |
| `.xml` / `.mjcf` | *(not supported)* | One-way MJCF export |

URDF is a full round trip; MJCF export is currently one-way (there is no MJCF importer yet), so a
`.xml`/`.mjcf` save can't be reopened in the editor — reopen the `.json` you built it from instead.

## What Else You Can Do

- Start from `quadruped`, `hexapod`, `worm`, or `humanoid` (or the onboarding picker's goal).
- Tune body parameters with sliders and see the static preview update.
- Browse the part hierarchy (friendly names, e.g. "Leg 1 (left)" instead of `leg_0l`) and select
  parts by clicking them in the scene, the tree, or the dropdown.
- Drag the selected-part transform gizmo to move its parent joint anchor.
- Edit part mass, shape, size, radius, length, and color (Advanced mode for mass/shape/colour).
- Add limbs, delete limbs (with a confirmation that lists affected child parts), and mirror.
- Tune the selected motor's range/speed, plus center angle, raw phase, and torque in Advanced mode.
- Choose task presets and adjust duration (and friction in Advanced mode).
- Undo/redo any change, save and restore named snapshots, or reset to the template defaults.
- Validate the creature/task pair before physics runs.

## Mental Model

The editor writes ordinary Creature Lab JSON (or URDF/MJCF, see above). After saving, every
existing command still works:

```bash
uv run creature-lab validate outputs/build_creature.json --task examples/crawl_forward.json
uv run creature-lab run outputs/build_creature.json --task examples/crawl_forward.json
uv run creature-lab evolve outputs/build_creature.json --task examples/crawl_forward.json
```

## Troubleshooting

For the browser-didn't-open / port-busy / dependency-install fixes shared with every viewer
command, see [Getting Started - Troubleshooting](GETTING_STARTED.md#troubleshooting). Editor-
specific issues:

- Simulate is disabled: read the Errors section in the status line and fix validation issues.
- "Files changed on disk" banner won't go away: click **Reload from disk**, or make any edit to
  autosave your in-editor version back over the external change.

## Testing The Editor (Why A Browser Is Required)

The editor is a Viser/React app, and its worst failures are **client-side** — a dropdown that
renders over its own buttons, a duplicate option value that crashes the page to blank, a stale
panel that contradicts the status line. The unit tests in `tests/test_editor_controls.py` drive a
*fake* GUI: they verify the Python that **builds** widgets, which catches wrong method names, bad
kwargs, and broken rebuild paths — but they cannot see how a real browser **renders** those
widgets, so a bug that only exists in the browser passes every unit test.

The fix for that blind spot is a real-browser smoke test:

```bash
uv sync --inexact --extra sim --extra viz --extra browser
python -m playwright install chromium     # one time
python scripts/browser_smoke.py           # add --headed to watch it
```

`scripts/browser_smoke.py` launches a real `creature-lab build` server, drives it with headless
Chromium through the exact first-run path (Humanoid → Move forward → Test → Simulate → Back to
Design), and
fails if any step is unusable or the browser logs a console/page error. It is intentionally **not**
in the default `pytest` suite (which must stay browser-free, per `AGENTS.md`). Run it whenever you
change the editor's layout, phases, onboarding, dropdowns, or result panel — every one of those is a
place a browser-only regression can hide. It found the onboarding-modal and duplicate-label bugs
that all the unit tests missed.
