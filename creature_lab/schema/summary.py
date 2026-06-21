"""Compact, human-readable summary of an episode.

Derived from an ``EpisodeTrace`` (plus an optional ``TaskSpec``) so it is a pure,
backend-free view that ``inspect`` and other commands can present.
"""

from __future__ import annotations

from pydantic import Field

from creature_lab.schema.base import StrictModel


class EpisodeSummary(StrictModel):
    frame_count: int = Field(ge=0)
    duration: float = Field(ge=0)
    final_score: float
    component_scores: dict[str, float] = Field(default_factory=dict)
    distance_traveled: float = Field(ge=0)
    forward_distance: float
    target_progress: float | None = None
    total_joint_motion: float = Field(ge=0)
    fell: bool | None = None
    damage_events: list[str] = Field(default_factory=list)
    contacts_by_part: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
