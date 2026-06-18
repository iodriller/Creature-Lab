"""Schema for the agent/mutator design loop.

`AgentTrace` records a sequence of tool-driven design attempts so the lab reads as
a creature-lineage log, not just a physics viewer (see docs/MVP_PLAN.md §5.5).
"""

from __future__ import annotations

from pydantic import Field

from creature_lab.schema.base import StrictModel


class AgentStep(StrictModel):
    attempt: int = Field(ge=0)
    action: str = Field(min_length=1)
    valid: bool
    score: float | None = None
    accepted: bool = False
    note: str = ""


class AgentTrace(StrictModel):
    creature_name: str = Field(min_length=1)
    task_name: str = Field(min_length=1)
    goal: str = ""
    best_score: float
    steps: list[AgentStep] = Field(min_length=1)
