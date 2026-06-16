"""Tests for the baseline mutator and hill-climb loop."""

import random

from creature_lab.evolve import hill_climb, mutate
from creature_lab.schema import CreatureSpec

SEED_CREATURE = {
    "name": "worm",
    "parts": [
        {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
        {"id": "tail", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
    ],
    "joints": [
        {"id": "hinge", "parent": "torso", "child": "tail", "type": "hinge", "axis": [0, 1, 0]},
    ],
    "motors": [{"joint": "hinge", "amplitude": 0.5, "frequency": 1.0, "phase": 0.0}],
}


def _seed() -> CreatureSpec:
    return CreatureSpec.model_validate(SEED_CREATURE)


def test_mutate_returns_valid_creature():
    rng = random.Random(0)
    for _ in range(50):
        mutated = mutate(_seed(), rng)
        # Re-validation proves the result is a usable spec, not just a dict.
        CreatureSpec.model_validate(mutated.model_dump())


def test_mutate_is_deterministic_for_a_seed():
    a = mutate(_seed(), random.Random(123))
    b = mutate(_seed(), random.Random(123))
    assert a == b


def test_mutate_changes_something():
    rng = random.Random(1)
    changed = any(mutate(_seed(), rng) != _seed() for _ in range(10))
    assert changed


def test_hill_climb_never_decreases_best_score():
    # Synthetic fitness: total motor amplitude. Mutation can raise or lower it,
    # but the kept best must be monotonic non-decreasing.
    def evaluate(creature: CreatureSpec) -> float:
        return sum(motor.amplitude for motor in creature.motors)

    result = hill_climb(_seed(), evaluate, attempts=30, rng=random.Random(7))

    assert result.best_score >= result.history[0].score
    assert evaluate(result.best) == result.best_score
    assert len(result.history) == 31


def test_hill_climb_is_deterministic():
    def evaluate(creature: CreatureSpec) -> float:
        return sum(motor.frequency for motor in creature.motors)

    first = hill_climb(_seed(), evaluate, attempts=20, rng=random.Random(42))
    second = hill_climb(_seed(), evaluate, attempts=20, rng=random.Random(42))

    assert first.best == second.best
    assert first.best_score == second.best_score


def test_hill_climb_with_zero_attempts_returns_seed():
    result = hill_climb(_seed(), lambda _: 1.0, attempts=0, rng=random.Random(0))
    assert result.best == _seed()
    assert len(result.history) == 1
