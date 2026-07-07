"""Policy-driven design loop.

The loop is provider-agnostic: a ``Policy`` proposes a tool call given an
``Observation``; the loop validates and applies it through the tool layer,
re-evaluates the creature with a caller-supplied ``evaluate`` function, keeps the
best, and records an ``AgentTrace``. This keeps the loop testable without any LLM
or simulator.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from creature_lab.agents.tools import ToolError, apply_tool
from creature_lab.schema import AgentStep, AgentTrace, CreatureSpec

EvaluateFn = Callable[[CreatureSpec], float]
#: Optional: summarize why a creature is scoring the way it does, as prompt-ready text.
DiagnoseFn = Callable[[CreatureSpec], str]


@dataclass(frozen=True)
class Observation:
    """What a policy sees before proposing the next edit."""

    creature: CreatureSpec
    best_score: float
    attempt: int
    goal: str = ""
    #: Plain-language failure-pattern summary for the current best (empty if none/unavailable).
    diagnosis: str = ""


@dataclass(frozen=True)
class Proposal:
    """A tool call proposed by a policy."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    note: str = ""


Policy = Callable[[Observation], Proposal]


@dataclass
class DesignResult:
    best: CreatureSpec
    best_score: float
    trace: AgentTrace


def design_loop(
    creature: CreatureSpec,
    evaluate: EvaluateFn,
    policy: Policy,
    *,
    attempts: int,
    goal: str = "",
    task_name: str = "design",
    diagnose: DiagnoseFn | None = None,
) -> DesignResult:
    """Run the policy for `attempts` steps, keeping any higher-scoring valid edit.

    When ``diagnose`` is given, it is called on the current best before every proposal
    and its text is attached to the ``Observation`` — so a policy (an LLM prompt, or a
    future rule-based one) can react to *why* the creature is scoring the way it is,
    not just the scalar score.
    """
    if attempts < 0:
        raise ValueError("attempts must not be negative")

    best = creature
    best_score = evaluate(creature)
    steps = [AgentStep(attempt=0, action="seed", valid=True, score=best_score, accepted=True)]

    for attempt in range(1, attempts + 1):
        diagnosis = diagnose(best) if diagnose is not None else ""
        proposal = policy(Observation(best, best_score, attempt, goal, diagnosis))
        action = f"{proposal.tool}({proposal.args})"
        try:
            candidate = apply_tool(best, proposal.tool, proposal.args)
        except ToolError as exc:
            steps.append(
                AgentStep(attempt=attempt, action=action, valid=False, note=str(exc)[:160])
            )
            continue
        score = evaluate(candidate)
        accepted = score > best_score
        if accepted:
            best, best_score = candidate, score
        steps.append(
            AgentStep(
                attempt=attempt,
                action=action,
                valid=True,
                score=score,
                accepted=accepted,
                note=proposal.note,
            )
        )

    trace = AgentTrace(
        creature_name=creature.name,
        task_name=task_name,
        goal=goal,
        best_score=best_score,
        steps=steps,
    )
    return DesignResult(best=best, best_score=best_score, trace=trace)
