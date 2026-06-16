"""Tests for the CreatureSpec schema and its validation rules."""

import pytest
from pydantic import ValidationError

from creature_lab.schema import CreatureSpec, PartSpec


def _two_part_creature(**overrides):
    spec = {
        "name": "biped",
        "parts": [
            {"id": "torso", "shape": "box", "size": [1, 1, 1], "mass": 1.0},
            {"id": "leg", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
        ],
        "joints": [
            {"id": "hip", "parent": "torso", "child": "leg", "type": "hinge", "axis": [0, 1, 0]},
        ],
        "motors": [{"joint": "hip", "amplitude": 0.5, "frequency": 1.0}],
    }
    spec.update(overrides)
    return spec


def test_valid_creature_round_trips():
    spec = CreatureSpec.model_validate(_two_part_creature())
    restored = CreatureSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec


def test_single_root_is_required():
    # Two disconnected parts -> two roots.
    spec = {
        "name": "c",
        "parts": [
            {"id": "a", "shape": "box", "size": [1, 1, 1], "mass": 1.0},
            {"id": "b", "shape": "box", "size": [1, 1, 1], "mass": 1.0},
        ],
    }
    with pytest.raises(ValidationError, match="exactly one root"):
        CreatureSpec.model_validate(spec)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        CreatureSpec.model_validate(_two_part_creature(extra="nope"))


def test_cycle_is_rejected():
    spec = {
        "name": "c",
        "parts": [
            {"id": "a", "shape": "box", "size": [1, 1, 1], "mass": 1.0},
            {"id": "b", "shape": "box", "size": [1, 1, 1], "mass": 1.0},
        ],
        "joints": [
            {"id": "j1", "parent": "a", "child": "b", "type": "fixed"},
            {"id": "j2", "parent": "b", "child": "a", "type": "fixed"},
        ],
    }
    # b already has a parent (j1); j2 makes it a second -> caught as multi-parent.
    with pytest.raises(ValidationError):
        CreatureSpec.model_validate(spec)


def test_motor_must_reference_known_joint():
    bad = _two_part_creature(motors=[{"joint": "nope", "amplitude": 0.5, "frequency": 1.0}])
    with pytest.raises(ValidationError, match="unknown joint"):
        CreatureSpec.model_validate(bad)


def test_one_motor_per_joint():
    bad = _two_part_creature(
        motors=[
            {"joint": "hip", "amplitude": 0.5, "frequency": 1.0},
            {"joint": "hip", "amplitude": 0.6, "frequency": 1.0},
        ]
    )
    with pytest.raises(ValidationError, match="more than one motor"):
        CreatureSpec.model_validate(bad)


@pytest.mark.parametrize(
    "part",
    [
        {"id": "a", "shape": "box", "size": [1, 1, 1], "mass": 1.0, "radius": 0.5},
        {"id": "a", "shape": "box", "size": [1, 1, 1], "mass": 1.0, "length": 0.5},
        {"id": "a", "shape": "sphere", "radius": 0.5, "mass": 1.0, "size": [1, 1, 1]},
        {
            "id": "a",
            "shape": "capsule",
            "radius": 0.5,
            "length": 1.0,
            "mass": 1.0,
            "size": [1, 1, 1],
        },
    ],
)
def test_stray_dimension_fields_are_rejected(part):
    with pytest.raises(ValidationError):
        PartSpec.model_validate(part)


@pytest.mark.parametrize(
    "part",
    [
        {"id": "a", "shape": "box", "size": [1, 1, 1], "mass": 1.0},
        {"id": "a", "shape": "sphere", "radius": 0.5, "mass": 1.0},
        {"id": "a", "shape": "capsule", "radius": 0.5, "length": 1.0, "mass": 1.0},
        {"id": "a", "shape": "cylinder", "radius": 0.5, "length": 1.0, "mass": 1.0},
    ],
)
def test_valid_shapes_are_accepted(part):
    PartSpec.model_validate(part)


def test_non_positive_mass_is_rejected():
    with pytest.raises(ValidationError):
        PartSpec.model_validate({"id": "a", "shape": "sphere", "radius": 0.5, "mass": 0.0})


def test_color_must_be_bounded():
    with pytest.raises(ValidationError, match="between 0 and 1"):
        PartSpec.model_validate(
            {"id": "a", "shape": "sphere", "radius": 0.5, "mass": 1.0, "color": [2, 0, 0]}
        )
