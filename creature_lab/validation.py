"""Cross-validation of a (creature, task) pair before simulation.

Schema validation checks each spec in isolation; this catches mistakes that only
show up when a creature and task are combined, before PyBullet runs. Hard errors
raise ``EpisodeInputError``; softer concerns are returned as warning strings for
the caller to surface.
"""

from __future__ import annotations

from creature_lab.schema import CreatureSpec, TaskSpec
from creature_lab.schema.creature import JointType

# Heuristics for the soft checks.
_MAX_REASONABLE_STEPS = 200_000
_MAX_STABLE_TIMESTEP = 1.0 / 30.0


class EpisodeInputError(ValueError):
    """Raised when a creature and task cannot be simulated together."""


def validate_episode_inputs(creature: CreatureSpec, task: TaskSpec) -> list[str]:
    """Check a (creature, task) pair. Returns warnings; raises on hard errors."""
    part_ids = {part.id for part in creature.parts}

    # --- hard errors ---
    if task.damage_event is not None and task.damage_event.part_id not in part_ids:
        raise EpisodeInputError(
            f"task damages unknown part {task.damage_event.part_id!r} "
            f"(creature parts: {sorted(part_ids)})"
        )
    if task.impulse_event is not None and task.impulse_event.part_id not in part_ids:
        raise EpisodeInputError(
            f"task pushes unknown part {task.impulse_event.part_id!r} "
            f"(creature parts: {sorted(part_ids)})"
        )

    # --- soft warnings ---
    warnings: list[str] = []

    if task.target is not None and task.reward.target_distance == 0.0:
        warnings.append("task has a target but reward.target_distance is 0 (target unused)")

    reward = task.reward
    # forward/target are "go" objectives; fall_penalty is a "stay upright" objective
    # (balance/push-recovery tasks), so it counts too.
    if (reward.forward_distance, reward.target_distance, reward.fall_penalty) == (0.0, 0.0, 0.0):
        warnings.append(
            "reward has no objective (forward_distance, target_distance, fall_penalty all 0)"
        )

    if task.step_count() > _MAX_REASONABLE_STEPS:
        warnings.append(
            f"very long episode: {task.step_count()} steps "
            f"(duration {task.duration}s / timestep {task.timestep}s)"
        )

    if task.timestep > _MAX_STABLE_TIMESTEP:
        warnings.append(f"large timestep {task.timestep}s may be unstable (prefer <= 1/30s)")

    warnings.extend(_motor_limit_warnings(creature))
    return warnings


def _motor_limit_warnings(creature: CreatureSpec) -> list[str]:
    """Warn when a motor's sinusoid swing drives a joint past its limits."""
    limits = {
        joint.id: joint.limit
        for joint in creature.joints
        if joint.type == JointType.HINGE and joint.limit is not None
    }
    warnings: list[str] = []
    for motor in creature.motors:
        limit = limits.get(motor.joint)
        if limit is None:
            continue
        lower, upper = limit
        if -motor.amplitude < lower or motor.amplitude > upper:
            warnings.append(
                f"motor on joint {motor.joint!r} swings to +/-{motor.amplitude} rad, "
                f"exceeding its limit [{lower}, {upper}] (target will be clamped each step)"
            )
    return warnings
