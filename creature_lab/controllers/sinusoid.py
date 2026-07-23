"""Deterministic sinusoidal joint controller."""

from __future__ import annotations

import math

from creature_lab.schema import CreatureSpec


def sinusoid_targets(creature: CreatureSpec, t: float) -> dict[str, float]:
    """Compute a target angle for each motor at time `t`.

    Backend-neutral and deterministic: the same `(creature, t)` always
    produces the same targets, independent of any physics engine.
    """
    return {
        motor.joint: motor.offset
        + motor.amplitude * math.sin(2 * math.pi * motor.frequency * t + motor.phase)
        for motor in creature.motors
    }
