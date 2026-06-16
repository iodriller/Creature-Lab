"""Episode trace persistence and run artifact layout.

Traces are saved as a single `trace.json` per run under `runs/`, which is
gitignored — see CLAUDE.md's rule against committing run folders.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from creature_lab.schema import EpisodeTrace

DEFAULT_RUNS_DIR = Path("runs")


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def save_trace(trace: EpisodeTrace, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    """Save a trace to `<runs_dir>/<run_id>/trace.json` and return that path."""
    run_dir = runs_dir / trace.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.json"
    trace_path.write_text(trace.model_dump_json(indent=2))
    return trace_path


def load_trace(path: Path) -> EpisodeTrace:
    """Load a trace from a `trace.json` file or a run directory containing one."""
    trace_path = path / "trace.json" if path.is_dir() else path
    return EpisodeTrace.model_validate(json.loads(trace_path.read_text()))
