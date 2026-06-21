"""Tests for the pure episode-scoring helper."""

from creature_lab.schema import RewardSpec
from creature_lab.scoring import episode_score, score_components


def test_forward_distance_only():
    reward = RewardSpec(forward_distance=2.0)
    assert episode_score(reward, forward_distance=1.5) == 3.0


def test_components_sum_to_episode_score():
    reward = RewardSpec(
        forward_distance=1.0, target_distance=2.0, energy_penalty=0.1, fall_penalty=3.0
    )
    kwargs = dict(forward_distance=1.0, target_progress=0.5, energy=10.0, fallen=True)
    components = score_components(reward, **kwargs)
    assert set(components) == {"forward", "target", "energy", "fall", "total"}
    assert components["total"] == episode_score(reward, **kwargs)
    assert (
        components["forward"] + components["target"] + components["energy"] + components["fall"]
        == components["total"]
    )


def test_target_progress_is_rewarded():
    reward = RewardSpec(forward_distance=0.0, target_distance=1.0)
    closer = episode_score(reward, forward_distance=0.0, target_progress=0.8)
    farther = episode_score(reward, forward_distance=0.0, target_progress=-0.3)
    assert closer == 0.8
    assert farther == -0.3
    assert closer > farther


def test_energy_is_penalized():
    reward = RewardSpec(forward_distance=1.0, energy_penalty=0.5)
    assert episode_score(reward, forward_distance=2.0, energy=4.0) == 2.0 - 0.5 * 4.0


def test_fall_penalty_applies_only_when_fallen():
    reward = RewardSpec(forward_distance=1.0, fall_penalty=5.0)
    standing = episode_score(reward, forward_distance=1.0, fallen=False)
    fallen = episode_score(reward, forward_distance=1.0, fallen=True)
    assert standing == 1.0
    assert fallen == 1.0 - 5.0


def test_all_terms_combine():
    reward = RewardSpec(
        forward_distance=1.0, target_distance=2.0, energy_penalty=0.1, fall_penalty=3.0
    )
    score = episode_score(
        reward, forward_distance=1.0, target_progress=0.5, energy=10.0, fallen=True
    )
    assert score == 1.0 * 1.0 + 2.0 * 0.5 - 0.1 * 10.0 - 3.0
