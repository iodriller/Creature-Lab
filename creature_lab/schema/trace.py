"""Portable frame and episode trace schemas."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from creature_lab.schema.base import Quaternion, StrictModel, Vector3


class PartPose(StrictModel):
    position: Vector3
    #: Orientation as a scalar-first quaternion ``(w, x, y, z)``; identity by default.
    orientation: Quaternion = (1.0, 0.0, 0.0, 0.0)


class ContactSpec(StrictModel):
    part_id: str = Field(min_length=1)
    position: Vector3
    normal: Vector3 | None = None
    force: float | None = Field(default=None, ge=0)

    @field_validator("part_id")
    @classmethod
    def clean_part_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("contact part_id must not be blank")
        return value


class FrameState(StrictModel):
    t: float = Field(ge=0)
    parts: dict[str, PartPose]
    joint_angles: dict[str, float] = Field(default_factory=dict)
    contacts: list[ContactSpec] = Field(default_factory=list)
    score: float = Field(default=0.0, allow_inf_nan=False)
    events: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_has_parts(self) -> FrameState:
        if not self.parts:
            raise ValueError("frame state must include at least one part pose")
        return self


class EpisodeTrace(StrictModel):
    run_id: str = Field(min_length=1)
    creature_name: str = Field(min_length=1)
    task_name: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    score: float = Field(allow_inf_nan=False)
    frames: list[FrameState] = Field(min_length=1)

    @field_validator("run_id", "creature_name", "task_name", "backend")
    @classmethod
    def clean_names(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("trace identifiers must not be blank")
        return value

    @model_validator(mode="after")
    def validate_frame_order(self) -> EpisodeTrace:
        times = [frame.t for frame in self.frames]
        if times != sorted(times):
            raise ValueError("episode trace frames must be sorted by time")
        return self
