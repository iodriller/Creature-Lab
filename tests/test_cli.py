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

    [run_dir] = list(runs_dir.iterdir())
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

    [run_dir] = list(runs_dir.iterdir())
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

    [run_dir] = list(runs_dir.iterdir())
    out = tmp_path / "clip.gif"
    result = runner.invoke(
        app, ["export", str(run_dir), "--out", str(out), "--width", "64", "--height", "48"]
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists() and out.stat().st_size > 0
