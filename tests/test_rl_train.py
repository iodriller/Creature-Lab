"""Tests for the PPO training driver (creature_lab.rl.train)."""

from __future__ import annotations

import pytest

from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import TaskSpec


def _task(duration: float = 0.5) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "name": "train_test",
            "duration": duration,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "reward": {"forward_distance": 1.0},
        }
    )


def test_evaluate_mean_return_with_a_fixed_action_policy():
    """A fake 'policy' that always predicts the zero action should behave
    deterministically and not crash the eval loop - proves the harness works
    without needing a real trained model for every test."""
    pytest.importorskip("gymnasium")
    pytest.importorskip("pybullet")
    import numpy as np

    from creature_lab.rl.train import evaluate_mean_return

    class _ZeroPolicy:
        def predict(self, obs, deterministic=True):
            return np.zeros(4), None

    creature = generate_quadruped()
    task = _task()
    mean_return = evaluate_mean_return(_ZeroPolicy(), creature, task, episodes=2, seed=0)
    assert isinstance(mean_return, float)


def test_evaluate_mean_return_random_baseline_is_reproducible_given_a_fixed_seed():
    pytest.importorskip("gymnasium")
    pytest.importorskip("pybullet")
    from creature_lab.rl.train import evaluate_mean_return

    creature = generate_quadruped()
    task = _task()
    a = evaluate_mean_return(None, creature, task, episodes=2, seed=42)
    b = evaluate_mean_return(None, creature, task, episodes=2, seed=42)
    assert a == b


def test_train_ppo_runs_and_returns_measured_results():
    """Real (tiny) end-to-end training: proves the pipeline works without asserting
    a specific improvement (PPO's default rollout batch is 2048 steps regardless of
    how small `timesteps` is set, so this is already the practical cost floor)."""
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("pybullet")
    from creature_lab.rl.train import train_ppo

    creature = generate_quadruped()
    task = _task(duration=0.2)  # short episodes -> more of them per rollout
    result = train_ppo(creature, task, timesteps=256, seed=0, eval_episodes=2)

    assert result.timesteps == 256
    assert result.eval_episodes == 2
    assert isinstance(result.baseline_mean_return, float)
    assert isinstance(result.trained_mean_return, float)
    assert result.model is not None


def test_train_ppo_model_can_predict_an_action_matching_the_action_space():
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("pybullet")
    import numpy as np

    from creature_lab.rl.gym_env import CreatureGymEnv
    from creature_lab.rl.train import train_ppo

    creature = generate_quadruped()
    task = _task(duration=0.2)
    result = train_ppo(creature, task, timesteps=256, seed=0, eval_episodes=1)

    env = CreatureGymEnv(creature, task)
    obs, _info = env.reset(seed=0)
    action, _state = result.model.predict(obs, deterministic=True)
    assert np.asarray(action).shape == env.action_space.shape
    env.close()
