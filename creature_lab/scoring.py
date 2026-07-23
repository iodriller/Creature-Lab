"""Backend-neutral episode scoring.

Turns raw per-episode quantities (measured by a backend) into a scalar score using
the weights in a ``RewardSpec``. Kept pure and engine-free so it is deterministic
and testable without a simulator.
"""

from __future__ import annotations

from creature_lab.schema import RewardSpec


def score_components(
    reward: RewardSpec,
    *,
    forward_distance: float,
    target_progress: float = 0.0,
    energy: float = 0.0,
    fallen: bool = False,
) -> dict[str, float]:
    """Break the score into its weighted components plus the ``total``.

    - ``forward_distance``: signed displacement along +x from the start.
    - ``target_progress``: how much closer to the target than at the start
      (positive = moved toward it).
    - ``energy``: accumulated actuation effort (always penalized).
    - ``fallen``: whether the creature has toppled - also gates ``survival``
      (the mirror image of ``fall_penalty``: reward for *not* having fallen).
    """
    components = {
        "forward": reward.forward_distance * forward_distance,
        "target": reward.target_distance * target_progress,
        "energy": -reward.energy_penalty * energy,
        "fall": -reward.fall_penalty if fallen else 0.0,
        "survival": 0.0 if fallen else reward.survival,
    }
    components["total"] = sum(components.values())
    return components


def episode_score(
    reward: RewardSpec,
    *,
    forward_distance: float,
    target_progress: float = 0.0,
    energy: float = 0.0,
    fallen: bool = False,
) -> float:
    """Combine reward components into a single scalar score."""
    return score_components(
        reward,
        forward_distance=forward_distance,
        target_progress=target_progress,
        energy=energy,
        fallen=fallen,
    )["total"]
