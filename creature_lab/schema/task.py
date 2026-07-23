"""Portable task/world schema for Creature Lab."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from creature_lab.schema.base import StrictModel, Vector3


class TerrainType(StrEnum):
    PLANE = "plane"
    SLOPE = "slope"
    STEPS = "steps"
    GAPS = "gaps"
    ROUGH = "rough"


class TargetType(StrEnum):
    SPHERE = "sphere"


class TerrainSpec(StrictModel):
    """The ground a task runs on.

    Non-``plane`` types build a shared heightfield (see ``creature_lab/terrain.py``) so
    both backends simulate the same shape; only the fields relevant to ``type`` are used.
    """

    type: TerrainType = TerrainType.PLANE
    friction: float = Field(default=0.8, ge=0)
    #: SLOPE: incline angle in radians, along the +x (forward) axis.
    slope_angle: float = Field(default=0.0, ge=-1.4, le=1.4)
    #: STEPS: rise per step (m) and horizontal run per step (m).
    step_height: float = Field(default=0.05, gt=0)
    step_length: float = Field(default=0.4, gt=0)
    #: GAPS: width of each impassable gap (m) and the distance between gap starts (m).
    gap_width: float = Field(default=0.2, gt=0)
    gap_period: float = Field(default=1.0, gt=0)
    #: ROUGH: max per-cell height perturbation (m) and the seed for reproducible noise.
    roughness: float = Field(default=0.03, ge=0)
    seed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_gaps(self) -> TerrainSpec:
        if self.gap_width >= self.gap_period:
            raise ValueError("terrain gap_width must be less than gap_period")
        return self


class TargetSpec(StrictModel):
    type: TargetType = TargetType.SPHERE
    position: Vector3
    radius: float = Field(default=0.15, gt=0)


class RewardSpec(StrictModel):
    forward_distance: float = 1.0
    target_distance: float = 0.0
    energy_penalty: float = 0.0
    fall_penalty: float = 0.0
    #: Positive reward for still being upright at the end of the episode - the
    #: mirror image of ``fall_penalty``. Without this, a "stay balanced" task built
    #: only from penalties (fall_penalty + energy_penalty) can never score above 0,
    #: so even a creature that succeeds looks like it failed.
    survival: float = 0.0


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


class ImpulseEventSpec(StrictModel):
    """A one-step external push applied to a part — used for push-recovery tasks."""

    time: float = Field(gt=0)
    part_id: str = Field(min_length=1)
    #: World-frame force (N) applied for a single timestep at the part's centre.
    force: Vector3

    @field_validator("part_id")
    @classmethod
    def clean_part_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("impulse event part_id must not be blank")
        return value


class TaskSpec(StrictModel):
    name: str = Field(min_length=1)
    duration: float = Field(gt=0)
    timestep: float = Field(default=1.0 / 60.0, gt=0)
    terrain: TerrainSpec = Field(default_factory=TerrainSpec)
    target: TargetSpec | None = None
    reward: RewardSpec = Field(default_factory=RewardSpec)
    damage_event: DamageEventSpec | None = None
    impulse_event: ImpulseEventSpec | None = None

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
        if self.impulse_event is not None and self.impulse_event.time >= self.duration:
            raise ValueError("impulse event time must be before task duration")
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
