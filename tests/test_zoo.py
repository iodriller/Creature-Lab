"""Tests for the Creature Zoo gallery and its CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from creature_lab.cli import app
from creature_lab.schema import ControllerSpec, CreatureSpec, TaskSpec
from creature_lab.zoo import (
    default_task_name,
    list_zoo_creatures,
    validate_all,
    zoo_baseline,
    zoo_creature,
    zoo_optimized_controller,
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


# -- packaged optimized gaits ------------------------------------------------------


@pytest.mark.parametrize("name", ["quadruped", "hexapod", "tripod", "worm"])
def test_locomotion_creatures_ship_a_valid_optimized_controller(name):
    from creature_lab.schema import ControllerSpec

    path = zoo_optimized_controller(name)
    assert path is not None and path.exists()
    spec = ControllerSpec.model_validate_json(path.read_text())
    assert spec.type.value == "sinusoid"
    creature, _ = zoo_creature(name)
    assert {m.joint for m in spec.motors} == {m.joint for m in creature.motors}


def test_only_walking_humanoid_ships_a_measured_controller():
    # The 8-DOF body remains a balance exercise. The 12-DOF body has horizontal
    # feet, scaled actuators, and a gait accepted by the executable showcase.
    assert zoo_optimized_controller("humanoid_minimal") is None
    path = zoo_optimized_controller("humanoid_12dof")
    assert path is not None and path.exists()
    spec = ControllerSpec.model_validate_json(path.read_text())
    assert spec.type.value == "sinusoid"


def test_zoo_run_curated_default_uses_the_optimized_gait():
    pytest.importorskip("pybullet")
    curated = runner.invoke(app, ["zoo", "run", "quadruped", "--json"])
    optimized = runner.invoke(
        app, ["zoo", "run", "quadruped", "--controller", "optimized", "--json"]
    )
    baseline = runner.invoke(app, ["zoo", "run", "quadruped", "--controller", "sinusoid", "--json"])
    assert curated.exit_code == 0, curated.stdout
    assert optimized.exit_code == 0, optimized.stdout
    assert baseline.exit_code == 0, baseline.stdout

    import json

    curated_score = json.loads(curated.stdout)["score"]
    assert curated_score == pytest.approx(json.loads(optimized.stdout)["score"])
    assert curated_score > json.loads(baseline.stdout)["score"]


def test_curated_controller_survives_editing_the_humanoid(tmp_path):
    """Regression test: editing any slider on the humanoid used to make `curated`
    silently fall back to `posture` (which stands still and never walks), because
    the old gate required an exact spec-hash match against the packaged creature.
    A single motor-amplitude edit doesn't change which joints exist, so the
    packaged walking gait must still be used - see docs/KNOWN_ISSUES.md."""
    pytest.importorskip("pybullet")
    creature, task = zoo_creature("humanoid_12dof", "walk")
    edited = creature.model_copy(deep=True)
    edited.motors[0].amplitude = round(edited.motors[0].amplitude + 0.01, 4)
    assert edited.motors[0].amplitude != creature.motors[0].amplitude  # sanity: it did change

    creature_path = tmp_path / "humanoid.json"
    task_path = tmp_path / "walk.json"
    creature_path.write_text(edited.model_dump_json())
    task_path.write_text(task.model_dump_json())
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            str(creature_path),
            "--task",
            str(task_path),
            "--controller",
            "curated",
            "--runs-dir",
            str(runs_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout

    import json

    payload = json.loads(result.stdout)
    saved_trace = json.loads((Path(payload["run_dir"]) / "trace.json").read_text())
    meta_controller = saved_trace["meta"]["controller"]
    assert meta_controller != "posture", (
        "editing a slider must not silently disable the packaged walking gait"
    )
    assert meta_controller.endswith("controller.json")
    assert payload["score"] > 0.1  # posture alone can't reach this; confirms it actually walked


def test_curated_controller_falls_back_when_a_driven_joint_is_removed(tmp_path):
    """The joint-id compatibility check must still reject a genuinely incompatible
    body - it should be more lenient than an exact hash match, not unconditional."""
    pytest.importorskip("pybullet")
    creature, task = zoo_creature("humanoid_12dof", "walk")
    incompatible = creature.model_copy(deep=True)
    # Rename one joint the packaged gait drives (not delete it - deleting a joint
    # breaks the body's tree structure and fails CreatureSpec validation before we
    # even get to the controller-compatibility check this test targets).
    for joint in incompatible.joints:
        if joint.id == "ankle_l":
            joint.id = "ankle_l_renamed"
    for motor in incompatible.motors:
        if motor.joint == "ankle_l":
            motor.joint = "ankle_l_renamed"

    creature_path = tmp_path / "humanoid.json"
    task_path = tmp_path / "walk.json"
    creature_path.write_text(incompatible.model_dump_json())
    task_path.write_text(task.model_dump_json())
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            str(creature_path),
            "--task",
            str(task_path),
            "--controller",
            "curated",
            "--runs-dir",
            str(runs_dir),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout

    import json

    payload = json.loads(result.stdout)
    saved_trace = json.loads((Path(payload["run_dir"]) / "trace.json").read_text())
    assert saved_trace["meta"]["controller"] == "posture"


def test_zoo_run_optimized_controller_errors_cleanly_when_none_packaged():
    pytest.importorskip("pybullet")
    result = runner.invoke(app, ["zoo", "run", "humanoid_minimal", "--controller", "optimized"])
    assert result.exit_code != 0
    assert "no optimized controller" in result.stdout.lower()


def test_zoo_list_shows_optimized_gait_column():
    result = runner.invoke(app, ["zoo", "list"])
    assert result.exit_code == 0, result.stdout
    assert "optimized gait" in result.stdout
