"""Baseline no-LLM mutator and hill-climb loop.

This module is backend-agnostic: it mutates and selects ``CreatureSpec`` objects
but never runs physics itself. Callers pass an ``evaluate`` function that returns
a fitness score for a creature, so the loop is deterministic and testable without
a simulator (see CLAUDE.md: do not rely on exact physics reproducibility).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from creature_lab.schema import CreatureSpec
from creature_lab.schema.creature import ShapeType

# Bounds keep mutations in a safe, validatable range.
_LENGTH_BOUNDS = (0.05, 1.0)
_AMPLITUDE_BOUNDS = (0.0, 3.14)
_FREQUENCY_BOUNDS = (0.1, 5.0)

EvaluateFn = Callable[[CreatureSpec], float]


@dataclass(frozen=True)
class Attempt:
    """One step of the hill-climb lineage."""

    index: int
    score: float
    accepted: bool


@dataclass(frozen=True)
class EvolutionResult:
    best: CreatureSpec
    best_score: float
    history: list[Attempt]


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    return max(low, min(high, value))


def mutate(creature: CreatureSpec, rng: random.Random) -> CreatureSpec:
    """Return a validated, randomly mutated copy of ``creature``.

    Applies one small change to either a motor parameter or a limb length. If the
    mutated spec fails validation the original is returned unchanged, so callers
    always receive a valid creature.
    """
    data = creature.model_dump()

    operators = []
    if data["motors"]:
        operators.extend(["amplitude", "frequency", "phase"])
    if any(part["shape"] in (ShapeType.CAPSULE, ShapeType.CYLINDER) for part in data["parts"]):
        operators.append("length")
    if not operators:
        return creature

    operator = rng.choice(operators)
    if operator == "amplitude":
        motor = rng.choice(data["motors"])
        motor["amplitude"] = _clamp(motor["amplitude"] * rng.uniform(0.7, 1.3), _AMPLITUDE_BOUNDS)
    elif operator == "frequency":
        motor = rng.choice(data["motors"])
        motor["frequency"] = _clamp(motor["frequency"] * rng.uniform(0.7, 1.3), _FREQUENCY_BOUNDS)
    elif operator == "phase":
        motor = rng.choice(data["motors"])
        motor["phase"] = motor["phase"] + rng.uniform(-0.5, 0.5)
    elif operator == "length":
        limbs = [
            part
            for part in data["parts"]
            if part["shape"] in (ShapeType.CAPSULE, ShapeType.CYLINDER)
        ]
        limb = rng.choice(limbs)
        limb["length"] = _clamp(limb["length"] * rng.uniform(0.85, 1.15), _LENGTH_BOUNDS)

    try:
        return CreatureSpec.model_validate(data)
    except ValueError:
        return creature


def hill_climb(
    seed: CreatureSpec,
    evaluate: EvaluateFn,
    *,
    attempts: int,
    rng: random.Random,
) -> EvolutionResult:
    """Greedily mutate ``seed``, keeping any candidate that scores higher.

    Deterministic for a given ``rng`` and ``evaluate``.
    """
    if attempts < 0:
        raise ValueError("attempts must not be negative")

    best = seed
    best_score = evaluate(seed)
    history = [Attempt(index=0, score=best_score, accepted=True)]

    for index in range(1, attempts + 1):
        candidate = mutate(best, rng)
        score = evaluate(candidate)
        accepted = score > best_score
        if accepted:
            best, best_score = candidate, score
        history.append(Attempt(index=index, score=score, accepted=accepted))

    return EvolutionResult(best=best, best_score=best_score, history=history)
