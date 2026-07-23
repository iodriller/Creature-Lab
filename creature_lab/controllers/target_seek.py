"""Target-seeking gait controller: CPG gait + heading-error steering + stop radius.

This is the fix for Creature Lab's central controller gap: a task's target can score
an episode, but the built-in open-loop gaits (``sinusoid``, ``cpg``) never turn toward
it. This wraps a :class:`~creature_lab.controllers.cpg.CPGController` with a
deterministic steering layer instead of inventing a new locomotion policy:

    base CPG gait + heading-error steering + target-distance speed scaling + stop radius

No learned model and no LLM - just trigonometry over the previous frame's root pose
and the task's target, so behavior is reproducible for a fixed seed/backend.

Steering assumes the usual scaffold convention: joints on the left side of the body
end their id in ``l`` (``hip_0l``, ``knee_l``, ...) and the right side in ``r``. Joints
that don't match either (e.g. a worm's ``seg``-chain joints) are left at the base gait's
output - they still walk, they just don't turn.
"""

from __future__ import annotations

import math

from creature_lab.controllers.cpg import CPGController
from creature_lab.schema import CreatureSpec, FrameState, TaskSpec


def _root_id(creature: CreatureSpec) -> str:
    child_ids = {joint.child for joint in creature.joints}
    return next(part.id for part in creature.parts if part.id not in child_ids)


def can_steer(creature: CreatureSpec) -> bool:
    """Whether any motored joint has a recognized left/right suffix (see module docstring).

    A creature that fails this (e.g. a worm's ``seg``-chain, or a custom-loaded
    creature with unrelated naming) will still walk under ``TargetSeekController``,
    but the steering term never applies - it just runs the base gait straight. Used
    to warn about that up front rather than let it be a silent surprise.
    """
    return any(motor.joint.endswith(("l", "r")) for motor in creature.motors)


def _forward_xy(orientation: tuple[float, float, float, float]) -> tuple[float, float]:
    """World-frame (x, y) of the root's local +X (forward) axis.

    ``orientation`` is the schema's scalar-first ``(w, x, y, z)`` quaternion, the same
    local-to-world rotation the backends report in ``FrameState``. Only the horizontal
    component is needed for heading.
    """
    w, x, y, z = orientation
    fx = 1 - 2 * (y * y + z * z)
    fy = 2 * (x * y + z * w)
    return fx, fy


def _wrap_to_pi(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi


class TargetSeekController:
    """Steers a CPG gait toward ``task.target``, slowing and stopping near it.

    Deterministic and stateful like :class:`CPGController` (call once per timestep in
    increasing ``t`` order). Raises ``ValueError`` at construction if the task has no
    target - there is nothing to seek.
    """

    def __init__(
        self,
        creature: CreatureSpec,
        task: TaskSpec,
        *,
        turn_gain: float = 1.2,
        max_turn_scale: float = 0.8,
        slow_radius: float = 1.0,
        stop_radius: float | None = None,
        cpg: CPGController | None = None,
    ) -> None:
        if task.target is None:
            raise ValueError("target_seek controller requires a task with a target")
        self.creature = creature
        self.task = task
        self.turn_gain = turn_gain
        self.max_turn_scale = max_turn_scale
        self.slow_radius = slow_radius
        #: Distance at which the gait is fully damped to a stop; defaults to the
        #: target's own radius, so "reached" and "stopped" agree.
        self.stop_radius = stop_radius if stop_radius is not None else task.target.radius
        self._cpg = cpg or CPGController(creature)
        self._root = _root_id(creature)

    def reset(self) -> None:
        self._cpg.reset()

    def __call__(self, t: float, prev_frame: FrameState | None = None) -> dict[str, float]:
        base = self._cpg(t, prev_frame)
        if prev_frame is None or self._root not in prev_frame.parts:
            # No pose yet (first call before any physics step) - just walk straight
            # until there's a frame to steer from.
            return base

        root_pose = prev_frame.parts[self._root]
        target_pos = self.task.target.position
        dx = target_pos[0] - root_pose.position[0]
        dy = target_pos[1] - root_pose.position[1]
        distance = math.hypot(dx, dy)

        forward_x, forward_y = _forward_xy(root_pose.orientation)
        heading_error = _wrap_to_pi(math.atan2(dy, dx) - math.atan2(forward_y, forward_x))
        turn = max(-self.max_turn_scale, min(self.max_turn_scale, self.turn_gain * heading_error))

        if distance <= self.stop_radius:
            speed_scale = 0.0
        elif distance <= self.slow_radius:
            speed_scale = distance / self.slow_radius
        else:
            speed_scale = 1.0

        targets: dict[str, float] = {}
        for joint_id, value in base.items():
            if joint_id.endswith("l"):
                side_scale = 1.0 - turn
            elif joint_id.endswith("r"):
                side_scale = 1.0 + turn
            else:
                side_scale = 1.0
            targets[joint_id] = value * speed_scale * side_scale
        return targets
