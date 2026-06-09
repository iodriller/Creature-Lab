"""Portable task/world schema for Creature Lab."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Vector3 = tuple[float, float, float]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
        return self
