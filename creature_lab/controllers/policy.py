"""Drive a creature with a trained Stable-Baselines3 policy (Grand Plan Phase 5,
Tier 3), through the same ``(t, prev_frame) -> targets`` interface every other
controller uses - so a trained policy composes with ``run``/``qualify``/``robustness``/
the editor exactly like ``sinusoid``/``cpg``/``target_seek``/``posture`` do.

Needs the optional ``rl`` extra (``uv sync --extra rl``) to *load and run* a policy -
not to define the ``ControllerSpec``/``ControllerType.POLICY`` schema, which stays
dependency-free like every other controller type.

Architectural note: :class:`~creature_lab.env.CreatureEnv` owns its own physics
stepping (``env.step(action)`` advances the backend internally), which does not fit
this codebase's controller convention of a passive ``(t, prev_frame) -> targets``
callable driven by an *external* stepping loop (``cli._simulate``). Rather than
double-stepping physics, this reuses ``CreatureEnv``'s own observation/action
translation helpers directly (they are pure data transforms - they never touch the
physics backend) and tracks its own two-frame history the same way
:class:`~creature_lab.controllers.posture.PostureController` tracks lean history, so
the exact same finite-difference velocity terms ``CreatureEnv`` computes during
training are reproduced at inference time.
"""

from __future__ import annotations

from pathlib import Path

from creature_lab.env import CreatureEnv
from creature_lab.schema import ActionSpec, CreatureSpec, FrameState, ObservationSpec, TaskSpec


class PolicyController:
    """Loads a saved SB3 model (e.g. ``PPO.save()``'s zip) and predicts joint targets
    from it each step. Deterministic given a fixed model and ``deterministic=True``
    (SB3's default policy-evaluation mode); call :meth:`reset` between episodes.
    """

    def __init__(
        self,
        creature: CreatureSpec,
        task: TaskSpec,
        policy_path: str | Path,
        *,
        deterministic: bool = True,
        obs_spec: ObservationSpec | None = None,
        action_spec: ActionSpec | None = None,
    ) -> None:
        try:
            from stable_baselines3 import PPO
        except ImportError as exc:
            raise ImportError(
                "PolicyController needs the 'rl' extra - `uv sync --extra rl`"
            ) from exc
        self._model = PPO.load(str(policy_path))
        # Never stepped/reset - used only for its pure obs/action translation logic,
        # which must match training exactly (same obs_spec/action_spec).
        self._helper_env = CreatureEnv(creature, task, obs_spec=obs_spec, action_spec=action_spec)
        expected_observation = self._helper_env.observation_space["shape"]
        expected_action = self._helper_env.action_space["shape"]
        model_observation = tuple(self._model.observation_space.shape)
        model_action = tuple(self._model.action_space.shape)
        if model_observation != expected_observation:
            raise ValueError(
                "policy observation ABI mismatch: "
                f"model expects {model_observation}, controller defines {expected_observation}"
            )
        if model_action != expected_action:
            raise ValueError(
                "policy action ABI mismatch: "
                f"model expects {model_action}, controller defines {expected_action}"
            )
        self._deterministic = deterministic
        self._prev_prev_frame: FrameState | None = None

    def reset(self) -> None:
        self._prev_prev_frame = None

    def __call__(self, t: float, prev_frame: FrameState | None = None) -> dict[str, float]:
        if prev_frame is None:
            # No pose yet (first call before any physics step) - hold neutral targets
            # until there's a frame to build an observation from, matching how
            # target_seek/posture handle their own first call.
            return dict.fromkeys(self._helper_env._controlled, 0.0)

        import numpy as np

        obs = self._helper_env._observation(prev_frame, prev=self._prev_prev_frame)
        action, _state = self._model.predict(obs, deterministic=self._deterministic)
        self._prev_prev_frame = prev_frame
        # Match CreatureEnv.step()'s own action preprocessing exactly (predict() can
        # return a batched (1, n) array; _action_to_targets expects flat (n,)).
        action = np.asarray(action, dtype=float).reshape(-1)
        return self._helper_env._action_to_targets(action)
