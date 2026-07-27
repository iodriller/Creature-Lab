"""Portable frame and episode trace schemas."""

from __future__ import annotations

import re

from pydantic import Field, field_validator, model_validator

from creature_lab.schema.base import Quaternion, StrictModel, Vector3

#: Version of the EpisodeTrace artifact format (bump on breaking changes).
TRACE_SCHEMA_VERSION = "1"


class TraceMeta(StrictModel):
    """Provenance/reproducibility metadata for an episode (see docs/archive/MVP_PLAN.md §5.4)."""

    schema_version: str
    lab_version: str
    backend_version: str | None = None
    timestep: float | None = None
    seed: int | None = None
    creature_hash: str | None = None
    task_hash: str | None = None
    #: The `--controller` value that produced this episode: a built-in name
    #: ("sinusoid"/"cpg"/"target_seek") or a controller.json path. None for traces
    #: saved before controller tracking was added, or ones built without going
    #: through `cli._build_meta` (e.g. hand-constructed in a test).
    controller: str | None = None
    #: Hash and run-relative filename of the exact controller snapshot saved beside
    #: the trace.  Older traces leave these unset.
    controller_hash: str | None = None
    controller_artifact: str | None = None
    policy_hash: str | None = None
    score_summary: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


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
    #: Closed-loop control record (populated by CreatureEnv). Both stay None for
    #: open-loop runs, so older traces without these fields still load.
    observations: list[float] | None = None
    actions: list[float] | None = None

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
    meta: TraceMeta | None = None

    @field_validator("run_id", "creature_name", "task_name", "backend")
    @classmethod
    def clean_names(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("trace identifiers must not be blank")
        return value

    @field_validator("run_id")
    @classmethod
    def validate_safe_run_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            raise ValueError("run_id may contain only letters, numbers, '.', '_' and '-'")
        if value in {".", ".."}:
            raise ValueError("run_id must name one run directory")
        return value

    @model_validator(mode="after")
    def validate_frame_order(self) -> EpisodeTrace:
        times = [frame.t for frame in self.frames]
        if times != sorted(times):
            raise ValueError("episode trace frames must be sorted by time")
        return self
