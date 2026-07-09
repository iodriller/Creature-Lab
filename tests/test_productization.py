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


def test_report_html_writes_self_contained_file(tmp_path):
    runs_dir, run_dir = _save_fixture_run(tmp_path)
    html_out = tmp_path / "report.html"

    result = runner.invoke(
        app, ["report", "latest", "--runs-dir", str(runs_dir), "--html", str(html_out)]
    )

    assert result.exit_code == 0, result.stdout
    page = html_out.read_text()
    assert "run1" in page
    assert "http://" not in page and "https://" not in page
    assert str(run_dir) not in result.stdout  # markdown wasn't also dumped to stdout


def test_compare_html_writes_comparison_report(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir_a = save_run(_creature(), _trace("run_a"), runs_dir=runs_dir, task=_task())
    run_dir_b = save_run(_creature(), _trace("run_b"), runs_dir=runs_dir, task=_task())
    html_out = tmp_path / "diff.html"

    result = runner.invoke(
        app, ["compare", str(run_dir_a), str(run_dir_b), "--html", str(html_out)]
    )

    assert result.exit_code == 0, result.stdout
    page = html_out.read_text()
    assert "run_a" in page and "run_b" in page
    assert "http://" not in page and "https://" not in page


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
    assert (out / "index.html").exists()
    page = (out / "index.html").read_text()
    assert "quadruped" in page
    assert "http://" not in page and "https://" not in page


def test_robustness_cli_json_smoke(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())

    result = runner.invoke(
        app,
        [
            "robustness",
            str(run_dir),
            "--trials",
            "2",
            "--seed",
            "0",
            "--runs-dir",
            str(runs_dir),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload["trials"]) == 2
    assert payload["mean_score"] is not None
    assert 0.0 <= payload["fail_rate"] <= 1.0


def test_robustness_cli_save_writes_a_reportable_run(tmp_path):
    pytest.importorskip("pybullet")
    runs_dir = tmp_path / "runs"
    save_runs_dir = tmp_path / "robustness_runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())

    result = runner.invoke(
        app,
        [
            "robustness",
            str(run_dir),
            "--trials",
            "2",
            "--save",
            "--runs-dir",
            str(save_runs_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    saved_run_dirs = [p for p in save_runs_dir.iterdir() if p.is_dir()]
    assert len(saved_run_dirs) == 1
    assert (saved_run_dirs[0] / "robustness.json").exists()

    report_result = runner.invoke(app, ["report", str(saved_run_dirs[0]), "--json"])
    payload = json.loads(report_result.stdout)
    assert payload["robustness"] is not None
    assert payload["robustness"]["mean_score"] is not None


def test_sim2sim_cli_json_smoke(tmp_path):
    pytest.importorskip("pybullet")
    pytest.importorskip("mujoco")
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())

    result = runner.invoke(app, ["sim2sim", str(run_dir), "--runs-dir", str(runs_dir), "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "pybullet" in payload and "mujoco" in payload
    assert payload["score_gap"] >= 0.0
    assert payload["mean_root_divergence"] >= 0.0


def test_sim2sim_cli_save_writes_a_reportable_run(tmp_path):
    pytest.importorskip("pybullet")
    pytest.importorskip("mujoco")
    runs_dir = tmp_path / "runs"
    save_runs_dir = tmp_path / "sim2sim_runs"
    run_dir = save_run(_creature(), _trace(), runs_dir=runs_dir, task=_task())

    result = runner.invoke(
        app, ["sim2sim", str(run_dir), "--save", "--runs-dir", str(save_runs_dir)]
    )

    assert result.exit_code == 0, result.stdout
    saved_run_dirs = [p for p in save_runs_dir.iterdir() if p.is_dir()]
    assert len(saved_run_dirs) == 1
    assert (saved_run_dirs[0] / "sim2sim.json").exists()

    html_out = tmp_path / "report.html"
    report_result = runner.invoke(app, ["report", str(saved_run_dirs[0]), "--html", str(html_out)])
    assert report_result.exit_code == 0, report_result.stdout
    assert "Sim2Sim" in html_out.read_text()


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


def test_bench_zoo_mujoco_backend_compares_against_the_mujoco_baseline(tmp_path):
    pytest.importorskip("mujoco")
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "bench",
            "--zoo",
            "--task",
            "crawl_forward",
            "--backend",
            "mujoco",
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
    quadruped_result = next(r for r in payload["results"] if r["creature"] == "quadruped")
    # The MuJoCo baseline is close to zero; the (much higher) PyBullet baseline would
    # wrongly fail this near-zero MuJoCo score against a ~0.9 threshold.
    assert quadruped_result["baseline_score"] == pytest.approx(-0.0027, abs=1e-3)
