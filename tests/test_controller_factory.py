"""Tests for building runtime controllers from a portable ControllerSpec."""

from __future__ import annotations

import math

import pytest

from creature_lab.controllers.cpg import CPGController
from creature_lab.controllers.factory import build_controller, extract_sinusoid_spec
from creature_lab.controllers.sinusoid import sinusoid_targets
from creature_lab.controllers.target_seek import TargetSeekController
from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import ControllerSpec, ControllerType, TaskSpec


def _task_with_target(target_xy: tuple[float, float], *, duration: float = 3.0) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "name": "reach",
            "duration": duration,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "target": {"position": [target_xy[0], target_xy[1], 0.15], "radius": 0.15},
            "reward": {"target_distance": 1.0},
        }
    )


# -- sinusoid --------------------------------------------------------------------


def test_build_sinusoid_controller_matches_sinusoid_targets():
    creature = generate_quadruped()
    spec = ControllerSpec.model_validate(
        {
            "type": "sinusoid",
            "motors": [
                {
                    "joint": m.joint,
                    "amplitude": m.amplitude,
                    "frequency": m.frequency,
                    "phase": m.phase,
                }
                for m in creature.motors
            ],
        }
    )
    controller = build_controller(spec, creature)

    for t in (0.0, 0.1, 0.37, 1.2):
        assert controller(t) == sinusoid_targets(creature, t)


def test_sinusoid_controller_applies_center_offset():
    creature = generate_quadruped()
    joint = creature.motors[0].joint
    spec = ControllerSpec.model_validate(
        {
            "type": "sinusoid",
            "motors": [{"joint": joint, "amplitude": 0.0, "frequency": 1.0, "offset": -0.25}],
        }
    )

    assert build_controller(spec, creature)(0.0)[joint] == pytest.approx(-0.25)


# -- cpg -----------------------------------------------------------------------


def test_build_cpg_controller_with_no_overrides_matches_bare_cpg():
    creature = generate_quadruped()
    spec = ControllerSpec.model_validate({"type": "cpg"})
    built = build_controller(spec, creature)
    bare = CPGController(creature)

    for t in (0.0, 0.05, 0.1, 0.2):
        assert built(t) == bare(t)


def test_build_cpg_controller_applies_overrides():
    creature = generate_quadruped()
    spec = ControllerSpec.model_validate({"type": "cpg", "amplitude": 0.1})
    built = build_controller(spec, creature)
    bare = CPGController(creature, amplitude=0.1)

    for t in (0.0, 0.05, 0.1):
        assert built(t) == bare(t)

    # Amplitude 0.1 vs the CPGController default of 0.8 must actually differ.
    default = CPGController(creature)
    assert built(0.1) != default(0.1)


# -- target_seek -----------------------------------------------------------------


def test_build_target_seek_requires_a_target_task():
    creature = generate_quadruped()
    spec = ControllerSpec.model_validate({"type": "target_seek"})
    no_target_task = TaskSpec.model_validate({"name": "t", "duration": 1.0})

    with pytest.raises(ValueError, match="requires a task with a target"):
        build_controller(spec, creature, no_target_task)

    with pytest.raises(ValueError, match="requires a task with a target"):
        build_controller(spec, creature, None)


def test_build_target_seek_controller_steers_via_real_physics():
    """End-to-end: ControllerSpec -> build_controller -> real PyBullet steering,
    not just object construction - the same scenario test_controllers.py already
    proves for the class directly, run here through the spec-based factory path."""
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend
    from creature_lab.controllers.target_seek import _forward_xy, _wrap_to_pi

    creature = generate_quadruped()
    target_xy = (0.0, 1.5)
    task = _task_with_target(target_xy)
    spec = ControllerSpec.model_validate({"type": "target_seek"})
    controller = build_controller(spec, creature, task)

    backend = PyBulletBackend()
    backend.build(creature, task)
    prev = None
    try:
        for i in range(task.step_count()):
            backend.apply_motor_targets(controller(i * task.timestep, prev))
            prev = backend.step(task.timestep)
    finally:
        backend.close()

    pose = prev.parts["torso"]
    dx, dy = target_xy[0] - pose.position[0], target_xy[1] - pose.position[1]
    fx, fy = _forward_xy(pose.orientation)
    final_error = abs(_wrap_to_pi(math.atan2(dy, dx) - math.atan2(fy, fx)))
    initial_error = abs(math.atan2(target_xy[1], target_xy[0]))
    assert final_error < initial_error - 0.3


def test_build_target_seek_applies_steering_overrides():
    creature = generate_quadruped()
    task = _task_with_target((1.0, 1.0))
    spec = ControllerSpec.model_validate({"type": "target_seek", "turn_gain": 5.0})
    built = build_controller(spec, creature, task)
    bare = TargetSeekController(creature, task, turn_gain=5.0)

    frame = None
    assert built(0.0, frame) == bare(0.0, frame)


def test_build_unknown_type_string_is_rejected_by_the_schema_itself():
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError, not ours to name here
        ControllerSpec.model_validate({"type": "not_a_real_controller"})


# -- posture ---------------------------------------------------------------------


def test_build_posture_controller_with_no_overrides_matches_bare_posture():
    from creature_lab.controllers.posture import PostureController

    creature = generate_quadruped()
    spec = ControllerSpec.model_validate({"type": "posture"})
    built = build_controller(spec, creature)
    bare = PostureController(creature)

    frame = None
    assert built(0.0, frame) == bare(0.0, frame)


def test_build_posture_controller_applies_overrides():
    from creature_lab.controllers.posture import PostureController
    from creature_lab.schema import FrameState

    creature = generate_quadruped()
    spec = ControllerSpec.model_validate({"type": "posture", "kp": 4.0, "kd": 0.5})
    built = build_controller(spec, creature)
    bare = PostureController(creature, kp=4.0, kd=0.5)

    # gains only affect output once there's a real (tilted) prev_frame to correct.
    torso_pose = {"position": [0, 0, 0.2], "orientation": [0.9, 0.1, 0.1, 0.1]}
    tilted = FrameState.model_validate({"t": 0.0, "parts": {"torso": torso_pose}})
    assert built(0.02, tilted) == bare(0.02, tilted)

    default = PostureController(creature)  # gain=40 by default -> must differ from kp=4
    assert built(0.02, tilted) != default(0.02, tilted)


# -- policy ------------------------------------------------------------------------


def test_build_policy_controller_requires_a_task():
    pytest.importorskip("stable_baselines3")
    creature = generate_quadruped()
    spec = ControllerSpec.model_validate({"type": "policy", "policy_file": "policy.zip"})
    with pytest.raises(ValueError, match="requires a task"):
        build_controller(spec, creature, None)


def test_build_policy_controller_missing_file_is_a_clean_error(tmp_path):
    pytest.importorskip("stable_baselines3")
    creature = generate_quadruped()
    task = _task_with_target((1.0, 0.0))
    spec = ControllerSpec.model_validate({"type": "policy", "policy_file": "nope.zip"})
    with pytest.raises(ValueError, match="not found"):
        build_controller(spec, creature, task, base_dir=tmp_path)


def test_build_policy_controller_resolves_policy_file_relative_to_base_dir(tmp_path):
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("pybullet")
    from creature_lab.rl.train import train_ppo

    creature = generate_quadruped()
    task = TaskSpec.model_validate(
        {
            "name": "t",
            "duration": 0.2,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "reward": {"forward_distance": 1.0},
        }
    )
    result = train_ppo(creature, task, timesteps=256, seed=0, eval_episodes=1)
    result.model.save(str(tmp_path / "policy.zip"))

    spec = ControllerSpec.model_validate({"type": "policy", "policy_file": "policy.zip"})
    controller = build_controller(spec, creature, task, base_dir=tmp_path)
    targets = controller(0.0, None)
    assert set(targets) == {m.joint for m in creature.motors}


# -- extract_sinusoid_spec ---------------------------------------------------------


def test_extract_sinusoid_spec_reproduces_the_creatures_own_gait():
    creature = generate_quadruped()
    spec = extract_sinusoid_spec(creature)

    assert spec.type == ControllerType.SINUSOID
    built = build_controller(spec, creature)
    for t in (0.0, 0.1, 0.5):
        assert built(t) == sinusoid_targets(creature, t)


def test_extract_sinusoid_spec_rejects_a_creature_with_no_motors():
    from creature_lab.schema import CreatureSpec

    creature = CreatureSpec.model_validate(
        {"name": "still", "parts": [{"id": "torso", "shape": "sphere", "radius": 0.1, "mass": 1.0}]}
    )
    with pytest.raises(ValueError, match="no motors"):
        extract_sinusoid_spec(creature)


def test_extract_sinusoid_spec_round_trips_through_json():
    creature = generate_quadruped()
    spec = extract_sinusoid_spec(creature, name="quad_gait")

    restored = ControllerSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
    assert restored.name == "quad_gait"
