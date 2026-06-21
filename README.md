# Creature Lab

Creature Lab is a minimal, visual, Python-first creature simulation lab where humans or LLM agents create modular robot-creatures, run them in simple physical worlds, mutate their bodies/controllers, and save animated replays.

The project is currently in bootstrap/planning mode.

## Core idea

Creature Lab should feel like an agent-accessible physical zoo:

```text
Prompt or user command
  -> CreatureSpec + TaskSpec
  -> backend adapter, PyBullet first
  -> FrameState stream
  -> live viewer + EpisodeTrace
  -> replay, score, lineage, mutation loop
```

The durable rule:

> Every creature is JSON. Every task is JSON. Every episode is a trace. Every simulator is an adapter.

## Planned MVP stack

- Python 3.11+
- `uv`
- PyBullet for the first physics backend
- Viser for live browser-based 3D visualization
- Pydantic for schemas
- Typer for CLI
- Rich for terminal output
- Pytest and Ruff for quality checks

## Current documents

- [`docs/MVP_PLAN.md`](docs/MVP_PLAN.md) — comprehensive MVP plan and roadmap
- [`CLAUDE.md`](CLAUDE.md) — development instructions for Claude Code and future agentic coding sessions

## MVP goal

The first lovable demo should let a user run a command, open a local browser viewer, and watch a small modular creature try to crawl toward a target while the run is saved as replay data.

Available today:

```bash
# Core install (schemas + validate).
uv sync
uv run creature-lab doctor   # check which extras/providers are installed and that examples run
uv run creature-lab validate examples/tripod.json
uv run creature-lab validate examples/tripod.json --task examples/crawl_forward.json  # pre-flight

# Physics commands need the optional PyBullet backend.
uv sync --extra sim
uv run creature-lab run examples/tripod.json --task examples/crawl_forward.json
uv run creature-lab run examples/tripod.json --task examples/reach_target.json
uv run creature-lab evolve examples/tripod.json --task examples/crawl_forward.json --attempts 20 --seed 0
uv run creature-lab replay runs/<run-id>
```

`run` saves a self-describing, reproducible run under `runs/<id>/` — `creature.json`,
`task.json`, and `trace.json`. Every newly created trace carries a `meta` block recording the
schema/lab versions, backend (PyBullet) version, timestep, seed, content hashes of the creature
and task, a per-component score summary, and any validation warnings (older traces without
`meta` still load). `creature-lab inspect runs/<id>` prints a full diagnostic summary — hashes,
versions, score breakdown, distance/target/energy, fall status, damage events, contacts by part,
duration, and stored warnings. `evolve` hill-climbs from a seed creature and saves the best one,
and `replay` summarizes a saved trace without re-running physics. Before simulating, every
command cross-validates the creature against the task (e.g. a damage event must target a real
part) — `validate --task` runs the same pre-flight check without simulating. `creature-lab
doctor` reports which optional extras and LLM providers are configured and whether the bundled
example can run. Tasks score with a
weighted blend of forward distance, progress toward a target, energy use, and a fall penalty
(see `examples/*.json`). Joints take an optional `rest_orientation` quaternion so limbs can be
angled, not just axis-aligned; axes and quaternions are normalized on load.

```bash
# Live browser viewer needs the optional Viser dependency (plus the sim backend).
uv sync --extra sim --extra viz
uv run creature-lab demo                 # simulate the tripod and stream it live in a browser
uv run creature-lab view runs/<run-id>   # replay a saved run's recorded poses

# GIF/MP4 export needs the optional imageio dependencies (plus the sim renderer).
uv sync --extra sim --extra export
uv run creature-lab export runs/<run-id> --out tripod.gif   # or --out clip.mp4

# `ask` improves a creature toward a goal using validated design tools.
uv run creature-lab ask "make it crawl farther" examples/tripod.json \
    --task examples/crawl_forward.json --offline      # no provider needed
uv sync --extra llm                                   # for the LLM-driven mode
uv run creature-lab ask "make it crawl farther" examples/tripod.json \
    --task examples/crawl_forward.json                # asks an LLM via LiteLLM
```

`demo` is the headline "clone → one command → a weird little creature moves" experience: it
streams the simulation to the browser live, then saves the run. The viewer renders boxes,
spheres, true cylinders, and true (rounded-end) capsules; `view` auto-loads `task.json` from a
run directory to draw the target marker. `view` and `export` render recorded poses only — they
never re-run physics, matching the
project's "replays are portable, exact physics is backend-dependent" promise. Install
everything with `uv sync --all-extras`. For headless use (CI, screenshots), `demo --no-hold`
streams one pass, saves the run, and exits instead of serving until interrupted.

`ask` edits the creature only through validated tools (each returns a re-validated
`CreatureSpec`), keeps the best-scoring result, and saves an `AgentTrace` (`agent.json`).
`--offline` uses a deterministic no-provider policy; the default online mode asks an LLM via
LiteLLM (`llm` extra) and needs a configured provider/API key.

## Testing

```bash
uv sync --all-extras
uv run pytest          # unit + schema tests, plus end-to-end CLI scenarios
uv run ruff check .
uv run ruff format --check .
```

Tests come in two tiers: fast unit/schema tests, and end-to-end scenarios
(`tests/test_end_to_end.py`) that drive the CLI through full pipelines
(`run → replay → export`, every example task, live `demo`, and `evolve → export`)
and assert the on-disk artifacts. Tests that need an optional backend
(`pybullet`/`viser`/`imageio`) skip automatically when it is absent; CI installs
all extras so the whole pipeline runs.

## Development principle

Do not build a PyBullet project. Build a backend-agnostic creature lab where PyBullet is only the first backend.
