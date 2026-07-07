"""Tests for report data assembly and Markdown rendering (creature_lab/reports.py)."""

from __future__ import annotations

import json

from creature_lab.reports import build_report, report_to_markdown
from creature_lab.runs import save_run
from creature_lab.schema import AgentTrace, CreatureSpec, EpisodeTrace, TaskSpec


def _creature() -> CreatureSpec:
    return CreatureSpec.model_validate(
        {
            "name": "test_bot",
            "parts": [{"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0}],
        }
    )


def _task() -> TaskSpec:
    return TaskSpec.model_validate({"name": "crawl_forward", "duration": 1.0})


def _trace(run_id: str = "run1") -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": run_id,
            "creature_name": "test_bot",
            "task_name": "crawl_forward",
            "backend": "pybullet",
            "score": 1.0,
            "frames": [
                {"t": 0.0, "parts": {"torso": {"position": [0, 0, 0]}}, "score": 0.0},
                {"t": 1.0, "parts": {"torso": {"position": [1, 0, 0]}}, "score": 1.0},
            ],
            "meta": {
                "schema_version": "1",
                "lab_version": "0.1.0",
                "backend_version": "3.2.7",
                "timestep": 1.0,
                "seed": 7,
            },
        }
    )


def test_build_report_basic_fields(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())

    report = build_report(run_dir)

    assert report["run_id"] == "run1"
    assert report["creature"]["name"] == "test_bot"
    assert report["creature"]["parts"] == 1
    assert report["task"]["name"] == "crawl_forward"
    assert report["task"]["terrain"] == "plane (friction=0.8)"
    assert report["backend"]["name"] == "pybullet"
    assert report["score"] == 1.0
    assert report["improvement"] is None
    assert report["reproducibility"]["seed"] == 7
    assert report["reproducibility"]["timestep"] == 1.0
    assert report["reproducibility"]["command"] is not None
    assert "creature-lab run" in report["reproducibility"]["command"]


def test_build_report_without_creature_json(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    (run_dir / "creature.json").unlink()

    report = build_report(run_dir)

    assert report["creature"]["parts"] is None
    assert report["diagnosis"] == {"patterns": [], "suggestions": [], "metrics": {}}
    # No creature.json means the reproduce command can't reference it.
    assert report["reproducibility"]["command"] is None


def test_build_report_describes_non_flat_terrain(tmp_path):
    runs_dir = tmp_path / "runs"
    sloped_task = TaskSpec.model_validate(
        {
            "name": "slope_climb",
            "duration": 1.0,
            "terrain": {"type": "slope", "slope_angle": 0.2, "friction": 1.0},
        }
    )
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=sloped_task)

    report = build_report(run_dir)

    assert report["task"]["terrain"] == "slope (angle=0.2 rad, friction=1)"


def test_build_report_terrain_is_none_without_a_task(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    (run_dir / "task.json").unlink()

    report = build_report(run_dir)

    assert report["task"]["terrain"] is None


def test_build_report_picks_up_evolve_lineage(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    lineage = {
        "strategy": "hill_climb",
        "nodes": [
            {"parent": None, "score": 0.2, "accepted": True},
            {"parent": 0, "score": 0.5, "accepted": True},
            {"parent": 1, "score": 0.4, "accepted": False},
        ],
    }
    (run_dir / "lineage.json").write_text(json.dumps(lineage))

    report = build_report(run_dir)

    assert report["improvement"]["kind"] == "evolve"
    assert report["improvement"]["strategy"] == "hill_climb"
    assert report["improvement"]["attempts"] == 2
    assert report["improvement"]["best_score"] == 0.5
    assert report["improvement"]["accepted"] == 1


def test_build_report_picks_up_agent_trace(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    agent_trace = AgentTrace.model_validate(
        {
            "creature_name": "test_bot",
            "task_name": "crawl_forward",
            "goal": "make it crawl farther",
            "best_score": 0.7,
            "steps": [
                {"attempt": 0, "action": "baseline", "valid": True, "score": 0.3},
                {
                    "attempt": 1,
                    "action": "set_motor",
                    "valid": True,
                    "score": 0.7,
                    "accepted": True,
                },
                {"attempt": 2, "action": "bad_edit", "valid": False},
            ],
        }
    )
    (run_dir / "agent.json").write_text(agent_trace.model_dump_json())

    report = build_report(run_dir)

    assert report["improvement"]["kind"] == "ask"
    assert report["improvement"]["goal"] == "make it crawl farther"
    assert report["improvement"]["best_score"] == 0.7
    assert report["improvement"]["accepted"] == 1
    assert report["improvement"]["invalid"] == 1


def test_report_to_markdown_renders_all_sections(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    lineage = {
        "strategy": "genetic",
        "nodes": [{"parent": None, "score": 0.1, "accepted": True}],
    }
    (run_dir / "lineage.json").write_text(json.dumps(lineage))

    markdown = report_to_markdown(build_report(run_dir))

    assert "# Creature Lab Run Report: run1" in markdown
    assert "- Terrain: plane (friction=0.8)" in markdown
    assert "## Score Breakdown" in markdown
    assert "## Signals" in markdown
    assert "## Diagnostics" in markdown
    assert "## Improvement" in markdown
    assert "genetic" in markdown
    assert "## Reproducibility" in markdown
    assert "Seed: 7" in markdown
    assert "## Artifacts" in markdown


def test_report_to_markdown_ask_improvement_variant(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    agent_trace = AgentTrace.model_validate(
        {
            "creature_name": "test_bot",
            "task_name": "crawl_forward",
            "goal": "make it crawl farther",
            "best_score": 0.7,
            "steps": [{"attempt": 0, "action": "baseline", "valid": True, "score": 0.7}],
        }
    )
    (run_dir / "agent.json").write_text(agent_trace.model_dump_json())

    markdown = report_to_markdown(build_report(run_dir))

    assert "Ask:" in markdown
    assert "Goal: make it crawl farther" in markdown
