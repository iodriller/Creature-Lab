# Creature Lab

[![CI](https://github.com/iodriller/Creature-Lab/actions/workflows/ci.yml/badge.svg)](https://github.com/iodriller/Creature-Lab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)

**Creature Lab is a failure-first, local workbench for robot morphology experiments.** Design a
body, run it in physics, determine whether a failure came from the body, controller, task,
fragility, or simulator, and hand someone the exact experiment that proves it. Everything is
inspectable JSON and runs offline on an ordinary laptop.

![Creature Lab demo](docs/assets/demo.gif)

The whole tool is one loop:

```text
Design → Run → Autopsy → Improve → Verify → Share
```

The distinctive unit is a **minimum reproducible robot experiment**: creature, task, controller,
trace, hashes, and runtime provenance in a verified pack. Creature Lab is an educational and
early-prototyping tool—not hardware qualification, a cloud service, or a GPU-scale RL platform.

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

For the shortest proof that the humanoid is doing something real, choose **Humanoid → Move
forward → Start**, select **Test**, and press **Simulate**. The curated setup advances about
0.4 m in five seconds on PyBullet without falling. Press **Back to Design** to restore the
editable pose and change the body or gait. The same measured setup is available directly:

```bash
uv run creature-lab zoo run humanoid_12dof --task walk --controller optimized
```

This is a slow, open-loop stepping gait, not a production humanoid controller. It is intentionally
useful as an inspectable starting experiment: change the foot size, leg proportions, gait center,
phase, or motor torque, then use the result and diagnosis to see what broke.

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
uv run creature-lab zoo check-showcases
uv run creature-lab report latest
```

The Zoo uses its measured **curated** controller by default. Use `--controller sinusoid` when you
specifically want the raw teaching baseline.

Ask why an experiment failed and get an HTML/Markdown/JSON report plus a verified pack:

```bash
uv run creature-lab autopsy examples/quadruped.json \
  --task examples/crawl_forward.json --controller sinusoid
uv run creature-lab failure list
uv run creature-lab failure export frozen-gait --out outputs/frozen-gait
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
- Physics runs saved with exact creature/task/controller snapshots, hashes, scores, contacts,
  warnings, and optional learned-policy payloads.
- Experiment Autopsy: controller counterfactuals, task-aware perturbation trials, optional
  backend comparison, cause attribution, and a recommended next experiment.
- A Failure Zoo of intentionally broken experiments for teaching and diagnostic regression.
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

> Every creature, task, and controller is JSON. Every episode is a trace. Every simulator is an adapter.

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
- [Failure Lab](docs/FAILURE_LAB.md) - hypothesis-driven lessons using intentional failures.
- [CLI Reference](docs/CLI_REFERENCE.md) - commands grouped by workflow.
- [Grand Plan](docs/GRAND_PLAN.md) - the single active roadmap: what Creature Lab is and where it's going.
- [Roadmap](docs/ROADMAP.md) - the durable guard rails (points to the Grand Plan).
- [Changelog](CHANGELOG.md) - notable changes by release.
- [Known Issues](docs/KNOWN_ISSUES.md) - latent gaps and deliberate limitations found in review.
- [Releasing](docs/RELEASING.md) - clean-install checks and explicit public-publication gates.
- [Archived plans](docs/archive/) - historical planning and audit notes.

## Advanced

These features are available, but they are not needed for the first run:

| Need | Command or API |
| --- | --- |
| Build/edit a creature visually | `uv run creature-lab build --preset humanoid` |
| Pre-flight validation | `uv run creature-lab validate examples/tripod.json --task examples/crawl_forward.json` |
| Diagnose why a run failed | `uv run creature-lab diagnose runs/<run-id>` |
| Autopsy a complete experiment | `uv run creature-lab autopsy creature.json --task task.json --controller controller.json` |
| Learn from intentional failures | `uv run creature-lab failure list` / `failure export frozen-gait --out outputs/frozen` |
| Write a run report | `uv run creature-lab report latest --out report.md` / `--html report.html` |
| Benchmark the zoo | `uv run creature-lab bench --zoo --task crawl_forward --attempts 3 --out runs/bench.json` |
| Export JSON schemas | `uv run creature-lab schema creature --out docs/schemas/creature.schema.json` |
| Build local zoo gallery cards | `uv run creature-lab gallery build --zoo --out docs/assets/zoo --no-media` |
| Ask for validated design edits | `uv run creature-lab ask "make it crawl farther" examples/tripod.json --task examples/crawl_forward.json --offline` |
| Generate new creature specs | `uv run creature-lab scaffold worm --out worm.json --segments 6` |
| Compare or plot runs | `uv run creature-lab compare runs/<a> runs/<b> --html diff.html` / `uv run creature-lab plot runs/<run-id>` |
| Check robustness / cross-backend gap | `uv run creature-lab robustness runs/<id> --trials 10` / `uv run creature-lab sim2sim runs/<id>` |
| Steer toward a target | `uv run creature-lab run creature.json --task examples/reach_target.json --controller target_seek` |
| Run the measured humanoid walker | `uv run creature-lab zoo run humanoid_12dof --task walk --controller optimized` |
| Combine success/robustness/portability into one pass-fail | `uv run creature-lab qualify creature.json --task task.json --profile basic-locomotion` |
| Author/check a portable controller.json | `uv run creature-lab controller scaffold cpg --out gait.json` |
| Optimize a creature's gait (2-3x typical) | `uv run creature-lab optimize creature.json --task task.json --out gait.json` |
| Train a policy with reinforcement learning (PPO) | `uv sync --extra rl`, then `uv run creature-lab train creature.json --task task.json --out outputs/trained` |
| Bundle and verify a run | `uv run creature-lab export-pack latest --out outputs/my_pack` / `verify-pack outputs/my_pack` |
| Visualize a MAP-Elites archive | `uv run creature-lab archive show runs/<id> --html archive.html` |
| MuJoCo backend | `uv sync --extra mujoco`, then `uv run creature-lab run ... --backend mujoco` |
| URDF/MJCF bridge | `export-urdf`, `export-mjcf`, and `import-urdf` |
| Gymnasium-style control | `creature_lab.env.CreatureEnv` (hand-written policies) or `creature_lab.rl.gym_env.CreatureGymEnv` (a real `gymnasium.Env`, for Stable-Baselines3/PPO) |
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
uv run creature-lab zoo check-showcases
```

CI runs Ruff, Pytest, packaging, showcase acceptance, a real browser journey, and platform jobs on
Linux, Windows, and macOS. Browser tests remain separate from the default offline Pytest suite.

For a local smoke test that mirrors the first-run path:

```bash
python scripts/start.py --dry-run
uv run creature-lab doctor
uv run creature-lab validate examples/tripod.json --task examples/crawl_forward.json
```

## Development Principle

Do not build a PyBullet project. Build a backend-agnostic creature lab where PyBullet is only
the first backend.
