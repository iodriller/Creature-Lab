"""Tests for the humanoid kit: impulse events, zoo entries, and biped diagnosis."""

import pytest

from creature_lab.diagnosis import diagnose
from creature_lab.scaffold import generate_humanoid
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec
from creature_lab.validation import EpisodeInputError, validate_episode_inputs

# --- impulse event (schema / validation / backend) ---------------------------


def test_impulse_event_rejects_time_past_duration():
    with pytest.raises(ValueError, match="impulse event time"):
        TaskSpec.model_validate(
            {
                "name": "t",
                "duration": 1.0,
                "impulse_event": {"time": 2.0, "part_id": "torso", "force": [0, 1, 0]},
            }
        )


def test_impulse_event_unknown_part_is_rejected():
    creature = CreatureSpec.model_validate(
        {"name": "c", "parts": [{"id": "box", "shape": "sphere", "radius": 0.1, "mass": 1.0}]}
    )
    task = TaskSpec.model_validate(
        {
            "name": "t",
            "duration": 1.0,
            "impulse_event": {"time": 0.5, "part_id": "ghost", "force": [0, 1, 0]},
        }
    )
    with pytest.raises(EpisodeInputError, match="pushes unknown part"):
        validate_episode_inputs(creature, task)


def test_balance_reward_has_no_objective_warning():
    creature = generate_humanoid(dof=8)
    task = TaskSpec.model_validate(
        {"name": "balance", "duration": 2.0, "reward": {"fall_penalty": 1.0}}
    )
    # fall_penalty counts as an objective, so no "no objective" warning.
    warnings = validate_episode_inputs(creature, task)
    assert not any("no objective" in w for w in warnings)


def test_impulse_event_perturbs_the_body():
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend
    from creature_lab.controllers.sinusoid import sinusoid_targets

    creature = CreatureSpec.model_validate(
        {
            "name": "blk",
            "parts": [{"id": "torso", "shape": "box", "size": [0.3, 0.3, 0.3], "mass": 1.0}],
        }
    )

    def final_y(force) -> float:
        spec = {
            "name": "t",
            "duration": 1.0,
            "timestep": 1 / 60,
            "reward": {"forward_distance": 1.0},
        }
        if force is not None:
            spec["impulse_event"] = {"time": 0.1, "part_id": "torso", "force": force}
        task = TaskSpec.model_validate(spec)
        backend = PyBulletBackend()
        backend.build(creature, task)
        try:
            last = None
            fired = False
            for i in range(task.step_count()):
                backend.apply_motor_targets(sinusoid_targets(creature, i * task.timestep))
                last = backend.step(task.timestep)
                fired = fired or any("impulse" in e for e in last.events)
        finally:
            backend.close()
        return last.parts["torso"].position[1], fired

    baseline_y, _ = final_y(None)
    pushed_y, fired = final_y([0.0, 4000.0, 0.0])
    assert fired  # the impulse event was recorded
    assert pushed_y > baseline_y + 0.1  # a sideways shove moved it in +y


# --- zoo entries --------------------------------------------------------------


def test_humanoid_zoo_entries_exist_and_default_to_stable_balance():
    from creature_lab.zoo import default_task_name, list_zoo_creatures, zoo_tasks

    creatures = list_zoo_creatures()
    assert {"humanoid_minimal", "humanoid_12dof"} <= set(creatures)
    assert set(zoo_tasks("humanoid_minimal")) == {"balance", "walk", "push_recovery"}
    assert default_task_name("humanoid_minimal") == "balance"


def test_humanoid_minimal_runs_and_saves(tmp_path):
    pytest.importorskip("pybullet")
    from typer.testing import CliRunner

    from creature_lab.cli import app

    runs_dir = tmp_path / "runs"
    result = CliRunner().invoke(
        app, ["zoo", "run", "humanoid_minimal", "--runs-dir", str(runs_dir)]
    )
    assert result.exit_code == 0, result.stdout
    assert any(p.is_dir() for p in runs_dir.iterdir())


# --- humanoid-specific diagnosis ----------------------------------------------


def _humanoid() -> CreatureSpec:
    """A minimal humanoid-named creature for diagnosis tests (no physics)."""
    parts = [{"id": "torso", "shape": "box", "size": [0.2, 0.3, 0.5], "mass": 5.0}]
    joints = []
    for side in ("l", "r"):
        parts += [
            {
                "id": f"upper_leg_{side}",
                "shape": "capsule",
                "length": 0.4,
                "radius": 0.05,
                "mass": 1.0,
            },
            {
                "id": f"lower_leg_{side}",
                "shape": "capsule",
                "length": 0.4,
                "radius": 0.05,
                "mass": 1.0,
            },
            {"id": f"foot_{side}", "shape": "capsule", "length": 0.2, "radius": 0.04, "mass": 0.5},
            {
                "id": f"upper_arm_{side}",
                "shape": "capsule",
                "length": 0.3,
                "radius": 0.04,
                "mass": 0.5,
            },
        ]
        joints += [
            {
                "id": f"hip_{side}",
                "parent": "torso",
                "child": f"upper_leg_{side}",
                "type": "hinge",
                "axis": [0, 1, 0],
                "limit": [-1.2, 1.2],
            },
            {
                "id": f"knee_{side}",
                "parent": f"upper_leg_{side}",
                "child": f"lower_leg_{side}",
                "type": "hinge",
                "axis": [0, 1, 0],
                "limit": [-1.2, 1.2],
            },
            {
                "id": f"ankle_{side}",
                "parent": f"lower_leg_{side}",
                "child": f"foot_{side}",
                "type": "hinge",
                "axis": [0, 1, 0],
                "limit": [-1.0, 1.0],
            },
            {
                "id": f"shoulder_{side}",
                "parent": "torso",
                "child": f"upper_arm_{side}",
                "type": "hinge",
                "axis": [0, 1, 0],
                "limit": [-1.5, 1.5],
            },
        ]
    return CreatureSpec.model_validate({"name": "h", "parts": parts, "joints": joints})


def _humanoid_frame(t, *, tipped, contacts, knee=0.0, shoulder=0.0, foot_sep=0.4):
    orn = (0.8, 0.6, 0.0, 0.0) if tipped else (1.0, 0.0, 0.0, 0.0)
    parts = {"torso": {"position": [0.0, 0.0, 0.5], "orientation": list(orn)}}
    for side, sign in (("l", 1.0), ("r", -1.0)):
        y = sign * foot_sep / 2
        for name in (f"upper_leg_{side}", f"lower_leg_{side}", f"foot_{side}", f"upper_arm_{side}"):
            parts[name] = {"position": [0.0, y, 0.2]}
    angles = {}
    for side in ("l", "r"):
        angles[f"knee_{side}"] = knee
        angles[f"shoulder_{side}"] = shoulder
        angles[f"hip_{side}"] = 0.3 * (t % 2)  # legs always move (so total motion > 0)
    return {
        "t": t,
        "parts": parts,
        "joint_angles": angles,
        "contacts": [{"part_id": p, "position": [0, 0, 0]} for p in contacts],
        "score": 0.0,
    }


def _trace(frames) -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": "h",
            "creature_name": "h",
            "task_name": "t",
            "backend": "x",
            "score": 0.0,
            "frames": frames,
        }
    )


def test_biped_asymmetric_fall_detected():
    # Left foot bears all contact; right never touches; the torso has tipped.
    frames = [_humanoid_frame(i * 0.1, tipped=i >= 2, contacts=["foot_l"]) for i in range(20)]
    result = diagnose(_trace(frames), _humanoid())
    assert "biped_asymmetric_fall" in result.patterns


def test_knee_hyperextension_detected():
    # Knees pinned at their +1.2 limit the whole episode.
    frames = [
        _humanoid_frame(i * 0.1, tipped=False, contacts=["foot_l", "foot_r"], knee=1.2)
        for i in range(20)
    ]
    result = diagnose(_trace(frames), _humanoid())
    assert "knee_hyperextension" in result.patterns


def test_arm_swing_absent_detected():
    # Arms never move (shoulder constant) while legs do.
    frames = [
        _humanoid_frame(i * 0.1, tipped=False, contacts=["foot_l", "foot_r"], shoulder=0.0)
        for i in range(20)
    ]
    result = diagnose(_trace(frames), _humanoid())
    assert "arm_swing_absent" in result.patterns


def test_stance_too_narrow_detected():
    frames = [
        _humanoid_frame(i * 0.1, tipped=False, contacts=["foot_l", "foot_r"], foot_sep=0.05)
        for i in range(20)
    ]
    result = diagnose(_trace(frames), _humanoid())
    assert "stance_too_narrow" in result.patterns


def test_humanoid_patterns_skip_non_humanoid():
    # A non-humanoid creature must never get biped/knee/arm/stance patterns.
    creature = CreatureSpec.model_validate(
        {
            "name": "blob",
            "parts": [
                {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
                {"id": "leg_0l", "shape": "capsule", "length": 0.2, "radius": 0.03, "mass": 0.2},
            ],
            "joints": [
                {
                    "id": "hip_0l",
                    "parent": "torso",
                    "child": "leg_0l",
                    "type": "hinge",
                    "axis": [0, 1, 0],
                }
            ],
        }
    )
    frames = [
        {
            "t": i * 0.1,
            "parts": {"torso": {"position": [0, 0, 0.2]}, "leg_0l": {"position": [0, 0, 0]}},
            "contacts": [{"part_id": "leg_0l", "position": [0, 0, 0]}],
            "score": 0.0,
        }
        for i in range(10)
    ]
    result = diagnose(_trace(frames), creature)
    humanoid_only = {
        "biped_asymmetric_fall",
        "knee_hyperextension",
        "arm_swing_absent",
        "stance_too_narrow",
    }
    assert humanoid_only.isdisjoint(result.patterns)
