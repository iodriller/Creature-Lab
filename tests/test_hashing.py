"""Tests for stable spec hashing."""

from creature_lab.hashing import spec_hash
from creature_lab.schema import CreatureSpec

SEED = {
    "name": "worm",
    "parts": [
        {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
        {"id": "tail", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
    ],
    "joints": [
        {"id": "hinge", "parent": "torso", "child": "tail", "type": "hinge", "axis": [0, 1, 0]}
    ],
    "motors": [{"joint": "hinge", "amplitude": 0.5, "frequency": 1.0}],
}


def test_hash_is_prefixed_and_hex():
    digest = spec_hash(CreatureSpec.model_validate(SEED))
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_hash_is_stable_across_reserialization():
    a = CreatureSpec.model_validate(SEED)
    b = CreatureSpec.model_validate_json(a.model_dump_json())
    assert spec_hash(a) == spec_hash(b)


def test_hash_independent_of_dict_key_order():
    reordered = {
        "motors": SEED["motors"],
        "joints": SEED["joints"],
        "parts": SEED["parts"],
        "name": SEED["name"],
    }
    assert spec_hash(CreatureSpec.model_validate(SEED)) == spec_hash(
        CreatureSpec.model_validate(reordered)
    )


def test_hash_changes_when_a_field_changes():
    base = CreatureSpec.model_validate(SEED)
    changed = base.model_copy(update={"name": "worm2"})
    assert spec_hash(base) != spec_hash(changed)
