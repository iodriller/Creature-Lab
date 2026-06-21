"""Tests for environment checks and episode summaries."""

from creature_lab.diagnostics import collect_doctor_checks, summarize_episode
from creature_lab.schema import EpisodeTrace, TaskSpec


def test_doctor_checks_cover_platform_and_extras():
    checks = {check.name: check for check in collect_doctor_checks()}
    assert "platform" in checks
    assert checks["platform"].status == "info"
    for name in ("sim (pybullet)", "viz (viser)", "export (imageio)", "llm (litellm)"):
        assert name in checks
        assert checks[name].status in {"ok", "missing", "warn", "info"}
    assert "examples run" in checks


def _trace() -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": "r1",
            "creature_name": "tripod",
            "task_name": "crawl_forward",
            "backend": "pybullet",
            "score": 1.5,
            "frames": [
                {
                    "t": 0.0,
                    "parts": {"a": {"position": [0.0, 0.0, 1.0]}},
                    "joint_angles": {"j": 0.0},
                    "contacts": [{"part_id": "a", "position": [0, 0, 0]}],
                    "score": 0.0,
                },
                {
                    "t": 0.5,
                    "parts": {"a": {"position": [1.0, 0.0, 1.0]}},
                    "joint_angles": {"j": 0.3},
                    "contacts": [{"part_id": "a", "position": [0, 0, 0]}],
                    "score": 1.5,
                    "events": ["damage:leg_a"],
                },
            ],
            "meta": {
                "schema_version": "1",
                "lab_version": "0.1.0",
                "score_summary": {"forward": 1.5, "fall": 0.0, "total": 1.5},
                "warnings": ["something looked off"],
            },
        }
    )


def test_summarize_episode_basic_fields():
    summary = summarize_episode(_trace())
    assert summary.frame_count == 2
    assert summary.duration == 0.5  # final frame timestamp
    assert summary.final_score == 1.5
    assert summary.forward_displacement == 1.0
    assert summary.net_displacement == 1.0
    assert summary.total_joint_motion == 0.3  # |0.3 - 0.0|
    assert summary.fell is False  # fall component is 0
    assert summary.damage_events == ["damage:leg_a"]
    assert summary.contacts_by_part == {"a": 2}
    assert summary.warnings == ["something looked off"]


def test_summarize_episode_target_progress():
    task = TaskSpec.model_validate(
        {"name": "reach", "duration": 1.0, "target": {"position": [2.0, 0.0, 1.0]}}
    )
    summary = summarize_episode(_trace(), task)
    # Centroid moves from x=0 to x=1 toward a target at x=2: 1.0 closer.
    assert summary.target_progress == 1.0


def test_summarize_episode_without_meta_has_none_fell():
    trace = _trace().model_copy(update={"meta": None})
    summary = summarize_episode(trace)
    assert summary.fell is None
    assert summary.component_scores == {}
    assert summary.warnings == []


def test_duration_is_final_frame_timestamp_not_span():
    # Frames at t=0.1 and t=0.3: duration is the final timestamp (0.3), not the span (0.2).
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r2",
            "creature_name": "c",
            "task_name": "t",
            "backend": "pybullet",
            "score": 0.0,
            "frames": [
                {"t": 0.1, "parts": {"a": {"position": [0, 0, 0]}}, "score": 0.0},
                {"t": 0.3, "parts": {"a": {"position": [0, 0, 0]}}, "score": 0.0},
            ],
        }
    )
    assert summarize_episode(trace).duration == 0.3


def test_doctor_viz_check_reports_trimesh_and_numpy():
    viz = {check.name: check for check in collect_doctor_checks()}["viz (viser)"]
    assert viz.status in {"ok", "warn", "missing"}
    if viz.status == "ok":
        assert "trimesh" in viz.detail and "numpy" in viz.detail
