"""Tests for onboarding/productization commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from creature_lab.cli import app
from creature_lab.runs import save_run
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec

runner = CliRunner()


def _creature() -> CreatureSpec:
    return CreatureSpec.model_validate(
        {
            "name": "test_bot",
            "parts": [
                {
                    "id": "torso",
                    "shape": "box",
                    "size": [0.4, 0.2, 0.1],
                    "mass": 1.0,
                }
            ],
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
        }
    )


def _save_fixture_run(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())
    return runs_dir, run_dir


def test_report_latest_markdown_and_json(tmp_path):
    runs_dir, run_dir = _save_fixture_run(tmp_path)

    result = runner.invoke(app, ["report", "latest", "--runs-dir", str(runs_dir)])
    assert result.exit_code == 0, result.stdout
    assert "Creature Lab Run Report" in result.stdout
    assert str(run_dir) in result.stdout

    json_result = runner.invoke(app, ["report", "latest", "--runs-dir", str(runs_dir), "--json"])
    assert json_result.exit_code == 0, json_result.stdout
    payload = json.loads(json_result.stdout)
    assert payload["run_id"] == "run1"
    assert payload["artifacts"]["trace"].endswith("trace.json")


def test_inspect_json_uses_latest_alias(tmp_path):
    runs_dir, _ = _save_fixture_run(tmp_path)

    result = runner.invoke(app, ["inspect", "latest", "--runs-dir", str(runs_dir), "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["summary"]["forward_displacement"] == 1.0


def test_schema_command_writes_json_schema(tmp_path):
    out = tmp_path / "creature.schema.json"
    result = runner.invoke(app, ["schema", "creature", "--out", str(out)])

    assert result.exit_code == 0, result.stdout
    data = json.loads(out.read_text())
    assert data["title"] == "CreatureSpec"
    assert "parts" in data["properties"]


def test_gallery_build_cards_without_media(tmp_path):
    out = tmp_path / "gallery"
    result = runner.invoke(app, ["gallery", "build", "--zoo", "--out", str(out), "--no-media"])

    assert result.exit_code == 0, result.stdout
    assert (out / "index.md").exists()
    assert (out / "quadruped.md").exists()


def test_zoo_list_json():
    result = runner.invoke(app, ["zoo", "list", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert any(entry["creature"] == "quadruped" for entry in payload)


def test_build_help_is_available():
    result = runner.invoke(app, ["build", "--help"])

    assert result.exit_code == 0, result.stdout
    assert "build editor" in result.stdout
    assert "--preset" in result.stdout


def test_bench_requires_zoo_flag():
    result = runner.invoke(app, ["bench"])

    assert result.exit_code == 2
    assert "use --zoo" in result.stdout


def test_bench_zoo_json_smoke(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "bench",
            "--zoo",
            "--task",
            "crawl_forward",
            "--attempts",
            "1",
            "--seed",
            "0",
            "--runs-dir",
            str(runs_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "zoo_benchmark"
    assert payload["results"]
    assert (runs_dir / "latest.txt").exists()
