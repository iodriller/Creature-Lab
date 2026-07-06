"""Episode trace persistence and run artifact layout.

Traces are saved as a single `trace.json` per run under `runs/`, which is
gitignored — see CLAUDE.md's rule against committing run folders.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

DEFAULT_RUNS_DIR = Path("runs")
LATEST_RUN_FILE = "latest.txt"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def latest_run_id(runs_dir: Path = DEFAULT_RUNS_DIR) -> str:
    """Return the run id recorded by ``<runs_dir>/latest.txt``."""
    latest_path = runs_dir / LATEST_RUN_FILE
    if not latest_path.exists():
        raise FileNotFoundError(f"no latest run recorded at {latest_path}")
    run_id = latest_path.read_text().strip()
    if not run_id:
        raise FileNotFoundError(f"latest run file is empty at {latest_path}")
    return run_id


def write_latest_run(run_dir: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Record ``run_dir`` as the latest run and return the marker path."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    latest_path = runs_dir / LATEST_RUN_FILE
    latest_path.write_text(f"{run_dir.name}\n")
    return latest_path


def resolve_run_path(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Resolve ``latest`` or a bare run id to a run directory when possible."""
    if path == Path("latest"):
        return runs_dir / latest_run_id(runs_dir)
    if path.exists():
        return path
    if len(path.parts) == 1:
        candidate = runs_dir / path
        if candidate.exists():
            return candidate
    return path


def resolve_trace_path(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Return the `trace.json` path for a run directory, ``latest``, or bare run id."""
    resolved = resolve_run_path(path, runs_dir=runs_dir)
    return resolved / "trace.json" if resolved.is_dir() else resolved


def save_trace(trace: EpisodeTrace, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Save a trace to `<runs_dir>/<run_id>/trace.json` and return that path."""
    run_dir = runs_dir / trace.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.json"
    trace_path.write_text(trace.model_dump_json(indent=2))
    write_latest_run(run_dir, runs_dir=runs_dir)
    return trace_path


def save_run(
    creature: CreatureSpec,
    trace: EpisodeTrace,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    *,
    task: TaskSpec | None = None,
) -> Path:
    """Save `creature.json` (+ optional `task.json`) + `trace.json` under the run directory.

    Writing the creature and task alongside the trace makes a run self-describing and
    reproducible: the viewer can render shapes and the target from just the run directory.
    """
    trace_path = save_trace(trace, runs_dir=runs_dir)
    run_dir = trace_path.parent
    (run_dir / "creature.json").write_text(creature.model_dump_json(indent=2))
    if task is not None:
        (run_dir / "task.json").write_text(task.model_dump_json(indent=2))
    return run_dir


def load_trace(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> EpisodeTrace:
    """Load a trace from a `trace.json` file or a run directory containing one."""
    return EpisodeTrace.model_validate(json.loads(resolve_trace_path(path, runs_dir).read_text()))


def load_run(
    path: Path, runs_dir: Path = DEFAULT_RUNS_DIR
) -> tuple[CreatureSpec, TaskSpec | None, EpisodeTrace]:
    """Load (creature, task?, trace) from a run directory."""
    resolved = resolve_run_path(path, runs_dir=runs_dir)
    run_dir = resolved if resolved.is_dir() else resolved.parent
    creature = CreatureSpec.model_validate_json((run_dir / "creature.json").read_text())
    task_path = run_dir / "task.json"
    task = TaskSpec.model_validate_json(task_path.read_text()) if task_path.exists() else None
    trace = load_trace(run_dir, runs_dir=runs_dir)
    return creature, task, trace
