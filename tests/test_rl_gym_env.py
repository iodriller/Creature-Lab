"""Tests for the CreatureGymEnv gymnasium.Env adapter."""

from __future__ import annotations

import pytest

from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import TaskSpec


def _task(duration: float = 0.5) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "name": "gym_test",
            "duration": duration,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "reward": {"forward_distance": 1.0},
        }
    )


def test_creature_gym_env_passes_gymnasium_check_env():
    pytest.importorskip("gymnasium")
    pytest.importorskip("pybullet")
    from gymnasium.utils.env_checker import check_env

    from creature_lab.rl.gym_env import CreatureGymEnv

    env = CreatureGymEnv(generate_quadruped(), _task())
    check_env(env, skip_render_check=True)


def test_creature_gym_env_spaces_match_creature_env():
    pytest.importorskip("gymnasium")
    pytest.importorskip("pybullet")
    from creature_lab.env import CreatureEnv
    from creature_lab.rl.gym_env import CreatureGymEnv

    creature = generate_quadruped()
    task = _task()
    plain = CreatureEnv(creature, task)
    wrapped = CreatureGymEnv(creature, task)

    assert wrapped.action_space.shape == plain.action_space["shape"]
    assert wrapped.observation_space.shape == plain.observation_space["shape"]


def test_creature_gym_env_reset_returns_obs_and_info_tuple():
    pytest.importorskip("gymnasium")
    pytest.importorskip("pybullet")
    from creature_lab.rl.gym_env import CreatureGymEnv

    env = CreatureGymEnv(generate_quadruped(), _task())
    try:
        result = env.reset(seed=0)
        assert isinstance(result, tuple) and len(result) == 2
        obs, info = result
        assert obs.shape == env.observation_space.shape
        assert isinstance(info, dict)
    finally:
        env.close()


def test_creature_gym_env_step_returns_five_tuple_with_split_terminated_truncated():
    pytest.importorskip("gymnasium")
    pytest.importorskip("pybullet")
    from creature_lab.rl.gym_env import CreatureGymEnv

    env = CreatureGymEnv(generate_quadruped(), _task(duration=0.05))  # 3 steps
    try:
        env.reset(seed=0)
        result = env.step(env.action_space.sample())
        assert len(result) == 5
        _obs, reward, terminated, truncated, info = result
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)

        # Run to the end of the (very short) episode: truncated should fire.
        done = False
        for _ in range(10):
            _obs, _reward, terminated, truncated, info = env.step(env.action_space.sample())
            done = terminated or truncated
            if done:
                break
        assert done
    finally:
        env.close()
