"""Tests for episode trace persistence (creature_lab.runs)."""

import json
from pathlib import Path

import pytest

from creature_lab.runs import (
    latest_run_id,
    list_recent_runs,
    load_run,
    load_trace,
    new_run_id,
    resolve_run_path,
    resolve_trace_path,
    save_run,
    save_trace,
)
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec, TraceMeta

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


def test_list_recent_runs_empty_when_dir_missing(tmp_path):
    assert list_recent_runs(tmp_path / "does_not_exist") == []


def test_list_recent_runs_returns_summaries_newest_first(tmp_path):
    import os

    creature = CreatureSpec.model_validate(_CREATURE)
    first_dir = save_run(creature, _trace("run_a"), runs_dir=tmp_path)
    second_dir = save_run(creature, _trace("run_b"), runs_dir=tmp_path)
    # Ensure a real mtime gap on filesystems with coarse resolution.
    older = (first_dir / "trace.json").stat().st_mtime - 5
    os.utime(first_dir / "trace.json", (older, older))

    summaries = list_recent_runs(tmp_path)

    assert [s.run_id for s in summaries] == ["run_b", "run_a"]
    assert summaries[0].creature_name == "tripod"
    assert summaries[0].run_dir == second_dir


def test_list_recent_runs_respects_limit(tmp_path):
    creature = CreatureSpec.model_validate(_CREATURE)
    for i in range(5):
        save_run(creature, _trace(f"run_{i}"), runs_dir=tmp_path)

    assert len(list_recent_runs(tmp_path, limit=3)) == 3


def test_list_recent_runs_skips_directories_without_a_trace(tmp_path):
    creature = CreatureSpec.model_validate(_CREATURE)
    save_run(creature, _trace("real_run"), runs_dir=tmp_path)
    (tmp_path / "not_a_run").mkdir()  # e.g. stray/incomplete directory

    summaries = list_recent_runs(tmp_path)

    assert [s.run_id for s in summaries] == ["real_run"]


def test_list_recent_runs_skips_trace_with_missing_required_fields(tmp_path):
    run_dir = tmp_path / "broken"
    run_dir.mkdir()
    # Valid JSON, but missing the scalar fields a summary needs.
    (run_dir / "trace.json").write_text(json.dumps({"frames": []}))

    assert list_recent_runs(tmp_path) == []


def test_list_recent_runs_skips_trace_with_invalid_json_syntax(tmp_path):
    run_dir = tmp_path / "corrupt"
    run_dir.mkdir()
    (run_dir / "trace.json").write_text("{not valid json")

    assert list_recent_runs(tmp_path) == []


def test_list_recent_runs_does_not_require_frames_to_pass_full_validation(tmp_path):
    """list_recent_runs reads trace.json's scalar fields directly (not through
    EpisodeTrace.model_validate), so it must not depend on `frames` being present
    or well-formed - a run history panel only needs 5 scalars per row, and full
    per-frame pydantic validation would be wasted (and, here, would actively fail:
    EpisodeTrace requires at least one well-formed frame)."""
    run_dir = tmp_path / "weird_frames"
    run_dir.mkdir()
    (run_dir / "trace.json").write_text(
        json.dumps(
            {
                "run_id": "weird",
                "creature_name": "c",
                "task_name": "t",
                "backend": "pybullet",
                "score": 0.5,
                "frames": [{"this": "is not a valid FrameState"}],
            }
        )
    )

    summaries = list_recent_runs(tmp_path)

    assert [s.run_id for s in summaries] == ["weird"]
    assert summaries[0].score == 0.5


def test_save_run_snapshots_the_recorded_controller(tmp_path):
    creature = CreatureSpec.model_validate(_CREATURE)
    task = TaskSpec.model_validate(_TASK)
    trace = _trace(new_run_id()).model_copy(
        update={"meta": TraceMeta(schema_version="1", lab_version="test", controller="cpg")}
    )

    run_dir = save_run(creature, trace, runs_dir=tmp_path, task=task)
    saved = load_trace(run_dir)

    assert (run_dir / "controller.json").exists()
    assert saved.meta.controller_artifact == "controller.json"
    assert saved.meta.controller_hash is not None


def test_latest_marker_cannot_escape_runs_directory(tmp_path):
    (tmp_path / "latest.txt").write_text("../outside\n")
    with pytest.raises(ValueError, match="unsafe run id"):
        latest_run_id(tmp_path)
