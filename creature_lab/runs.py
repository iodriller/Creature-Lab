"""Episode trace persistence and run artifact layout.

Traces are saved as a single `trace.json` per run under `runs/`, which is
gitignored — see CLAUDE.md's rule against committing run folders.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from creature_lab.io_utils import atomic_write_text
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

DEFAULT_RUNS_DIR = Path("runs")
LATEST_RUN_FILE = "latest.txt"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _safe_run_id(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) or value in {".", ".."}:
        raise ValueError(f"unsafe run id: {value!r}")
    return value


def latest_run_id(runs_dir: Path = DEFAULT_RUNS_DIR) -> str:
    """Return the run id recorded by ``<runs_dir>/latest.txt``."""
    latest_path = runs_dir / LATEST_RUN_FILE
    if not latest_path.exists():
        raise FileNotFoundError(f"no latest run recorded at {latest_path}")
    run_id = latest_path.read_text(encoding="utf-8").strip()
    if not run_id:
        raise FileNotFoundError(f"latest run file is empty at {latest_path}")
    return _safe_run_id(run_id)


def write_latest_run(run_dir: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Record ``run_dir`` as the latest run and return the marker path."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    latest_path = runs_dir / LATEST_RUN_FILE
    atomic_write_text(latest_path, f"{_safe_run_id(run_dir.name)}\n")
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
    run_dir = runs_dir / _safe_run_id(trace.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.json"
    atomic_write_text(trace_path, trace.model_dump_json(indent=2))
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
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_dir = runs_dir / _safe_run_id(trace.run_id)
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    stage = Path(tempfile.mkdtemp(prefix=f".{trace.run_id}.", dir=runs_dir))
    saved_trace = trace
    try:
        atomic_write_text(stage / "creature.json", creature.model_dump_json(indent=2))
        if task is not None:
            atomic_write_text(stage / "task.json", task.model_dump_json(indent=2))

        if trace.meta is not None and trace.meta.controller is not None:
            from creature_lab.exporting import resolve_controller_bundle, write_controller_snapshot
            from creature_lab.hashing import spec_hash

            try:
                bundle = resolve_controller_bundle(creature, trace.meta.controller)
                controller_spec, policy_hash = write_controller_snapshot(stage, bundle)
                warnings = list(trace.meta.warnings)
                if not bundle.exact:
                    warnings.append(f"controller snapshot: {bundle.note}")
                meta = trace.meta.model_copy(
                    update={
                        "controller_hash": spec_hash(controller_spec),
                        "controller_artifact": "controller.json",
                        "policy_hash": policy_hash,
                        "warnings": warnings,
                    }
                )
                saved_trace = trace.model_copy(update={"meta": meta})
            except (OSError, ValueError) as exc:
                meta = trace.meta.model_copy(
                    update={
                        "warnings": [*trace.meta.warnings, f"controller snapshot failed: {exc}"]
                    }
                )
                saved_trace = trace.model_copy(update={"meta": meta})

        atomic_write_text(stage / "trace.json", saved_trace.model_dump_json(indent=2))
        os.replace(stage, run_dir)
        write_latest_run(run_dir, runs_dir=runs_dir)
        return run_dir
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def load_trace(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> EpisodeTrace:
    """Load a trace from a `trace.json` file or a run directory containing one."""
    return EpisodeTrace.model_validate(
        json.loads(resolve_trace_path(path, runs_dir).read_text(encoding="utf-8"))
    )


def load_run(
    path: Path, runs_dir: Path = DEFAULT_RUNS_DIR
) -> tuple[CreatureSpec, TaskSpec | None, EpisodeTrace]:
    """Load (creature, task?, trace) from a run directory."""
    resolved = resolve_run_path(path, runs_dir=runs_dir)
    run_dir = resolved if resolved.is_dir() else resolved.parent
    creature = CreatureSpec.model_validate_json(
        (run_dir / "creature.json").read_text(encoding="utf-8")
    )
    task_path = run_dir / "task.json"
    task = (
        TaskSpec.model_validate_json(task_path.read_text(encoding="utf-8"))
        if task_path.exists()
        else None
    )
    trace = load_trace(run_dir, runs_dir=runs_dir)
    if trace.creature_name != creature.name:
        raise ValueError(
            f"run creature mismatch: trace names {trace.creature_name!r}, "
            f"creature.json names {creature.name!r}"
        )
    if task is not None and trace.task_name != task.name:
        raise ValueError(
            f"run task mismatch: trace names {trace.task_name!r}, task.json names {task.name!r}"
        )
    if trace.meta is not None:
        from creature_lab.hashing import spec_hash

        if trace.meta.creature_hash is not None and trace.meta.creature_hash != spec_hash(creature):
            raise ValueError("creature.json does not match the hash recorded in trace metadata")
        if (
            task is not None
            and trace.meta.task_hash is not None
            and trace.meta.task_hash != spec_hash(task)
        ):
            raise ValueError("task.json does not match the hash recorded in trace metadata")
    return creature, task, trace


@dataclass(frozen=True)
class RunSummary:
    """One row of run history: enough to list, restore, or replay without loading
    the full trace."""

    run_dir: Path
    run_id: str
    creature_name: str
    task_name: str
    backend: str
    score: float
    saved_at: float  # trace.json mtime, as a Unix timestamp


def list_recent_runs(runs_dir: Path = DEFAULT_RUNS_DIR, *, limit: int = 10) -> list[RunSummary]:
    """Most-recent-first summaries of saved runs, for an editor's run-history panel.

    Reads each ``trace.json``'s top-level scalar fields directly (``json.loads`` +
    dict access) rather than through ``EpisodeTrace.model_validate`` - a run history
    panel only ever needs 5 scalars per run, and full pydantic validation would mean
    constructing a ``FrameState``/``PartPose``/``ContactSpec`` object per recorded
    frame (often hundreds) just to list a handful of rows.

    Skips any run directory missing ``trace.json`` (created via ``save_trace`` alone,
    without ``save_run``) or one that fails to parse - a corrupt/partial run should
    not make the whole history unusable.
    """
    if not runs_dir.exists():
        return []
    summaries: list[RunSummary] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        trace_path = run_dir / "trace.json"
        if not trace_path.exists():
            continue
        try:
            data = json.loads(trace_path.read_text(encoding="utf-8"))
            summaries.append(
                RunSummary(
                    run_dir=run_dir,
                    run_id=data["run_id"],
                    creature_name=data["creature_name"],
                    task_name=data["task_name"],
                    backend=data["backend"],
                    score=data["score"],
                    saved_at=trace_path.stat().st_mtime,
                )
            )
        except Exception:
            continue
    summaries.sort(key=lambda s: s.saved_at, reverse=True)
    return summaries[:limit]
