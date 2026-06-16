"""Episode trace persistence and run artifact layout.

Traces are saved as a single `trace.json` per run under `runs/`, which is
gitignored — see CLAUDE.md's rule against committing run folders.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from creature_lab.schema import CreatureSpec, EpisodeTrace

DEFAULT_RUNS_DIR = Path("runs")


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def resolve_trace_path(path: Path) -> Path:
    """Return the `trace.json` path for a run directory, or `path` unchanged."""
    return path / "trace.json" if path.is_dir() else path


def save_trace(trace: EpisodeTrace, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Save a trace to `<runs_dir>/<run_id>/trace.json` and return that path."""
    run_dir = runs_dir / trace.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.json"
    trace_path.write_text(trace.model_dump_json(indent=2))
    return trace_path


def save_run(
    creature: CreatureSpec, trace: EpisodeTrace, runs_dir: Path = DEFAULT_RUNS_DIR
) -> Path:
    """Save `creature.json` + `trace.json` under the run directory and return it.

    Writing the creature alongside the trace makes a run self-describing, so the
    viewer can render shapes from just the run directory.
    """
    trace_path = save_trace(trace, runs_dir=runs_dir)
    run_dir = trace_path.parent
    (run_dir / "creature.json").write_text(creature.model_dump_json(indent=2))
    return run_dir


def load_trace(path: Path) -> EpisodeTrace:
    """Load a trace from a `trace.json` file or a run directory containing one."""
    return EpisodeTrace.model_validate(json.loads(resolve_trace_path(path).read_text()))
