"""Closed-loop posture/balance controller: PD feedback on root pitch.

This is Creature Lab's first controller that actually senses and corrects rather
than blindly playing a waveform (see ``docs/GRAND_PLAN.md`` Phase 5, Tier 2). It
reads the previous frame's root orientation, estimates forward/backward lean and its
rate of change, and applies a corrective offset to hip (and knee/ankle, if present)
joint targets on top of an optional base pose or gait - the same "read prev_frame,
correct this step" pattern :class:`~creature_lab.controllers.target_seek.
TargetSeekController` already uses for steering.

Scope, stated honestly: every creature this codebase generates
(``creature_lab/scaffold/``) actuates its hips/knees/ankles with a single sagittal
(local Y-axis) hinge - there is no ab/adduction (roll) degree of freedom anywhere.
That means this controller can only correct **pitch** (forward/backward tipping,
e.g. from walking momentum or a fore/aft push) - it structurally cannot correct
**roll** (side-to-side tipping, e.g. the packaged lateral ``push_recovery`` impulse).
Fixing that needs a new hip joint axis, a body change tracked in
``docs/KNOWN_ISSUES.md``, not a controller change.
"""

from __future__ import annotations

from collections.abc import Callable

from creature_lab.schema import CreatureSpec, FrameState

#: (t, prev_frame) -> {joint_id: target_angle}, matching every other controller.
ControllerFn = Callable[[float, "FrameState | None"], dict[str, float]]


def _root_id(creature: CreatureSpec) -> str:
    child_ids = {joint.child for joint in creature.joints}
    return next(part.id for part in creature.parts if part.id not in child_ids)


def _pitch_lean(orientation: tuple[float, float, float, float]) -> float:
    """World-frame +X component of the root's local +Z (up) axis.

    Zero when upright; positive when the body leans toward its own +X (forward,
    matching :func:`creature_lab.controllers.target_seek._forward_xy`'s convention).
    Ignores roll entirely (see module docstring) - this is a 1D pitch signal, not a
    full orientation error.
    """
    w, x, y, z = orientation
    return 2 * (x * z + y * w)


def default_stabilized_joints(creature: CreatureSpec) -> list[str]:
    """Joints that receive pitch correction.

    Prefer hips when the naming convention identifies them. Applying the same
    correction to hips, knees, and ankles looked plausible but was only "working"
    while the PyBullet link map was wrong; on correctly mapped links it fights
    itself. Unknown bodies still fall back to all motors.
    """
    hips = [motor.joint for motor in creature.motors if "hip" in motor.joint]
    return hips or [motor.joint for motor in creature.motors]


def _default_held_joints(creature: CreatureSpec) -> list[str]:
    """Leg joints held at their base pose even when only hips receive correction."""
    keywords = ("hip", "knee", "ankle")
    matched = [motor.joint for motor in creature.motors if any(k in motor.joint for k in keywords)]
    return matched or [motor.joint for motor in creature.motors]


class PostureController:
    """PD pitch stabilization on top of an optional base pose/gait.

    Deterministic and stateful like :class:`~creature_lab.controllers.cpg.
    CPGController` (call once per timestep in increasing ``t`` order; call
    :meth:`reset` to reuse across episodes).
    """

    def __init__(
        self,
        creature: CreatureSpec,
        *,
        kp: float = 40.0,
        kd: float = 0.0,
        base: ControllerFn | None = None,
        stabilized_joints: list[str] | None = None,
    ) -> None:
        self.creature = creature
        self.kp = kp
        self.kd = kd
        self._base = base
        self._joints = stabilized_joints or default_stabilized_joints(creature)
        self._held_joints = _default_held_joints(creature)
        self._root = _root_id(creature)
        self._prev_lean: float | None = None
        self._prev_t: float | None = None

    def reset(self) -> None:
        self._prev_lean = None
        self._prev_t = None
        reset_fn = getattr(self._base, "reset", None)
        if reset_fn is not None:
            reset_fn()

    def __call__(self, t: float, prev_frame: FrameState | None = None) -> dict[str, float]:
        targets: dict[str, float] = (
            dict(self._base(t, prev_frame)) if self._base is not None else {}
        )
        for joint_id in self._held_joints:
            targets.setdefault(joint_id, 0.0)

        if prev_frame is None or self._root not in prev_frame.parts:
            self._prev_lean = None
            self._prev_t = t
            return targets

        lean = _pitch_lean(prev_frame.parts[self._root].orientation)
        dt = t - self._prev_t if self._prev_t is not None else 0.0
        d_lean = (lean - self._prev_lean) / dt if dt > 1e-6 and self._prev_lean is not None else 0.0
        self._prev_lean, self._prev_t = lean, t

        # Leaning forward (+lean) -> +correction on every stabilized joint. The sign
        # here is empirical, not derived: verified against a real forward push (see
        # tests/test_posture.py) - a plausible-looking "pull the hips back" sign
        # derivation was actually backward and made falls happen *sooner*.
        correction = self.kp * lean + self.kd * d_lean
        for joint_id in self._joints:
            targets[joint_id] += correction
        return targets
