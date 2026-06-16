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


def test_run_example_episode():
    pytest.importorskip("pybullet")
    result = runner.invoke(app, ["run", str(EXAMPLE), "--task", str(TASK)])
    assert result.exit_code == 0, result.stdout
    assert "score=" in result.stdout
