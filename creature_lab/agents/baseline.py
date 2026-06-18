"""A no-LLM policy that proposes random, valid tool calls.

Lets the agent loop (and ``creature-lab ask --offline``) run without any model
provider, so the lab is useful and testable out of the box. Deterministic for a
given seed.
"""

from __future__ import annotations

import random

from creature_lab.agents.loop import Observation, Proposal
from creature_lab.schema.creature import ShapeType

_LENGTH_SHAPES = (ShapeType.CAPSULE, ShapeType.CYLINDER)


class RandomToolPolicy:
    """Propose a random parameter tweak via the validated tool layer."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def __call__(self, observation: Observation) -> Proposal:
        creature = observation.creature
        rng = self._rng
        options: list[str] = []
        if creature.motors:
            options += ["amplitude", "frequency", "phase"]
        if any(part.shape in _LENGTH_SHAPES for part in creature.parts):
            options.append("length")
        if not options:
            # Nothing tweakable; a no-op proposal the loop will reject as invalid.
            return Proposal("set_motor", {"joint": "_none_"}, "no tunable parameters")

        choice = rng.choice(options)
        if choice == "length":
            limbs = [part for part in creature.parts if part.shape in _LENGTH_SHAPES]
            limb = rng.choice(limbs)
            new_length = round(max(0.05, limb.length * rng.uniform(0.85, 1.15)), 4)
            return Proposal("resize_limb", {"part": limb.id, "length": new_length}, "resize limb")

        motor = rng.choice(creature.motors)
        if choice == "amplitude":
            value = round(max(0.0, motor.amplitude * rng.uniform(0.7, 1.3)), 4)
            args = {"joint": motor.joint, "amplitude": value}
            return Proposal("set_motor", args, "tune amplitude")
        if choice == "frequency":
            value = round(max(0.1, motor.frequency * rng.uniform(0.7, 1.3)), 4)
            args = {"joint": motor.joint, "frequency": value}
            return Proposal("set_motor", args, "tune frequency")
        value = round(motor.phase + rng.uniform(-0.5, 0.5), 4)
        return Proposal("set_motor", {"joint": motor.joint, "phase": value}, "tune phase")
