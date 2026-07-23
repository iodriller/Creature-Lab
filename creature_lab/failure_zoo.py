"""Curated broken experiments for teaching and regression diagnosis."""

from __future__ import annotations

import math
from dataclasses import dataclass

from creature_lab.controllers.factory import extract_sinusoid_spec
from creature_lab.schema import ControllerSpec, CreatureSpec, TaskSpec
from creature_lab.zoo import zoo_creature, zoo_optimized_controller


@dataclass(frozen=True)
class FailureCase:
    id: str
    title: str
    expected_cause: str
    description: str


FAILURE_CASES: tuple[FailureCase, ...] = (
    FailureCase("frozen-gait", "Frozen gait", "controller", "All motor amplitudes are zero."),
    FailureCase(
        "overdriven-gait",
        "Overdriven gait",
        "controller",
        "Excessive amplitude and frequency destabilize an otherwise capable body.",
    ),
    FailureCase(
        "top-heavy-body",
        "Top-heavy body",
        "morphology_or_task",
        "Torso mass is increased far beyond the leg support geometry.",
    ),
    FailureCase(
        "ice-rink-task",
        "Ice-rink task",
        "morphology_or_task",
        "Ground friction is too low for the expected gait.",
    ),
    FailureCase(
        "wrong-way-phases",
        "Wrong-way phases",
        "controller",
        "Every other leg is shifted into an unhelpful phase pattern.",
    ),
    FailureCase(
        "tripod-tipping",
        "Tripod tipping",
        "morphology_or_task",
        "An asymmetric three-leg challenge exposes support and balance limits.",
    ),
)


def list_failure_cases() -> list[FailureCase]:
    return list(FAILURE_CASES)


def build_failure_case(case_id: str) -> tuple[CreatureSpec, TaskSpec, ControllerSpec, FailureCase]:
    cases = {case.id: case for case in FAILURE_CASES}
    if case_id not in cases:
        raise KeyError(f"unknown failure case {case_id!r}; choose one of: {', '.join(cases)}")
    case = cases[case_id]
    source = "tripod" if case_id == "tripod-tipping" else "quadruped"
    creature, task = zoo_creature(source, "crawl_forward")
    controller_path = zoo_optimized_controller(source)
    controller = (
        ControllerSpec.model_validate_json(controller_path.read_text(encoding="utf-8"))
        if controller_path is not None
        else extract_sinusoid_spec(creature)
    )

    if case_id == "frozen-gait":
        data = controller.model_dump(mode="json")
        for motor in data["motors"]:
            motor["amplitude"] = 0.0
        controller = ControllerSpec.model_validate(data)
    elif case_id == "overdriven-gait":
        data = controller.model_dump(mode="json")
        for motor in data["motors"]:
            motor["amplitude"] = 2.2
            motor["frequency"] = 5.0
        controller = ControllerSpec.model_validate(data)
    elif case_id == "top-heavy-body":
        data = creature.model_dump(mode="json")
        data["parts"][0]["mass"] *= 15.0
        creature = CreatureSpec.model_validate(data)
    elif case_id == "ice-rink-task":
        data = task.model_dump(mode="json")
        data["terrain"]["friction"] = 0.01
        task = TaskSpec.model_validate(data)
    elif case_id == "wrong-way-phases":
        data = controller.model_dump(mode="json")
        for index, motor in enumerate(data["motors"]):
            motor["phase"] = math.pi if index % 2 else 0.0
        controller = ControllerSpec.model_validate(data)
    return creature, task, controller, case
