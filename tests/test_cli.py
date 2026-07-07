"""Tests for the command-line interface."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from creature_lab.cli import app

runner = CliRunner()
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
EXAMPLE = EXAMPLES / "tripod.json"
TASK = EXAMPLES / "crawl_forward.json"


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "creature-lab" in result.stdout


def test_doctor_runs_and_reports_checks():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.stdout
    assert "doctor" in result.stdout
    assert "platform" in result.stdout
    assert "examples run" in result.stdout


def test_inspect_reports_summary(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"
    run = runner.invoke(
        app, ["run", str(EXAMPLE), "--task", str(TASK), "--runs-dir", str(runs_dir)]
    )
    assert run.exit_code == 0, run.stdout
    [run_dir] = [path for path in runs_dir.iterdir() if path.is_dir()]

    result = runner.invoke(app, ["inspect", str(run_dir)])
    assert result.exit_code == 0, result.stdout
    assert "score breakdown" in result.stdout
    assert "contacts by part" in result.stdout
    assert "sha256:" in result.stdout
    assert "terrain" in result.stdout
    assert "plane" in result.stdout


def test_inspect_shows_non_flat_terrain(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"
    run = runner.invoke(
        app,
        ["zoo", "run", "quadruped", "--task", "slope_climb", "--runs-dir", str(runs_dir)],
    )
    assert run.exit_code == 0, run.stdout
    [run_dir] = [path for path in runs_dir.iterdir() if path.is_dir()]

    result = runner.invoke(app, ["inspect", str(run_dir)])
    assert result.exit_code == 0, result.stdout
    assert "slope" in result.stdout

    json_result = runner.invoke(app, ["inspect", str(run_dir), "--json"])
    payload = json.loads(json_result.stdout)
    assert "slope" in payload["terrain"]


def test_inspect_missing_path_exits_cleanly():
    result = runner.invoke(app, ["inspect", "does/not/exist"])
    assert result.exit_code == 2  # friendly file-not-found, not a raw traceback


def test_inspect_without_creature_json_still_summarizes(tmp_path):
    # A run dir / trace.json without a sibling creature.json must not crash inspect.
    trace = {
        "run_id": "r1",
        "creature_name": "c",
        "task_name": "t",
        "backend": "pybullet",
        "score": 0.5,
        "frames": [
            {"t": 0.1, "parts": {"a": {"position": [0, 0, 0]}}, "score": 0.0},
            {"t": 0.2, "parts": {"a": {"position": [1, 0, 0]}}, "score": 0.5},
        ],
    }
    (tmp_path / "trace.json").write_text(json.dumps(trace))
    result = runner.invoke(app, ["inspect", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "final score" in result.stdout


def test_validate_example_creature():
    result = runner.invoke(app, ["validate", str(EXAMPLE)])
    assert result.exit_code == 0, result.stdout
    assert "valid" in result.stdout


def test_validate_missing_file():
    result = runner.invoke(app, ["validate", "does/not/exist.json"])
    assert result.exit_code == 2


def test_demo_missing_creature_exits():
    # The happy path serves a blocking viewer; exercise the spec-loading guard instead.
    result = runner.invoke(app, ["demo", "does/not/exist.json", "--task", "also/missing.json"])
    assert result.exit_code == 2


def test_validate_invalid_creature(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "x"}))  # missing parts
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "invalid CreatureSpec" in result.stdout


def test_validate_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "invalid JSON" in result.stdout


def test_run_saves_a_replayable_trace(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"
    result = runner.invoke(
        app, ["run", str(EXAMPLE), "--task", str(TASK), "--runs-dir", str(runs_dir)]
    )
    assert result.exit_code == 0, result.stdout
    assert "score=" in result.stdout

    [run_dir] = [path for path in runs_dir.iterdir() if path.is_dir()]
    replay_result = runner.invoke(app, ["replay", str(run_dir)])
    assert replay_result.exit_code == 0, replay_result.stdout
    assert "tripod" in replay_result.stdout
    assert "crawl_forward" in replay_result.stdout


def test_replay_missing_trace(tmp_path):
    result = runner.invoke(app, ["replay", str(tmp_path)])
    assert result.exit_code == 2


def test_evolve_saves_best_creature(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"
    result = runner.invoke(
        app,
        [
            "evolve",
            str(EXAMPLE),
            "--task",
            str(TASK),
            "--attempts",
            "2",
            "--seed",
            "0",
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "best" in result.stdout

    [run_dir] = [path for path in runs_dir.iterdir() if path.is_dir()]
    assert (run_dir / "creature.json").exists()
    assert (run_dir / "trace.json").exists()


def test_export_creates_gif(tmp_path):
    pytest.importorskip("pybullet")
    pytest.importorskip("imageio")
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app, ["run", str(EXAMPLE), "--task", str(TASK), "--runs-dir", str(runs_dir)]
    )
    assert run_result.exit_code == 0, run_result.stdout

    [run_dir] = [path for path in runs_dir.iterdir() if path.is_dir()]
    out = tmp_path / "clip.gif"
    result = runner.invoke(
        app, ["export", str(run_dir), "--out", str(out), "--width", "64", "--height", "48"]
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists() and out.stat().st_size > 0


def test_export_reads_terrain_from_the_saved_task(tmp_path):
    # CLI wiring smoke test: `export` reads task.json from the run dir and passes it
    # through to render_trace, so a non-flat-terrain run doesn't render a flat floor.
    pytest.importorskip("pybullet")
    pytest.importorskip("imageio")
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "zoo",
            "run",
            "quadruped",
            "--task",
            "slope_climb",
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 0, run_result.stdout

    [run_dir] = [path for path in runs_dir.iterdir() if path.is_dir()]
    assert (run_dir / "task.json").exists()
    out = tmp_path / "clip.gif"
    result = runner.invoke(
        app, ["export", str(run_dir), "--out", str(out), "--width", "64", "--height", "48"]
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists() and out.stat().st_size > 0
