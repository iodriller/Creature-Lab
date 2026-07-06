"""Tests for episode trace persistence (creature_lab.runs)."""

from pathlib import Path

import pytest

from creature_lab.runs import (
    latest_run_id,
    load_run,
    load_trace,
    new_run_id,
    resolve_run_path,
    resolve_trace_path,
    save_run,
    save_trace,
)
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

_CREATURE = {
    "name": "tripod",
    "parts": [{"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0}],
}
_TASK = {"name": "crawl_forward", "duration": 1.0}


def _trace(run_id: str) -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": run_id,
            "creature_name": "tripod",
            "task_name": "crawl_forward",
            "backend": "pybullet",
            "score": 1.25,
            "frames": [{"t": 0.0, "parts": {"torso": {"position": [0, 0, 0]}}, "score": 1.25}],
        }
    )


def test_save_and_load_round_trip(tmp_path):
    trace = _trace(new_run_id())
    saved_path = save_trace(trace, runs_dir=tmp_path)

    assert saved_path == tmp_path / trace.run_id / "trace.json"
    assert load_trace(saved_path) == trace
    assert latest_run_id(tmp_path) == trace.run_id


def test_load_trace_from_run_directory(tmp_path):
    trace = _trace(new_run_id())
    save_trace(trace, runs_dir=tmp_path)

    assert load_trace(tmp_path / trace.run_id) == trace


def test_latest_alias_resolves_to_most_recent_run(tmp_path):
    first = _trace("first")
    second = _trace("second")
    save_trace(first, runs_dir=tmp_path)
    save_trace(second, runs_dir=tmp_path)

    assert latest_run_id(tmp_path) == "second"
    assert resolve_run_path(Path("latest"), tmp_path) == tmp_path / "second"
    assert resolve_trace_path(Path("latest"), tmp_path) == tmp_path / "second" / "trace.json"
    assert load_trace(Path("latest"), runs_dir=tmp_path) == second


def test_latest_alias_reports_missing_marker(tmp_path):
    with pytest.raises(FileNotFoundError, match="no latest run"):
        latest_run_id(tmp_path)


def test_run_ids_are_unique():
    assert new_run_id() != new_run_id()


def test_save_run_writes_task_json(tmp_path):
    creature = CreatureSpec.model_validate(_CREATURE)
    task = TaskSpec.model_validate(_TASK)
    trace = _trace(new_run_id())

    run_dir = save_run(creature, trace, runs_dir=tmp_path, task=task)

    assert (run_dir / "creature.json").exists()
    assert (run_dir / "task.json").exists()
    assert (run_dir / "trace.json").exists()


def test_load_run_round_trips_all_three(tmp_path):
    creature = CreatureSpec.model_validate(_CREATURE)
    task = TaskSpec.model_validate(_TASK)
    trace = _trace(new_run_id())
    run_dir = save_run(creature, trace, runs_dir=tmp_path, task=task)

    loaded_creature, loaded_task, loaded_trace = load_run(run_dir)
    assert loaded_creature == creature
    assert loaded_task == task
    assert loaded_trace == trace


def test_load_run_task_is_none_when_absent(tmp_path):
    creature = CreatureSpec.model_validate(_CREATURE)
    trace = _trace(new_run_id())
    run_dir = save_run(creature, trace, runs_dir=tmp_path)  # no task

    _, loaded_task, _ = load_run(run_dir)
    assert loaded_task is None
