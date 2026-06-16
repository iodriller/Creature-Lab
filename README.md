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
uv run creature-lab validate examples/tripod.json

# Physics commands need the optional PyBullet backend.
uv sync --extra sim
uv run creature-lab run examples/tripod.json --task examples/crawl_forward.json
uv run creature-lab evolve examples/tripod.json --task examples/crawl_forward.json --attempts 20 --seed 0
uv run creature-lab replay runs/<run-id>
```

`run` saves a self-describing run (`creature.json` + `trace.json`) under `runs/`, `evolve`
hill-climbs from a seed creature and saves the best one, and `replay` summarizes a saved
trace without re-running physics.

```bash
# Browser replay viewer needs the optional Viser dependency.
uv sync --extra viz
uv run creature-lab view runs/<run-id>   # animates the recorded poses in a browser

# GIF/MP4 export needs the optional imageio dependencies (plus the sim renderer).
uv sync --extra sim --extra export
uv run creature-lab export runs/<run-id> --out tripod.gif   # or --out clip.mp4
```

`view` and `export` render recorded poses only — they never re-run physics, matching the
project's "replays are portable, exact physics is backend-dependent" promise. Install
everything with `uv sync --all-extras`.

## Development principle

Do not build a PyBullet project. Build a backend-agnostic creature lab where PyBullet is only the first backend.
