"""Prompt construction and response parsing for the LLM policy.

Kept free of any provider import so the parser is unit-testable without network.
"""

from __future__ import annotations

import json

from creature_lab.agents.loop import Observation, Proposal
from creature_lab.agents.tools import TOOL_SIGNATURES

SYSTEM_PROMPT = (
    "You are a creature-design assistant. You improve a small simulated robot-creature "
    "by proposing ONE tool call at a time. Respond with a single JSON object only, of the "
    'form {"tool": <name>, "args": {<kwargs>}, "note": <short reason>}. Do not add prose.'
)


def _creature_summary(observation: Observation) -> str:
    creature = observation.creature
    motors = ", ".join(
        f"{m.joint}(amp={m.amplitude}, freq={m.frequency}, phase={m.phase})"
        for m in creature.motors
    )
    limbs = ", ".join(f"{p.id}(len={p.length})" for p in creature.parts if p.length is not None)
    summary = (
        f"goal: {observation.goal}\n"
        f"current best score: {observation.best_score:.4f}\n"
        f"motors: {motors or 'none'}\n"
        f"resizable limbs: {limbs or 'none'}"
    )
    if observation.diagnosis:
        summary += f"\ndiagnosed issues: {observation.diagnosis}"
    return summary


def build_prompt(observation: Observation) -> str:
    """Build the user message describing the creature and available tools."""
    tools = "\n".join(f"- {name}({sig})" for name, sig in TOOL_SIGNATURES.items())
    return (
        f"{_creature_summary(observation)}\n\navailable tools:\n{tools}\n\nPropose one tool call."
    )


def parse_proposal(text: str) -> Proposal:
    """Parse a model response into a Proposal, tolerating surrounding prose/code fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model response")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in model response: {exc}") from exc
    tool = data.get("tool")
    if not isinstance(tool, str) or not tool:
        raise ValueError("model response missing a 'tool' name")
    args = data.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("'args' must be an object")
    note = str(data.get("note", ""))
    return Proposal(tool=tool, args=args, note=note)
