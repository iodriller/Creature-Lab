"""A Gymnasium-style environment wrapping a creature, task, and physics backend.

``CreatureEnv`` exposes the standard ``reset() -> obs`` / ``step(action) ->
(obs, reward, done, info)`` loop so a policy (hand-written, RL, or LLM) can drive a
creature step by step. The observation is assembled from the backend's
``FrameState`` according to an :class:`~creature_lab.schema.ObservationSpec`; root and
joint velocities are computed by finite difference, so this stays backend-agnostic
(no engine-specific velocity API required). Actions are mapped onto joints per an
:class:`~creature_lab.schema.ActionSpec`.

The creature *body is the editable part*: the same env code runs any CreatureSpec.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from creature_lab.schema import (
    ActionSpec,
    CreatureSpec,
    FrameState,
    JointType,
    ObservationSpec,
    TaskSpec,
)

if TYPE_CHECKING:
    import numpy as np


def _root_id(creature: CreatureSpec) -> str:
    child_ids = {joint.child for joint in creature.joints}
    return next(part.id for part in creature.parts if part.id not in child_ids)


def _hinge_joint_ids(creature: CreatureSpec) -> list[str]:
    return sorted(j.id for j in creature.joints if j.type == JointType.HINGE)


def default_observation_spec(task: TaskSpec) -> ObservationSpec:
    """The default policy ABI, including task context whenever a target exists."""
    return ObservationSpec(
        include_root_orientation=True,
        include_root_angular_velocity=True,
        include_target_vector=task.target is not None,
    )


def _angular_velocity(
    current: tuple[float, float, float, float],
    previous: tuple[float, float, float, float],
    dt: float,
) -> tuple[float, float, float]:
    """Finite-difference quaternion angular velocity, scalar-first."""
    pw, px, py, pz = previous
    cw, cx, cy, cz = current
    # current * conjugate(previous)
    w = cw * pw + cx * px + cy * py + cz * pz
    x = -cw * px + cx * pw - cy * pz + cz * py
    y = -cw * py + cx * pz + cy * pw - cz * px
    z = -cw * pz - cx * py + cy * px + cz * pw
    if w < 0.0:  # shortest equivalent quaternion arc
        w, x, y, z = -w, -x, -y, -z
    vector_norm = math.sqrt(x * x + y * y + z * z)
    if vector_norm < 1e-12:
        return (0.0, 0.0, 0.0)
    angle = 2.0 * math.atan2(vector_norm, max(-1.0, min(1.0, w)))
    scale = angle / (vector_norm * dt)
    return (x * scale, y * scale, z * scale)


class CreatureEnv:
    """Step-by-step control of a creature through a physics backend."""

    def __init__(
        self,
        creature: CreatureSpec,
        task: TaskSpec,
        *,
        obs_spec: ObservationSpec | None = None,
        action_spec: ActionSpec | None = None,
        backend: Any | None = None,
    ) -> None:
        self.creature = creature
        self.task = task
        self.obs_spec = obs_spec or default_observation_spec(task)
        self.action_spec = action_spec or ActionSpec()

        self._hinges = _hinge_joint_ids(creature)
        self._controlled = self.action_spec.joints or list(self._hinges)
        unknown = set(self._controlled) - set(self._hinges)
        if unknown:
            raise ValueError(f"action joints are not hinge joints: {sorted(unknown)}")
        self._limits = {j.id: j.limit for j in creature.joints}
        self._root = _root_id(creature)
        self._part_ids = [p.id for p in creature.parts]

        if backend is None:
            from creature_lab.backends.pybullet_backend import PyBulletBackend

            backend = PyBulletBackend()
        self._backend = backend

        self._steps = 0
        self._prev_score = 0.0
        self._prev_frame: FrameState | None = None
        #: Recorded frames with observations/actions attached (for saving as a trace).
        self.frames: list[FrameState] = []

    # -- spaces -----------------------------------------------------------------

    @property
    def action_space(self) -> dict[str, Any]:
        lo, hi = self.action_spec.clip_range
        return {"shape": (len(self._controlled),), "low": lo, "high": hi}

    @property
    def observation_space(self) -> dict[str, Any]:
        return {"shape": (self._obs_size(),), "low": float("-inf"), "high": float("inf")}

    def _obs_size(self) -> int:
        spec = self.obs_spec
        size = 0
        size += 3 if spec.include_root_pos else 0
        size += 4 if spec.include_root_orientation else 0
        size += 3 if spec.include_root_vel else 0
        size += 3 if spec.include_root_angular_velocity else 0
        size += len(self._hinges) if spec.include_joint_angles else 0
        size += len(self._hinges) if spec.include_joint_velocities else 0
        size += len(self._part_ids) if spec.include_contacts else 0
        size += 3 if spec.include_target_vector else 0
        return size

    # -- gym loop ---------------------------------------------------------------

    def reset(self, seed: int | None = None) -> np.ndarray:
        """Rebuild the episode and return the initial observation."""
        self._backend.build(self.creature, self.task, seed=seed)
        self._steps = 0
        self._prev_score = 0.0
        self._prev_frame = None
        self.frames = []
        frame = self._backend.observe()
        obs = self._observation(frame, prev=None)
        self._prev_frame = frame
        return obs

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict[str, Any]]:
        """Apply an action, advance one timestep, and return (obs, reward, done, info)."""
        import numpy as np

        action = np.asarray(action, dtype=float).reshape(-1)
        clipped_action = self._clip_action(action)
        targets = self._action_to_targets(clipped_action)
        self._apply(targets)

        frame = self._backend.step(self.task.timestep)
        self._steps += 1

        obs = self._observation(frame, prev=self._prev_frame)
        reward = frame.score - self._prev_score
        terminated = self._fallen(frame)
        truncated = self._steps >= self.task.step_count()
        done = terminated or truncated
        info = {
            "score": frame.score,
            "step": self._steps,
            "terminated": terminated,
            "truncated": truncated,
        }

        recorded = frame.model_copy(
            update={"observations": obs.tolist(), "actions": clipped_action.tolist()}
        )
        self.frames.append(recorded)
        self._prev_score = frame.score
        self._prev_frame = frame
        return obs, reward, done, info

    def close(self) -> None:
        self._backend.close()

    # -- mapping helpers --------------------------------------------------------

    def _action_to_targets(self, action: np.ndarray) -> dict[str, float]:
        if action.shape[0] != len(self._controlled):
            raise ValueError(
                f"action has {action.shape[0]} values, expected {len(self._controlled)}"
            )
        lo, hi = self.action_spec.clip_range
        targets: dict[str, float] = {}
        for value, joint_id in zip(action, self._controlled, strict=True):
            clipped = max(lo, min(hi, float(value)))
            if self.action_spec.mode == "position":
                limit = self._limits.get(joint_id) or (-3.141592653589793, 3.141592653589793)
                frac = (clipped - lo) / (hi - lo)
                targets[joint_id] = limit[0] + frac * (limit[1] - limit[0])
            else:
                # velocity/torque modes pass the (clipped) command straight through.
                targets[joint_id] = clipped
        return targets

    def _clip_action(self, action: np.ndarray) -> np.ndarray:
        import numpy as np

        if action.shape[0] != len(self._controlled):
            raise ValueError(
                f"action has {action.shape[0]} values, expected {len(self._controlled)}"
            )
        lo, hi = self.action_spec.clip_range
        return np.clip(action, lo, hi)

    def _apply(self, targets: dict[str, float]) -> None:
        mode = self.action_spec.mode
        if hasattr(self._backend, "apply_joint_control"):
            # Drives joints by id (works for hinges with or without a MotorSpec) and
            # honours position/velocity/torque modes.
            self._backend.apply_joint_control(targets, mode=mode)
        elif mode == "position":
            self._backend.apply_motor_targets(targets)
        else:
            raise NotImplementedError(f"this backend supports position control only, not {mode!r}")

    def _fallen(self, frame: FrameState) -> bool:
        pose = frame.parts.get(self._root)
        if pose is None:
            return False
        _, x, y, _ = pose.orientation
        return (1 - 2 * (x * x + y * y)) < 0.5

    def _observation(self, frame: FrameState, prev: FrameState | None) -> np.ndarray:
        import numpy as np

        spec = self.obs_spec
        dt = self.task.timestep
        values: list[float] = []
        root_pos = frame.parts[self._root].position
        root_orientation = frame.parts[self._root].orientation

        if spec.include_root_pos:
            values.extend(root_pos)
        if spec.include_root_orientation:
            values.extend(root_orientation)
        if spec.include_root_vel:
            if prev is not None:
                prev_pos = prev.parts[self._root].position
                values.extend((root_pos[i] - prev_pos[i]) / dt for i in range(3))
            else:
                values.extend((0.0, 0.0, 0.0))
        if spec.include_root_angular_velocity:
            if prev is not None:
                values.extend(
                    _angular_velocity(root_orientation, prev.parts[self._root].orientation, dt)
                )
            else:
                values.extend((0.0, 0.0, 0.0))
        if spec.include_joint_angles:
            values.extend(frame.joint_angles.get(j, 0.0) for j in self._hinges)
        if spec.include_joint_velocities:
            for j in self._hinges:
                now = frame.joint_angles.get(j, 0.0)
                was = prev.joint_angles.get(j, 0.0) if prev is not None else now
                values.append((now - was) / dt)
        if spec.include_contacts:
            touching = {c.part_id for c in frame.contacts}
            values.extend(1.0 if pid in touching else 0.0 for pid in self._part_ids)
        if spec.include_target_vector:
            if self.task.target is not None:
                tgt = self.task.target.position
                values.extend(tgt[i] - root_pos[i] for i in range(3))
            else:
                values.extend((0.0, 0.0, 0.0))
        return np.asarray(values, dtype=float)
