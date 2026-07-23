"""Real ``gymnasium.Env`` adapter around :class:`~creature_lab.env.CreatureEnv`.

``CreatureEnv`` is deliberately **not** a ``gymnasium.Env`` itself: its
``reset()``/``step()`` are an older, already-tested plain-obs / 4-tuple API (see
``tests/test_env.py``) used by any hand-written policy loop, and changing that
signature in place would break existing, real callers. Stable-Baselines3 requires the
real Gymnasium contract instead - ``reset() -> (obs, info)``,
``step() -> (obs, reward, terminated, truncated, info)``, and proper
``gymnasium.spaces.Box`` action/observation spaces - so this wraps ``CreatureEnv``
rather than modifying it. ``CreatureEnv.step()`` already computes ``terminated``/
``truncated`` separately internally (it just merges them into one ``done`` for its own
return value), so no logic is duplicated here - only translated.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from creature_lab.env import CreatureEnv
from creature_lab.schema import ActionSpec, CreatureSpec, ObservationSpec, TaskSpec


class CreatureGymEnv(gym.Env):
    """Drives one ``CreatureEnv`` episode per reset, as a standard Gymnasium env."""

    metadata: dict[str, Any] = {"render_modes": []}

    def __init__(
        self,
        creature: CreatureSpec,
        task: TaskSpec,
        *,
        obs_spec: ObservationSpec | None = None,
        action_spec: ActionSpec | None = None,
        backend: Any | None = None,
    ) -> None:
        super().__init__()
        self.env = CreatureEnv(
            creature, task, obs_spec=obs_spec, action_spec=action_spec, backend=backend
        )
        action_meta = self.env.action_space
        obs_meta = self.env.observation_space
        self.action_space = spaces.Box(
            low=float(action_meta["low"]),
            high=float(action_meta["high"]),
            shape=action_meta["shape"],
            dtype=np.float32,
        )
        self.observation_space = spaces.Box(
            low=-np.finfo(np.float32).max,
            high=np.finfo(np.float32).max,
            shape=obs_meta["shape"],
            dtype=np.float32,
        )

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        obs = self.env.reset(seed=seed)
        return obs.astype(np.float32), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        obs, reward, _done, info = self.env.step(action)
        terminated = bool(info["terminated"])
        truncated = bool(info["truncated"])
        return obs.astype(np.float32), float(reward), terminated, truncated, info

    def close(self) -> None:
        self.env.close()
