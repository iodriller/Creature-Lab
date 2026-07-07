"""Tests for the Creature Zoo gallery and its CLI."""

import pytest
from typer.testing import CliRunner

from creature_lab.cli import app
from creature_lab.schema import CreatureSpec, TaskSpec
from creature_lab.zoo import (
    default_task_name,
    list_zoo_creatures,
    validate_all,
    zoo_baseline,
    zoo_creature,
    zoo_tasks,
)

runner = CliRunner()


def test_zoo_has_at_least_five_creatures():
    creatures = list_zoo_creatures()
    assert len(creatures) >= 5
    assert "quadruped" in creatures and "worm" in creatures


def test_validate_all_passes():
    pairs = validate_all()
    # At least one pair per creature, all cross-validated without raising.
    assert len(pairs) >= len(list_zoo_creatures())


def test_zoo_creature_loads_default_and_named_task():
    creature, task = zoo_creature("quadruped")
    assert isinstance(creature, CreatureSpec)
    assert isinstance(task, TaskSpec)
    assert task.name == default_task_name("quadruped")

    _, reach = zoo_creature("quadruped", "reach_target")
    assert reach.target is not None


def test_damaged_quadruped_task_targets_a_real_part():
    creature, task = zoo_creature("damaged_quadruped")
    assert task.damage_event is not None
    assert task.damage_event.part_id in {part.id for part in creature.parts}


@pytest.mark.parametrize("task_name", ["slope_climb", "step_over", "gap_cross"])
def test_quadruped_terrain_tasks_have_a_calibrated_baseline(task_name):
    creature, task = zoo_creature("quadruped", task_name)
    assert task.terrain.type != "plane"

    baseline = zoo_baseline("quadruped", task_name)
    assert baseline is not None
    assert baseline["best_score"] > 0


def test_zoo_baseline_backend_selects_the_suffixed_file():
    pybullet_baseline = zoo_baseline("quadruped", "crawl_forward")
    mujoco_baseline = zoo_baseline("quadruped", "crawl_forward", backend="mujoco")

    assert pybullet_baseline is not None
    assert mujoco_baseline is not None
    assert "pybullet" in pybullet_baseline["backend"]
    assert "mujoco" in mujoco_baseline["backend"]


def test_zoo_baseline_missing_backend_returns_none():
    assert zoo_baseline("quadruped", "crawl_forward", backend="nonexistent") is None


def test_zoo_creature_unknown_name_raises():
    with pytest.raises(KeyError, match="unknown zoo creature"):
        zoo_creature("dragon")


def test_zoo_creature_unknown_task_raises():
    with pytest.raises(KeyError, match="unknown task"):
        zoo_creature("worm", "fly")


def test_every_zoo_creature_has_a_default_task():
    for name in list_zoo_creatures():
        assert default_task_name(name) in zoo_tasks(name)


def test_zoo_list_cli():
    result = runner.invoke(app, ["zoo", "list"])
    assert result.exit_code == 0, result.stdout
    assert "quadruped" in result.stdout


def test_zoo_validate_all_cli():
    result = runner.invoke(app, ["zoo", "validate-all"])
    assert result.exit_code == 0, result.stdout
    assert "valid all" in result.stdout


def test_zoo_run_cli_saves_trace(tmp_path):
    pytest.importorskip("pybullet")
    from creature_lab.schema import EpisodeTrace

    runs_dir = tmp_path / "runs"
    result = runner.invoke(app, ["zoo", "run", "worm", "--runs-dir", str(runs_dir)])
    assert result.exit_code == 0, result.stdout

    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    trace = EpisodeTrace.model_validate_json((run_dirs[0] / "trace.json").read_text())
    assert trace.creature_name == "worm"
