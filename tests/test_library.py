"""Tests for the built-in default creature and task."""

import pytest

from creature_lab.library import (
    builtin_creature_names,
    creature_by_name,
    default_creature,
    default_task,
)
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


def test_every_builtin_creature_is_valid():
    names = builtin_creature_names()
    assert {"quadruped", "worm", "tripod"} <= set(names)
    for name in names:
        creature = creature_by_name(name)
        assert isinstance(creature, CreatureSpec)
        assert creature.name == name


def test_creature_by_name_rejects_unknown():
    with pytest.raises(KeyError, match="unknown built-in creature"):
        creature_by_name("dragon")
