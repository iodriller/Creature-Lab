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
uv sync
uv run creature-lab validate examples/tripod.json
```

Planned command shape (aspirational until their backends land):

```bash
uv run creature-lab demo
uv run creature-lab run examples/tripod.json --task crawl
uv run creature-lab replay runs/latest
```

## Development principle

Do not build a PyBullet project. Build a backend-agnostic creature lab where PyBullet is only the first backend.
