"""End-to-end scenario tests driving the CLI exactly as a user would.

Each test runs a full pipeline through the Typer app and validates the on-disk
artifacts, so it exercises the real backend, trace I/O, viewer, and exporter
together (not mocked). Tests skip when their optional dependency is absent; CI
installs all extras, so the whole pipeline runs there.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from creature_lab.cli import app
from creature_lab.schema import CreatureSpec, EpisodeTrace

runner = CliRunner()
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
TRIPOD = EXAMPLES / "tripod.json"

pybullet = pytest.importorskip("pybullet")  # the whole module needs the sim backend


def _only_run_dir(runs_dir: Path) -> Path:
    [run_dir] = list(runs_dir.iterdir())
    return run_dir


def test_run_replay_export_pipeline(tmp_path):
    pytest.importorskip("imageio")
    runs_dir = tmp_path / "runs"

    run = runner.invoke(
        app,
        [
            "run",
            str(TRIPOD),
            "--task",
            str(EXAMPLES / "crawl_forward.json"),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run.exit_code == 0, run.stdout

    run_dir = _only_run_dir(runs_dir)
    # Run is self-describing: creature, task, and trace are all written.
    creature = CreatureSpec.model_validate_json((run_dir / "creature.json").read_text())
    trace = EpisodeTrace.model_validate_json((run_dir / "trace.json").read_text())
    assert (run_dir / "task.json").exists()
    assert creature.name == "tripod"
    assert len(trace.frames) == 180
    assert any(frame.contacts for frame in trace.frames)

    # Reproducibility metadata is populated.
    meta = trace.meta
    assert meta is not None
    assert meta.schema_version and meta.lab_version
    assert meta.backend_version and meta.backend_version.startswith("pybullet")
    assert meta.timestep == pytest.approx(1 / 60)
    assert meta.creature_hash and meta.creature_hash.startswith("sha256:")
    assert meta.task_hash and meta.task_hash.startswith("sha256:")
    assert "total" in meta.score_summary
    assert isinstance(meta.warnings, list)  # warnings are stored (empty for a clean run)
    # Hashes match an independent hash of the saved specs.
    from creature_lab.hashing import spec_hash
    from creature_lab.schema import TaskSpec

    saved_task = TaskSpec.model_validate_json((run_dir / "task.json").read_text())
    assert meta.creature_hash == spec_hash(creature)
    assert meta.task_hash == spec_hash(saved_task)

    replay = runner.invoke(app, ["replay", str(run_dir)])
    assert replay.exit_code == 0, replay.stdout
    assert trace.run_id in replay.stdout

    inspect = runner.invoke(app, ["inspect", str(run_dir)])
    assert inspect.exit_code == 0, inspect.stdout
    assert "score breakdown" in inspect.stdout
    assert trace.run_id in inspect.stdout

    gif = tmp_path / "out.gif"
    mp4 = tmp_path / "out.mp4"
    for out in (gif, mp4):
        result = runner.invoke(
            app, ["export", str(run_dir), "--out", str(out), "--width", "120", "--height", "90"]
        )
        assert result.exit_code == 0, result.stdout
        assert out.exists() and out.stat().st_size > 0


@pytest.mark.parametrize(
    "task_file", ["crawl_forward.json", "reach_target.json", "recover_after_damage.json"]
)
def test_every_example_task_runs(tmp_path, task_file):
    runs_dir = tmp_path / "runs"
    result = runner.invoke(
        app, ["run", str(TRIPOD), "--task", str(EXAMPLES / task_file), "--runs-dir", str(runs_dir)]
    )
    assert result.exit_code == 0, result.stdout
    assert "score=" in result.stdout

    trace = EpisodeTrace.model_validate_json((_only_run_dir(runs_dir) / "trace.json").read_text())
    assert trace.frames
    if task_file == "recover_after_damage.json":
        # The mid-run damage event must be recorded in the trace.
        assert any("damage:leg_a" in frame.events for frame in trace.frames)


def test_demo_streams_and_saves(tmp_path):
    pytest.importorskip("viser")
    runs_dir = tmp_path / "runs"
    # --no-hold returns after one streamed pass instead of serving forever.
    result = runner.invoke(
        app, ["demo", "--no-hold", "--port", "8147", "--runs-dir", str(runs_dir)]
    )
    assert result.exit_code == 0, result.stdout

    run_dir = _only_run_dir(runs_dir)
    trace = EpisodeTrace.model_validate_json((run_dir / "trace.json").read_text())
    assert trace.creature_name == "tripod"
    assert (run_dir / "creature.json").exists()
    assert (run_dir / "task.json").exists()
    assert trace.meta is not None and trace.meta.creature_hash


def test_soft_warning_is_stored_in_run_artifact(tmp_path):
    # A motor swinging past its joint limit is a soft warning -> run continues but records it.
    creature = json.loads(TRIPOD.read_text())
    for motor in creature["motors"]:
        motor["amplitude"] = 2.0  # joint limit is [-0.8, 0.8]
    wild = tmp_path / "wild.json"
    wild.write_text(json.dumps(creature))

    runs_dir = tmp_path / "runs"
    result = runner.invoke(
        app,
        [
            "run",
            str(wild),
            "--task",
            str(EXAMPLES / "crawl_forward.json"),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout

    trace = EpisodeTrace.model_validate_json((_only_run_dir(runs_dir) / "trace.json").read_text())
    assert trace.meta is not None
    assert any("exceeding its limit" in w for w in trace.meta.warnings)


def test_validate_with_task_is_a_clean_preflight():
    # No simulation; just schema + cross-validation. Does not need any backend.
    result = runner.invoke(
        app, ["validate", str(TRIPOD), "--task", str(EXAMPLES / "crawl_forward.json")]
    )
    assert result.exit_code == 0, result.stdout
    assert "compatible" in result.stdout


def test_run_aborts_on_unknown_damage_part(tmp_path):
    bad_task = tmp_path / "bad_task.json"
    bad_task.write_text(
        '{"name": "boom", "duration": 2.0, "damage_event": {"time": 1.0, "part_id": "ghost"}}'
    )
    result = runner.invoke(
        app, ["run", str(TRIPOD), "--task", str(bad_task), "--runs-dir", str(tmp_path / "runs")]
    )
    assert result.exit_code == 1
    assert "unknown part" in result.stdout


def test_ask_offline_designs_and_saves_agent_trace(tmp_path):
    from creature_lab.schema import AgentTrace

    runs_dir = tmp_path / "runs"
    result = runner.invoke(
        app,
        [
            "ask",
            "make it crawl farther",
            str(TRIPOD),
            "--task",
            str(EXAMPLES / "crawl_forward.json"),
            "--offline",
            "--attempts",
            "3",
            "--seed",
            "0",
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout

    run_dir = _only_run_dir(runs_dir)
    assert (run_dir / "creature.json").exists()
    assert (run_dir / "trace.json").exists()
    agent = AgentTrace.model_validate_json((run_dir / "agent.json").read_text())
    assert agent.goal == "make it crawl farther"
    assert len(agent.steps) == 4  # seed + 3 attempts


def test_evolve_then_export_best(tmp_path):
    pytest.importorskip("imageio")
    runs_dir = tmp_path / "runs"
    evolve = runner.invoke(
        app,
        [
            "evolve",
            str(TRIPOD),
            "--task",
            str(EXAMPLES / "crawl_forward.json"),
            "--attempts",
            "2",
            "--seed",
            "1",
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert evolve.exit_code == 0, evolve.stdout

    run_dir = _only_run_dir(runs_dir)
    best = json.loads((run_dir / "creature.json").read_text())
    assert best["name"] == "tripod"

    out = tmp_path / "best.gif"
    export = runner.invoke(
        app, ["export", str(run_dir), "--out", str(out), "--width", "120", "--height", "90"]
    )
    assert export.exit_code == 0, export.stdout
    assert out.exists() and out.stat().st_size > 0
