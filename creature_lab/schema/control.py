"""Observation and action contracts for closed-loop control.

These describe what a policy *sees* (``ObservationSpec``) and how its action vector
*drives* the creature (``ActionSpec``) in :class:`creature_lab.env.CreatureEnv`. Like
everything in ``schema/``, they are backend-neutral data — no physics engine here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from creature_lab.schema.base import StrictModel


class ObservationSpec(StrictModel):
    """Which signals are concatenated into the observation vector, in this order."""

    include_root_pos: bool = True
    include_root_orientation: bool = False
    include_root_vel: bool = True
    include_root_angular_velocity: bool = False
    include_joint_angles: bool = True
    include_joint_velocities: bool = True
    include_contacts: bool = False
    include_target_vector: bool = False


class ActionSpec(StrictModel):
    """How a normalized action vector maps onto the creature's joints."""

    mode: Literal["position", "velocity", "torque"] = "position"
    #: Joints this policy controls, in vector order. Empty => all hinge joints (sorted).
    joints: list[str] = Field(default_factory=list)
    #: Range each action component is expected to fall in (clipped to this).
    clip_range: tuple[float, float] = (-1.0, 1.0)

    @model_validator(mode="after")
    def validate_clip_range(self) -> ActionSpec:
        if self.clip_range[0] >= self.clip_range[1]:
            raise ValueError("clip_range minimum must be less than maximum")
        return self

    @model_validator(mode="after")
    def validate_unique_joints(self) -> ActionSpec:
        if len(self.joints) != len(set(self.joints)):
            raise ValueError("action joints must be unique")
        return self
