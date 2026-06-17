"""Backend-neutral episode scoring.

Turns raw per-episode quantities (measured by a backend) into a scalar score using
the weights in a ``RewardSpec``. Kept pure and engine-free so it is deterministic
and testable without a simulator.
"""

from __future__ import annotations

from creature_lab.schema import RewardSpec


def episode_score(
    reward: RewardSpec,
    *,
    forward_distance: float,
    target_progress: float = 0.0,
    energy: float = 0.0,
    fallen: bool = False,
) -> float:
    """Combine reward components into a single score.

    - ``forward_distance``: signed displacement along +x from the start.
    - ``target_progress``: how much closer to the target than at the start
      (positive = moved toward it).
    - ``energy``: accumulated actuation effort (always penalized).
    - ``fallen``: whether the creature has toppled.
    """
    score = reward.forward_distance * forward_distance
    score += reward.target_distance * target_progress
    score -= reward.energy_penalty * energy
    if fallen:
        score -= reward.fall_penalty
    return score
