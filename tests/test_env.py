"""Tests for CreatureEnv and the control schemas."""

import pytest

from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import ActionSpec, CreatureSpec, EpisodeTrace, ObservationSpec, TaskSpec


def _task() -> TaskSpec:
    return TaskSpec.model_validate(
        {"name": "f", "duration": 0.2, "timestep": 1 / 60, "reward": {"forward_distance": 1.0}}
    )


def test_action_spec_rejects_bad_clip_range():
    with pytest.raises(ValueError, match="clip_range minimum"):
        ActionSpec(clip_range=(1.0, -1.0))


def test_old_trace_without_obs_actions_loads():
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "old",
            "creature_name": "c",
            "task_name": "t",
            "backend": "pybullet",
            "score": 0.0,
            "frames": [{"t": 0.0, "parts": {"a": {"position": [0, 0, 0]}}, "score": 0.0}],
        }
    )
    assert trace.frames[0].observations is None
    assert trace.frames[0].actions is None


def test_observation_size_tracks_spec():
    pytest.importorskip("pybullet")
    from creature_lab.env import CreatureEnv

    creature = generate_quadruped()
    minimal = CreatureEnv(
        creature,
        _task(),
        obs_spec=ObservationSpec(
            include_root_pos=True,
            include_root_vel=False,
            include_joint_angles=False,
            include_joint_velocities=False,
        ),
    )
    full = CreatureEnv(
        creature,
        _task(),
        obs_spec=ObservationSpec(include_contacts=True, include_target_vector=True),
    )
    try:
        assert minimal.observation_space["shape"] == (3,)  # root pos only
        assert full.observation_space["shape"][0] > minimal.observation_space["shape"][0]
        assert minimal.reset().shape == (3,)
        assert full.reset().shape == full.observation_space["shape"]
    finally:
        minimal.close()
        full.close()


def test_env_reset_step_close():
    pytest.importorskip("pybullet")
    import numpy as np

    from creature_lab.env import CreatureEnv

    env = CreatureEnv(generate_quadruped(), _task())
    try:
        obs = env.reset(seed=0)
        assert obs.shape == env.observation_space["shape"]
        done = False
        steps = 0
        while not done and steps < 100:
            obs, reward, done, info = env.step(np.zeros(env.action_space["shape"]))
            assert isinstance(reward, float)
            steps += 1
        assert done  # truncates at task.step_count()
        # Recorded frames carry the observation/action that produced them.
        assert env.frames and env.frames[0].observations is not None
        assert env.frames[0].actions is not None
    finally:
        env.close()


def test_env_rejects_wrong_action_length():
    pytest.importorskip("pybullet")
    import numpy as np

    from creature_lab.env import CreatureEnv

    env = CreatureEnv(generate_quadruped(), _task())
    try:
        env.reset()
        with pytest.raises(ValueError, match="expected"):
            env.step(np.zeros(99))
    finally:
        env.close()


def test_env_rejects_non_hinge_action_joints():
    pytest.importorskip("pybullet")
    from creature_lab.env import CreatureEnv

    with pytest.raises(ValueError, match="not hinge joints"):
        CreatureEnv(generate_quadruped(), _task(), action_spec=ActionSpec(joints=["torso"]))


def _motorless_hinge():
    return CreatureSpec.model_validate(
        {
            "name": "nm",
            "parts": [
                {"id": "torso", "shape": "box", "size": [0.3, 0.3, 0.1], "mass": 1.0},
                {"id": "arm", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
            ],
            "joints": [
                {
                    "id": "j",
                    "parent": "torso",
                    "child": "arm",
                    "type": "hinge",
                    "axis": [0, 1, 0],
                    "limit": [-1.5, 1.5],
                }
            ],
            "motors": [],
        }
    )


@pytest.mark.parametrize("mode", ["position", "velocity", "torque"])
def test_env_control_modes_drive_a_motorless_hinge(mode):
    # Regression: the env controls joints directly, so all three modes must move a
    # hinge even when it carries no MotorSpec (apply_motor_targets would ignore it).
    pytest.importorskip("pybullet")
    import numpy as np

    from creature_lab.env import CreatureEnv

    task = TaskSpec.model_validate(
        {"name": "t", "duration": 1.0, "timestep": 1 / 60, "reward": {"forward_distance": 1.0}}
    )
    env = CreatureEnv(_motorless_hinge(), task, action_spec=ActionSpec(mode=mode))
    try:
        env.reset()
        for _ in range(task.step_count()):
            env.step(np.array([1.0]))
        angle = env.frames[-1].joint_angles["j"]
    finally:
        env.close()
    assert angle > 0.3  # a positive command in any mode rotates the joint


def test_pybullet_apply_joint_control_rejects_unknown_mode():
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend

    backend = PyBulletBackend()
    backend.build(generate_quadruped(), _task())
    try:
        with pytest.raises(ValueError, match="unknown control mode"):
            backend.apply_joint_control({"hip_0l": 0.5}, mode="warp")
    finally:
        backend.close()
