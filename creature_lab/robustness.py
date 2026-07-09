"""Score robustness under small seeded perturbations (backend-agnostic).

Mirrors ``evolve.py``'s pattern: this module perturbs specs and computes trial
statistics, but never runs physics itself — the caller injects an ``evaluate``
function backed by whichever simulator it likes.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass

from creature_lab.schema import CreatureSpec, TaskSpec

#: (creature, task) -> (score, fell)
EvaluateFn = Callable[[CreatureSpec, TaskSpec], tuple[float, bool]]


@dataclass(frozen=True)
class RobustnessTrial:
    seed: int
    score: float
    fell: bool
    mass_scale: float
    friction_scale: float


@dataclass(frozen=True)
class RobustnessResult:
    trials: list[RobustnessTrial]
    mean_score: float
    std_score: float
    min_score: float
    max_score: float
    fail_rate: float


def perturb(
    creature: CreatureSpec,
    task: TaskSpec,
    seed: int,
    *,
    mass_jitter: float = 0.05,
    friction_jitter: float = 0.05,
) -> tuple[CreatureSpec, TaskSpec, float, float]:
    """Deterministically perturb part masses and ground friction for one trial.

    Returns the perturbed ``(creature, task)`` plus the scale factors actually used
    (for reporting). Re-validates both specs, since a multiplicative jitter can only
    ever keep a positive field positive, but this keeps the safety net explicit.
    """
    rng = random.Random(seed)
    mass_scale = 1.0 + rng.uniform(-mass_jitter, mass_jitter)
    friction_scale = 1.0 + rng.uniform(-friction_jitter, friction_jitter)

    creature_data = creature.model_dump()
    for part in creature_data["parts"]:
        part["mass"] *= mass_scale
    perturbed_creature = CreatureSpec.model_validate(creature_data)

    task_data = task.model_dump()
    task_data["terrain"]["friction"] = max(task.terrain.friction * friction_scale, 0.0)
    perturbed_task = TaskSpec.model_validate(task_data)

    return perturbed_creature, perturbed_task, mass_scale, friction_scale


def run_trials(
    creature: CreatureSpec,
    task: TaskSpec,
    evaluate: EvaluateFn,
    *,
    trials: int = 10,
    seed: int = 0,
    mass_jitter: float = 0.05,
    friction_jitter: float = 0.05,
) -> RobustnessResult:
    """Evaluate ``trials`` deterministically perturbed variants and summarize scores."""
    if trials < 1:
        raise ValueError("trials must be at least 1")

    results: list[RobustnessTrial] = []
    for i in range(trials):
        trial_seed = seed + i
        perturbed_creature, perturbed_task, mass_scale, friction_scale = perturb(
            creature, task, trial_seed, mass_jitter=mass_jitter, friction_jitter=friction_jitter
        )
        score, fell = evaluate(perturbed_creature, perturbed_task)
        results.append(RobustnessTrial(trial_seed, score, fell, mass_scale, friction_scale))

    scores = [trial.score for trial in results]
    return RobustnessResult(
        trials=results,
        mean_score=statistics.fmean(scores),
        std_score=statistics.pstdev(scores) if len(scores) > 1 else 0.0,
        min_score=min(scores),
        max_score=max(scores),
        fail_rate=sum(trial.fell for trial in results) / len(results),
    )
