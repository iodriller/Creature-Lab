"""Tests for the FrameState and EpisodeTrace schemas."""

import pytest
from pydantic import ValidationError

from creature_lab.schema import EpisodeTrace, FrameState, TraceMeta


def _frame(t: float, score: float = 0.0) -> dict:
    return {"t": t, "parts": {"torso": {"position": [0.0, 0.0, 0.0]}}, "score": score}


def test_trace_round_trips():
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r1",
            "creature_name": "tripod",
            "task_name": "crawl_forward",
            "backend": "pybullet",
            "score": 1.5,
            "frames": [_frame(0.0), _frame(0.1, 1.5)],
        }
    )
    restored = EpisodeTrace.model_validate_json(trace.model_dump_json())
    assert restored == trace
    assert trace.meta is None  # meta is optional and defaults to None


def test_trace_with_meta_round_trips():
    meta = TraceMeta(
        schema_version="1",
        lab_version="0.1.0",
        backend_version="pybullet api 201",
        timestep=1 / 60,
        seed=7,
        creature_hash="sha256:abc",
        task_hash="sha256:def",
        score_summary={"forward": 1.0, "total": 1.0},
    )
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r1",
            "creature_name": "tripod",
            "task_name": "crawl_forward",
            "backend": "pybullet",
            "score": 1.0,
            "frames": [_frame(0.0, 1.0)],
            "meta": meta.model_dump(),
        }
    )
    restored = EpisodeTrace.model_validate_json(trace.model_dump_json())
    assert restored == trace
    assert restored.meta == meta


def test_frame_requires_parts():
    with pytest.raises(ValidationError):
        FrameState.model_validate({"t": 0.0, "parts": {}})


def test_frame_score_must_be_finite():
    with pytest.raises(ValidationError):
        FrameState.model_validate({**_frame(0.0), "score": float("inf")})


def test_frames_must_be_time_sorted():
    spec = {
        "run_id": "r1",
        "creature_name": "c",
        "task_name": "t",
        "backend": "pybullet",
        "score": 0.0,
        "frames": [_frame(0.2), _frame(0.1)],
    }
    with pytest.raises(ValidationError, match="sorted by time"):
        EpisodeTrace.model_validate(spec)


def test_trace_requires_at_least_one_frame():
    spec = {
        "run_id": "r1",
        "creature_name": "c",
        "task_name": "t",
        "backend": "pybullet",
        "score": 0.0,
        "frames": [],
    }
    with pytest.raises(ValidationError):
        EpisodeTrace.model_validate(spec)
