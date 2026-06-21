"""Tests for pre-simulation cross-validation."""

import pytest

from creature_lab.schema import CreatureSpec, TaskSpec
from creature_lab.validation import EpisodeInputError, validate_episode_inputs

CREATURE = {
    "name": "tripod",
    "parts": [
        {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
        {"id": "leg", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
    ],
    "joints": [
        {
            "id": "hip",
            "parent": "torso",
            "child": "leg",
            "type": "hinge",
            "axis": [0, 1, 0],
            "limit": [-0.5, 0.5],
        }
    ],
    "motors": [{"joint": "hip", "amplitude": 0.4, "frequency": 1.0}],
}


def _creature(**overrides) -> CreatureSpec:
    data = {**CREATURE, **overrides}
    return CreatureSpec.model_validate(data)


def test_clean_episode_has_no_warnings():
    task = TaskSpec.model_validate({"name": "t", "duration": 1.0})
    assert validate_episode_inputs(_creature(), task) == []


def test_unknown_damage_part_is_hard_error():
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 2.0, "damage_event": {"time": 1.0, "part_id": "ghost"}}
    )
    with pytest.raises(EpisodeInputError, match="unknown part 'ghost'"):
        validate_episode_inputs(_creature(), task)


def test_known_damage_part_is_accepted():
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 2.0, "damage_event": {"time": 1.0, "part_id": "leg"}}
    )
    assert validate_episode_inputs(_creature(), task) == []


def test_unused_target_warns():
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 1.0, "target": {"position": [1, 0, 0]}}
    )
    warnings = validate_episode_inputs(_creature(), task)
    assert any("target unused" in w for w in warnings)


def test_large_timestep_warns():
    task = TaskSpec.model_validate({"name": "t", "duration": 1.0, "timestep": 0.1})
    warnings = validate_episode_inputs(_creature(), task)
    assert any("large timestep" in w for w in warnings)


def test_motor_amplitude_over_limit_warns():
    # Joint limit is [-0.5, 0.5] but the motor swings to +/-1.5.
    creature = _creature(motors=[{"joint": "hip", "amplitude": 1.5, "frequency": 1.0}])
    task = TaskSpec.model_validate({"name": "t", "duration": 1.0})
    warnings = validate_episode_inputs(creature, task)
    assert any("exceeding its limit" in w for w in warnings)
