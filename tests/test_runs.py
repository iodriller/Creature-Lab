"""Tests for episode trace persistence (creature_lab.runs)."""

from creature_lab.runs import load_trace, new_run_id, save_trace
from creature_lab.schema import EpisodeTrace


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


def test_load_trace_from_run_directory(tmp_path):
    trace = _trace(new_run_id())
    save_trace(trace, runs_dir=tmp_path)

    assert load_trace(tmp_path / trace.run_id) == trace


def test_run_ids_are_unique():
    assert new_run_id() != new_run_id()
