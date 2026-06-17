"""Portable task/world schema for Creature Lab."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from creature_lab.schema.base import StrictModel, Vector3


class TerrainType(StrEnum):
    PLANE = "plane"


class TargetType(StrEnum):
    SPHERE = "sphere"


class TerrainSpec(StrictModel):
    type: TerrainType = TerrainType.PLANE
    friction: float = Field(default=0.8, ge=0)


class TargetSpec(StrictModel):
    type: TargetType = TargetType.SPHERE
    position: Vector3
    radius: float = Field(default=0.15, gt=0)


class RewardSpec(StrictModel):
    forward_distance: float = 1.0
    target_distance: float = 0.0
    energy_penalty: float = 0.0
    fall_penalty: float = 0.0


class DamageEventSpec(StrictModel):
    time: float = Field(gt=0)
    part_id: str = Field(min_length=1)

    @field_validator("part_id")
    @classmethod
    def clean_part_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("damage event part_id must not be blank")
        return value


class TaskSpec(StrictModel):
    name: str = Field(min_length=1)
    duration: float = Field(gt=0)
    timestep: float = Field(default=1.0 / 60.0, gt=0)
    terrain: TerrainSpec = Field(default_factory=TerrainSpec)
    target: TargetSpec | None = None
    reward: RewardSpec = Field(default_factory=RewardSpec)
    damage_event: DamageEventSpec | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task name must not be blank")
        return value

    @model_validator(mode="after")
    def validate_timing(self) -> TaskSpec:
        if self.timestep > self.duration:
            raise ValueError("task timestep must not exceed duration")
        if self.damage_event is not None and self.damage_event.time >= self.duration:
            raise ValueError("damage event time must be before task duration")
        if self.target is None and self.reward.target_distance != 0.0:
            raise ValueError("reward.target_distance requires a task target")
        return self

    def step_count(self) -> int:
        """Number of simulation steps for this task.

        Uses rounding (not truncation) so floating-point error in
        ``duration / timestep`` cannot silently drop the final step; always at
        least one step since ``timestep <= duration``.
        """
        return max(1, round(self.duration / self.timestep))
