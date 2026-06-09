# CLAUDE.md

## Project mission

Creature Lab is a minimal, visual, Python-first creature simulation lab.

## Core rules

- Keep development minimal.
- Build backend-agnostic architecture.
- Treat JSON specs and traces as the source of truth.
- Keep PyBullet isolated as the first backend, not the whole project.
- Add tests for meaningful code changes.
- Do not add dependencies without a clear reason.
- Do not add Unity, Godot, Isaac, ROS, CUDA, databases, or web frameworks for MVP unless explicitly requested.
- Run available checks before finishing code changes.

## Preferred checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Expected boundaries

- `schema/` contains data models and must not import physics engines.
- `backends/` contains simulator adapters.
- `viewers/` consumes frame/trace data.
- `agents/` uses validated tools and must not access backend internals directly.
- `docs/` explains architecture and roadmap.

## MVP stack

Python 3.11+, uv, PyBullet, Viser, Pydantic, Typer, Rich, NumPy, imageio, LiteLLM, pytest, and ruff.
