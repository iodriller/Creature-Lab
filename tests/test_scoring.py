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
    assert set(components) == {"forward", "target", "energy", "fall", "survival", "total"}
    assert components["total"] == episode_score(reward, **kwargs)
    assert sum(v for k, v in components.items() if k != "total") == components["total"]


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


def test_survival_rewards_staying_upright_and_nothing_else():
    """The mirror image of fall_penalty: a reward built only from survival +
    fall_penalty must be able to score positive when the creature stays up -
    otherwise a 'stay balanced' task can never be won (see docs/KNOWN_ISSUES.md)."""
    reward = RewardSpec(forward_distance=0.0, survival=1.0, fall_penalty=0.5)
    upright = episode_score(reward, forward_distance=0.0, fallen=False)
    fell = episode_score(reward, forward_distance=0.0, fallen=True)
    assert upright == 1.0
    assert fell == -0.5
    assert upright > 0 > fell


def test_survival_is_zero_when_unset():
    reward = RewardSpec(forward_distance=1.0)
    assert episode_score(reward, forward_distance=0.0, fallen=False) == 0.0


def test_all_terms_combine():
    reward = RewardSpec(
        forward_distance=1.0, target_distance=2.0, energy_penalty=0.1, fall_penalty=3.0
    )
    score = episode_score(
        reward, forward_distance=1.0, target_progress=0.5, energy=10.0, fallen=True
    )
    assert score == 1.0 * 1.0 + 2.0 * 0.5 - 0.1 * 10.0 - 3.0
