"""Tests for the built-in default creature and task."""

from creature_lab.library import default_creature, default_task
from creature_lab.schema import CreatureSpec, TaskSpec


def test_default_creature_is_valid():
    creature = default_creature()
    assert isinstance(creature, CreatureSpec)
    # Round-trips through validation, so demo never ships a broken default.
    assert CreatureSpec.model_validate(creature.model_dump()) == creature


def test_default_task_is_valid():
    task = default_task()
    assert isinstance(task, TaskSpec)
    assert task.step_count() > 0
