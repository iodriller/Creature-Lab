"""Tests for the backend-agnostic robustness trial/perturbation logic (Phase 2)."""

from __future__ import annotations

import pytest

from creature_lab.robustness import perturb, run_trials
from creature_lab.schema import CreatureSpec, TaskSpec


def _creature() -> CreatureSpec:
    return CreatureSpec.model_validate(
        {
            "name": "test_bot",
            "parts": [
                {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
                {"id": "leg", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
            ],
            "joints": [
                {"id": "hip", "parent": "torso", "child": "leg", "type": "fixed"},
            ],
        }
    )


def _task() -> TaskSpec:
    return TaskSpec.model_validate({"name": "crawl_forward", "duration": 1.0})


def test_perturb_is_deterministic_for_a_given_seed():
    a = perturb(_creature(), _task(), seed=5)
    b = perturb(_creature(), _task(), seed=5)

    assert a[2] == b[2]  # mass_scale
    assert a[3] == b[3]  # friction_scale
    assert [p.mass for p in a[0].parts] == [p.mass for p in b[0].parts]


def test_perturb_different_seeds_differ():
    a = perturb(_creature(), _task(), seed=1)
    b = perturb(_creature(), _task(), seed=2)

    assert a[2] != b[2]


def test_perturb_stays_within_the_jitter_bound():
    creature, task, mass_scale, friction_scale = perturb(
        _creature(), _task(), seed=3, mass_jitter=0.1, friction_jitter=0.2
    )

    assert 0.9 <= mass_scale <= 1.1
    assert 0.8 <= friction_scale <= 1.2
    original = _creature()
    for original_part, perturbed_part in zip(original.parts, creature.parts, strict=True):
        assert perturbed_part.mass == pytest.approx(original_part.mass * mass_scale)
    assert task.terrain.friction == pytest.approx(_task().terrain.friction * friction_scale)


def test_perturb_never_produces_negative_friction():
    # A huge jitter would drive friction negative without the floor-at-zero clamp.
    _, task, _, friction_scale = perturb(_creature(), _task(), seed=7, friction_jitter=5.0)

    assert friction_scale < 0 or task.terrain.friction >= 0.0
    assert task.terrain.friction >= 0.0


def test_run_trials_computes_summary_statistics():
    scores = iter([0.5, 0.6, 0.4, 0.5, 0.5])

    def evaluate(creature: CreatureSpec, task: TaskSpec) -> tuple[float, bool]:
        return next(scores), False

    result = run_trials(_creature(), _task(), evaluate, trials=5, seed=0)

    assert len(result.trials) == 5
    assert result.mean_score == pytest.approx(0.5)
    assert result.min_score == pytest.approx(0.4)
    assert result.max_score == pytest.approx(0.6)
    assert result.fail_rate == 0.0


def test_run_trials_reports_fail_rate():
    fell_flags = iter([True, False, True, False])

    def evaluate(creature: CreatureSpec, task: TaskSpec) -> tuple[float, bool]:
        return 0.1, next(fell_flags)

    result = run_trials(_creature(), _task(), evaluate, trials=4, seed=0)

    assert result.fail_rate == 0.5


def test_run_trials_uses_sequential_seeds_from_the_base():
    seeds_seen = []

    def evaluate(creature: CreatureSpec, task: TaskSpec) -> tuple[float, bool]:
        return 0.0, False

    run_trials(_creature(), _task(), evaluate, trials=3, seed=10)
    # Re-run and capture seeds via perturb directly, since run_trials doesn't expose them.
    result = run_trials(_creature(), _task(), evaluate, trials=3, seed=10)
    seeds_seen = [t.seed for t in result.trials]

    assert seeds_seen == [10, 11, 12]


def test_run_trials_rejects_zero_trials():
    def evaluate(creature: CreatureSpec, task: TaskSpec) -> tuple[float, bool]:
        return 0.0, False

    with pytest.raises(ValueError):
        run_trials(_creature(), _task(), evaluate, trials=0)
