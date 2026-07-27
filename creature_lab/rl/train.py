"""PPO training driver over :class:`~creature_lab.rl.gym_env.CreatureGymEnv`.

Grand Plan Phase 5, Tier 3: a creature learning to move through
:class:`~creature_lab.env.CreatureEnv`, rather than a hand-tuned open-loop gait
(Tier 1) or hand-tuned feedback (Tier 2). Deliberately scoped honestly (see
``docs/project/GRAND_PLAN.md``): this is a working training loop that measurably improves a
locomotion metric over a random baseline, not a promise of a polished walker -
real bipedal walking is a research problem, not a short-training-run outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from creature_lab.schema import ActionSpec, CreatureSpec, ObservationSpec, TaskSpec


@dataclass(frozen=True)
class TrainResult:
    """A trained model plus before/after evidence, so ``train`` never has to just
    assert the training "worked" - the mean returns are measured, not assumed."""

    model: Any  # stable_baselines3.PPO
    timesteps: int
    eval_episodes: int
    baseline_mean_return: float  # a random policy, same env/seeds
    trained_mean_return: float
    observation_spec: ObservationSpec
    action_spec: ActionSpec
    evaluation_seed: int


def evaluate_mean_return(
    policy: Any | None,
    creature: CreatureSpec,
    task: TaskSpec,
    *,
    episodes: int,
    seed: int,
    obs_spec: ObservationSpec | None = None,
    action_spec: ActionSpec | None = None,
    deterministic: bool = True,
) -> float:
    """Mean total episodic reward over ``episodes`` real rollouts.

    ``policy=None`` means "sample random actions" - the baseline every trained
    policy must be measured against, since a positive score alone proves nothing
    without a comparison point.
    """
    import numpy as np

    from creature_lab.rl.gym_env import CreatureGymEnv

    if episodes < 1:
        raise ValueError("episodes must be at least 1")
    env = CreatureGymEnv(creature, task, obs_spec=obs_spec, action_spec=action_spec)
    # `env.reset(seed=...)` seeds CreatureEnv's own physics reset and gymnasium.Env's
    # `self.np_random`, but NOT `action_space.sample()`'s RNG - that needs its own
    # explicit seed, or the "random" baseline isn't reproducible run to run.
    env.action_space.seed(seed)
    returns: list[float] = []
    try:
        for episode in range(episodes):
            obs, _info = env.reset(seed=seed + episode)
            total = 0.0
            done = False
            while not done:
                if policy is None:
                    action = env.action_space.sample()
                else:
                    action, _state = policy.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, _info = env.step(action)
                total += reward
                done = terminated or truncated
            returns.append(total)
    finally:
        env.close()
    return float(np.mean(returns))


def train_ppo(
    creature: CreatureSpec,
    task: TaskSpec,
    *,
    timesteps: int = 20_000,
    seed: int = 0,
    eval_episodes: int = 3,
    obs_spec: ObservationSpec | None = None,
    action_spec: ActionSpec | None = None,
) -> TrainResult:
    """Train a PPO policy on ``creature``/``task`` and measure it against a random
    baseline on the same env/eval seeds. Needs the ``rl`` extra."""
    if timesteps < 1:
        raise ValueError("timesteps must be at least 1")
    if eval_episodes < 1:
        raise ValueError("eval_episodes must be at least 1")
    from creature_lab.env import default_observation_spec

    resolved_observation = obs_spec or default_observation_spec(task)
    resolved_action = action_spec or ActionSpec()

    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise ImportError(
            "creature_lab.rl.train needs the 'rl' extra - `uv sync --extra rl`"
        ) from exc
    from creature_lab.rl.gym_env import CreatureGymEnv

    evaluation_seed = seed + 10_000
    baseline = evaluate_mean_return(
        None,
        creature,
        task,
        episodes=eval_episodes,
        seed=evaluation_seed,
        obs_spec=resolved_observation,
        action_spec=resolved_action,
    )

    env = CreatureGymEnv(creature, task, obs_spec=resolved_observation, action_spec=resolved_action)
    try:
        model = PPO("MlpPolicy", env, seed=seed, verbose=0)
        model.learn(total_timesteps=timesteps)
    finally:
        env.close()

    trained = evaluate_mean_return(
        model,
        creature,
        task,
        episodes=eval_episodes,
        seed=evaluation_seed,
        obs_spec=resolved_observation,
        action_spec=resolved_action,
    )

    return TrainResult(
        model=model,
        timesteps=timesteps,
        eval_episodes=eval_episodes,
        baseline_mean_return=baseline,
        trained_mean_return=trained,
        observation_spec=resolved_observation,
        action_spec=resolved_action,
        evaluation_seed=evaluation_seed,
    )
