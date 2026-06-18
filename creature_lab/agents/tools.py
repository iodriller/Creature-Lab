"""Validated creature-editing tools.

Each tool takes a ``CreatureSpec`` plus keyword arguments and returns a new,
re-validated ``CreatureSpec``. Anything invalid (unknown id, wrong shape, value
out of range) raises ``ToolError`` rather than producing an unvalidated creature,
so the agent loop can record the failure and move on.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from creature_lab.schema import CreatureSpec
from creature_lab.schema.creature import ShapeType

_LENGTH_SHAPES = (ShapeType.CAPSULE, ShapeType.CYLINDER)


class ToolError(ValueError):
    """Raised when a tool is called with arguments that cannot be applied."""


def _revalidate(data: dict) -> CreatureSpec:
    try:
        return CreatureSpec.model_validate(data)
    except ValidationError as exc:
        raise ToolError(f"resulting creature is invalid: {exc.errors()[0]['msg']}") from exc


def set_motor(
    creature: CreatureSpec,
    *,
    joint: str,
    amplitude: float | None = None,
    frequency: float | None = None,
    phase: float | None = None,
) -> CreatureSpec:
    """Update an existing motor's sinusoid parameters."""
    data = creature.model_dump()
    motors = [motor for motor in data["motors"] if motor["joint"] == joint]
    if not motors:
        raise ToolError(f"no motor drives joint {joint!r}")
    motor = motors[0]
    if amplitude is not None:
        motor["amplitude"] = amplitude
    if frequency is not None:
        motor["frequency"] = frequency
    if phase is not None:
        motor["phase"] = phase
    return _revalidate(data)


def set_joint_limit(
    creature: CreatureSpec, *, joint: str, lower: float, upper: float
) -> CreatureSpec:
    """Set the lower/upper limit of a joint."""
    data = creature.model_dump()
    joints = [item for item in data["joints"] if item["id"] == joint]
    if not joints:
        raise ToolError(f"unknown joint {joint!r}")
    joints[0]["limit"] = [lower, upper]
    return _revalidate(data)


def resize_limb(creature: CreatureSpec, *, part: str, length: float) -> CreatureSpec:
    """Change the length of a capsule/cylinder part."""
    data = creature.model_dump()
    parts = [item for item in data["parts"] if item["id"] == part]
    if not parts:
        raise ToolError(f"unknown part {part!r}")
    if parts[0]["shape"] not in _LENGTH_SHAPES:
        raise ToolError(f"part {part!r} has no length to resize")
    parts[0]["length"] = length
    return _revalidate(data)


#: Public tool registry and a short, prompt-friendly description of each tool's args.
TOOLS = {
    "set_motor": set_motor,
    "set_joint_limit": set_joint_limit,
    "resize_limb": resize_limb,
}

TOOL_SIGNATURES = {
    "set_motor": "joint:str, amplitude?:float, frequency?:float, phase?:float",
    "set_joint_limit": "joint:str, lower:float, upper:float",
    "resize_limb": "part:str, length:float",
}


def apply_tool(creature: CreatureSpec, name: str, args: dict[str, Any]) -> CreatureSpec:
    """Dispatch to a tool by name, validating the call."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"unknown tool {name!r}")
    try:
        return tool(creature, **args)
    except TypeError as exc:  # wrong/missing keyword arguments
        raise ToolError(f"bad arguments for {name!r}: {exc}") from exc
