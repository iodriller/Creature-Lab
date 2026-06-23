"""Tests for procedural creature generators and the mirror operation."""

import pytest

from creature_lab.scaffold import (
    GENERATORS,
    generate_hexapod,
    generate_humanoid,
    generate_quadruped,
    generate_worm,
    mirror_limb,
)
from creature_lab.schema import CreatureSpec


def test_all_generators_produce_valid_creatures():
    for _name, generator in GENERATORS.items():
        creature = generator()
        assert isinstance(creature, CreatureSpec)
        # A scaffolded creature must round-trip through full validation.
        assert CreatureSpec.model_validate(creature.model_dump()) == creature


def test_worm_segment_count():
    worm = generate_worm(7)
    assert len(worm.parts) == 7
    assert len(worm.joints) == 6  # one fewer joint than segments
    assert len(worm.motors) == 6


def test_worm_rejects_too_few_segments():
    with pytest.raises(ValueError, match="at least 2 segments"):
        generate_worm(1)


def test_quadruped_has_four_legs():
    quad = generate_quadruped()
    legs = [p for p in quad.parts if p.id.startswith("leg_")]
    assert len(legs) == 4


def test_hexapod_has_six_legs():
    hexapod = generate_hexapod()
    legs = [p for p in hexapod.parts if p.id.startswith("leg_")]
    assert len(legs) == 6


def test_humanoid_dof_controls_complexity():
    h8 = generate_humanoid(dof=8)
    h12 = generate_humanoid(dof=12)
    assert len(h8.motors) == 8
    assert len(h12.motors) == 12
    assert len(h12.parts) > len(h8.parts)  # feet + hands added


def test_humanoid_rejects_bad_dof():
    with pytest.raises(ValueError, match="dof must be 8 or 12"):
        generate_humanoid(dof=10)  # type: ignore[arg-type]


def test_mirror_limb_negates_anchor_y():
    # A half quadruped: torso + only the left legs.
    quad = generate_quadruped().model_dump(exclude_none=True)
    half = CreatureSpec.model_validate(
        {
            "name": "half",
            "parts": [p for p in quad["parts"] if p["id"] == "torso" or p["id"].endswith("l")],
            "joints": [j for j in quad["joints"] if j["child"].endswith("l")],
            "motors": [m for m in quad["motors"] if m["joint"].endswith("l")],
        }
    )
    left_count = len(half.joints)
    mirrored = mirror_limb(half, side="left")

    assert len(mirrored.joints) == 2 * left_count  # originals + mirrored copies
    by_id = {j.id: j for j in mirrored.joints}
    for joint in half.joints:
        original = by_id[joint.id]
        copy = by_id[joint.id + "_m"]
        assert copy.anchor[1] == pytest.approx(-original.anchor[1])
        assert copy.parent == original.parent  # both hang off the torso (root)


def test_mirror_limb_errors_with_no_source_limbs():
    worm = generate_worm()  # a chain with no left/right limbs off the root
    with pytest.raises(ValueError, match="no limbs found"):
        mirror_limb(worm, side="left")


def test_mirror_limb_twice_collides():
    quad = generate_quadruped()
    once = mirror_limb(quad, side="left")  # adds leg_*l_m copies
    with pytest.raises(ValueError, match="collides"):
        mirror_limb(once, side="left")  # the _m copies already exist
