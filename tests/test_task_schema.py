"""Tests for the TaskSpec schema."""

import pytest
from pydantic import ValidationError

from creature_lab.schema import TaskSpec


def test_minimal_task_round_trips():
    task = TaskSpec.model_validate({"name": "crawl_forward", "duration": 5.0})
    restored = TaskSpec.model_validate_json(task.model_dump_json())
    assert restored == task


def test_timestep_must_not_exceed_duration():
    with pytest.raises(ValidationError, match="timestep must not exceed"):
        TaskSpec.model_validate({"name": "t", "duration": 0.01, "timestep": 1.0})


def test_damage_event_must_precede_duration():
    spec = {"name": "t", "duration": 1.0, "damage_event": {"time": 1.0, "part_id": "leg"}}
    with pytest.raises(ValidationError, match="before task duration"):
        TaskSpec.model_validate(spec)


def test_target_reward_requires_target():
    spec = {"name": "reach", "duration": 1.0, "reward": {"target_distance": 1.0}}
    with pytest.raises(ValidationError, match="requires a task target"):
        TaskSpec.model_validate(spec)


def test_target_reward_with_target_is_valid():
    spec = {
        "name": "reach",
        "duration": 1.0,
        "target": {"position": [1.0, 0.0, 0.0]},
        "reward": {"target_distance": 1.0},
    }
    TaskSpec.model_validate(spec)
