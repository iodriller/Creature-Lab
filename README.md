# Creature Lab

[![CI](https://github.com/iodriller/Creature-Lab/actions/workflows/ci.yml/badge.svg)](https://github.com/iodriller/Creature-Lab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)

Creature Lab is a tiny local lab for designing, running, diagnosing, and improving
modular robot-creatures from JSON.

![Creature Lab demo](docs/assets/demo.gif)

Run a creature, watch it move, score the episode, diagnose failures, evolve better
versions, and replay or export the result.

## Start Here

From a fresh checkout, run one launcher. It installs the starter extras, checks the environment,
and opens the interactive **build editor** in your browser — configure a creature first, then
run it, instead of jumping straight into physics.

Windows PowerShell:

```powershell
.\scripts\start.ps1
```

Portable Python:

```bash
python scripts/start.py
```

What should happen:

- A terminal shows setup progress and an editor URL such as `http://localhost:8080`.
- Your browser opens to the build editor: a template picker, live 3D preview, body/part/motor
  sliders, and a **Simulate** button.
- Pick a preset, tune it, click Simulate to run it through the existing physics pipeline, read
  its score/diagnosis and a robustness sweep in the same panel, then Save to write a normal
  `CreatureSpec` JSON (or a `.urdf`).

Start from a different preset (`quadruped`, `hexapod`, `worm`, `humanoid`):

```bash
python scripts/start.py --creature humanoid
```

Prefer the old read-only playback demo instead of the setup screen?

```bash
python scripts/start.py --mode demo
```

## Manual Quickstart

```bash
uv sync --inexact --extra sim --extra viz
uv run creature-lab build
```

`build` opens the browser setup screen described above. For the plain playback demo instead:

```bash
uv run creature-lab demo --open-browser
```

`demo` runs the built-in quadruped in the browser viewer and keeps it looping. Add `--no-hold`
when you want it to save a trace and exit after one pass.

If launch fails, start with:

```bash
python scripts/start.py --dry-run
uv run creature-lab doctor
```

If the browser does not open automatically, copy the printed `http://localhost:<port>` URL into
your browser. If port `8080` is busy, the launcher picks the next open port unless you explicitly
set `--port`.

## Next Steps

Browse the built-in Creature Zoo:

```bash
uv run creature-lab zoo list
uv run creature-lab zoo run quadruped
uv run creature-lab report latest
```

Create or tune a CreatureSpec without hand-editing JSON:

```bash
uv run creature-lab build --preset humanoid
uv run creature-lab build outputs/build_creature.json --out outputs/build_creature.json
```

Improve a creature with the local evolution loop:

```bash
uv run creature-lab evolve examples/quadruped.json --task examples/crawl_forward.json --attempts 20
```

Replay or export a saved run:

```bash
uv run creature-lab view runs/<run-id>
uv run creature-lab view latest
uv sync --extra sim --extra export
uv run creature-lab export latest --gif demo.gif
```

## What You Get

- A curated Creature Zoo: quadruped, worm, hexapod, tripod, damaged quadruped, and humanoids.
- A browser build editor for presets, body sliders, part edits, motor tuning, validation,
  simulation, live metrics/diagnosis, a robustness sweep, and URDF import/export — all in one
  screen, with optional live file-sync to a project directory (`--project`).
- Portable JSON specs for creatures and tasks.
- Physics runs saved as replayable traces with metadata, hashes, scores, contacts, and warnings.
- Local improvement loops: `evolve` for search and `ask --offline` for validated design edits.
- Replay, diagnosis, GIF/MP4 export, and advanced backend/export bridges.

## Core Workflow

```text
CreatureSpec + TaskSpec
  -> run a physics episode
  -> save an EpisodeTrace
  -> inspect or diagnose the result
  -> evolve or edit the creature
  -> replay/export the best run
```

The durable rule:

> Every creature is JSON. Every task is JSON. Every episode is a trace. Every simulator is an adapter.

PyBullet is the default simulator. Specs, tasks, traces, and replays are portable; exact
physics behavior is backend-dependent.

## Docs

- [Documentation Home](docs/README.md) - where to start and how the docs fit together.
- [Getting Started](docs/GETTING_STARTED.md) - the shortest path from clone to first run.
- [Build Editor](docs/BUILD_EDITOR.md) - browser setup screen for creating CreatureSpec JSON.
- [Concepts](docs/CONCEPTS.md) - creatures, tasks, traces, backends, and the improve loop.
- [Creature Spec](docs/CREATURE_SPEC.md) - the JSON shape for body graphs and motors.
- [Task Spec](docs/TASK_SPEC.md) - worlds, rewards, targets, damage, and push events.
- [Run Artifacts](docs/RUN_ARTIFACTS.md) - what is saved under `runs/<run-id>/`.
- [Zoo](docs/ZOO.md) - bundled creatures, tasks, baselines, and challenge pack.
- [CLI Reference](docs/CLI_REFERENCE.md) - commands grouped by workflow.
- [Roadmap](docs/ROADMAP.md) - MVP status and future product priorities.
- [Improvement Plan (2026 H2)](docs/IMPROVEMENT_PLAN_2026.md) - report upgrade and next feature phases.
- [Changelog](CHANGELOG.md) - notable changes by release.
- [Known Issues](docs/KNOWN_ISSUES.md) - latent gaps and deliberate limitations found in review.
- [Archived plans](docs/archive/) - historical planning and audit notes.

## Advanced

These features are available, but they are not needed for the first run:

| Need | Command or API |
| --- | --- |
| Build/edit a creature visually | `uv run creature-lab build --preset humanoid` |
| Pre-flight validation | `uv run creature-lab validate examples/tripod.json --task examples/crawl_forward.json` |
| Diagnose why a run failed | `uv run creature-lab diagnose runs/<run-id>` |
| Write a run report | `uv run creature-lab report latest --out report.md` / `--html report.html` |
| Benchmark the zoo | `uv run creature-lab bench --zoo --task crawl_forward --attempts 3 --out runs/bench.json` |
| Export JSON schemas | `uv run creature-lab schema creature --out docs/schemas/creature.schema.json` |
| Build local zoo gallery cards | `uv run creature-lab gallery build --zoo --out docs/assets/zoo --no-media` |
| Ask for validated design edits | `uv run creature-lab ask "make it crawl farther" examples/tripod.json --task examples/crawl_forward.json --offline` |
| Generate new creature specs | `uv run creature-lab scaffold worm --out worm.json --segments 6` |
| Compare or plot runs | `uv run creature-lab compare runs/<a> runs/<b> --html diff.html` / `uv run creature-lab plot runs/<run-id>` |
| Check robustness / cross-backend gap | `uv run creature-lab robustness runs/<id> --trials 10` / `uv run creature-lab sim2sim runs/<id>` |
| Visualize a MAP-Elites archive | `uv run creature-lab archive show runs/<id> --html archive.html` |
| MuJoCo backend | `uv sync --extra mujoco`, then `uv run creature-lab run ... --backend mujoco` |
| URDF/MJCF bridge | `export-urdf`, `export-mjcf`, and `import-urdf` |
| Gymnasium-style control | `creature_lab.env.CreatureEnv` |
| Online LLM mode | `uv sync --extra llm`, then run `ask` without `--offline` |

Install everything with:

```bash
uv sync --all-extras
```

## Testing

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

CI runs Ruff, Pytest, `doctor`, and `validate --task` with the test-exercised extras installed.

For a local smoke test that mirrors the first-run path:

```bash
python scripts/start.py --dry-run
uv run creature-lab doctor
uv run creature-lab validate examples/tripod.json --task examples/crawl_forward.json
```

## Development Principle

Do not build a PyBullet project. Build a backend-agnostic creature lab where PyBullet is only
the first backend.
