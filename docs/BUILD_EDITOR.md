# Build Editor

The build editor is a one-screen workbench, powered by Viser: configure a creature, run it, and
read its metrics without leaving the browser tab. It uses the same dependency as the replay
viewer, so there is no separate web app, server framework, or frontend build step.

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
- **Disk → UI**: edit `creature.json` by hand, restore it with `git checkout`, or have another
  tool write it — the editor detects the change and shows a banner with a **Reload from disk**
  button. It never silently overwrites your in-editor work; you choose Reload or keep editing
  (which then autosaves your version back over the external change).

Without `--project`, the editor works exactly as before: a one-shot **Open**/**Save** pair you
point at any path.

## Metrics (After Simulate)

Clicking **Simulate** now populates a **Metrics** folder in the same panel:

- Score, its breakdown, forward/net displacement, joint motion, duration, target progress, fall.
- The same root-cause diagnosis `creature-lab diagnose` produces — matched failure patterns
  (e.g. `early_fall`, `lateral_drift`, `knee_hyperextension`) each with a plain-language
  explanation and a concrete suggested edit.
- Any validation warnings carried in the trace.

So the loop is: tweak a slider → Simulate → read *why* it failed → tweak again, all in one tab.

## Robustness Panel: Is This Gait Actually Robust?

A single simulated score is one seed's lucky-or-unlucky roll against one exact body. The
**Robustness** folder (collapsed by default) re-simulates the current creature/task under small
seeded mass/friction perturbations and reports the score distribution:

- **Trials**, **Mass jitter**, **Friction jitter** sliders control the sweep.
- **Run robustness sweep** runs that many perturbed episodes (real physics each time, so a large
  trial count takes a while) and shows mean/std, min–max range, and fail rate.
- A wide spread or a high fail rate means the gait only works for the exact recorded body/terrain
  — not a robust result. This is the same engine behind the `creature-lab robustness <run>` CLI
  command (see `docs/CLI_REFERENCE.md`), run directly against the in-editor creature instead of a
  saved run.

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

- Start from `quadruped`, `hexapod`, `worm`, or `humanoid`.
- Tune body parameters with sliders and see the static preview update.
- Select parts by clicking them in the scene or choosing them in the panel.
- Drag the selected-part transform gizmo to move its parent joint anchor.
- Edit part mass, shape, size, radius, length, and color.
- Add or delete limbs.
- Tune individual motor amplitude, frequency, and phase.
- Choose task presets and adjust duration/friction.
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

- Browser did not open: copy the printed `http://localhost:<port>` URL into your browser.
- Port is busy: rerun with `--port 8090`.
- Simulate is disabled: read the Errors section in the Run folder and fix validation issues.
- Physics dependency is missing: run `uv sync --inexact --extra sim --extra viz`.
- "Files changed on disk" banner won't go away: click **Reload from disk**, or make any edit to
  autosave your in-editor version back over the external change.
