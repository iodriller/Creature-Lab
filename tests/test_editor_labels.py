"""Tests for friendly part labels and the hierarchy tree view."""

from __future__ import annotations

from creature_lab.editor import presets
from creature_lab.editor.labels import friendly_label, hierarchy_markdown, hierarchy_rows


def test_friendly_label_special_cases():
    assert friendly_label("torso") == "Torso"
    assert friendly_label("head") == "Head"
    assert friendly_label("neck") == "Neck"


def test_friendly_label_leg_row_pattern():
    assert friendly_label("leg_0l") == "Leg 1 (left)"
    assert friendly_label("hip_2r") == "Hip 3 (right)"


def test_friendly_label_sided_humanoid_pattern():
    assert friendly_label("upper_leg_l") == "Upper leg (left)"
    assert friendly_label("foot_r") == "Foot (right)"
    assert friendly_label("shoulder_l") == "Shoulder (left)"


def test_friendly_label_segment_pattern():
    assert friendly_label("seg0") == "Segment 1"
    assert friendly_label("seg4") == "Segment 5"
    assert friendly_label("j2") == "Segment 3"


def test_friendly_label_limb_pattern():
    assert friendly_label("limb_3") == "Limb 3"


def test_friendly_label_falls_back_to_title_case():
    assert friendly_label("sensor_mount") == "Sensor mount"
    assert friendly_label("weird-id") == "Weird-id"


def test_hierarchy_rows_root_first_depth_first():
    creature = presets.generate_creature("quadruped")
    rows = hierarchy_rows(creature)

    assert rows[0] == (0, "torso")
    ids = [part_id for _depth, part_id in rows]
    assert set(ids) == {part.id for part in creature.parts}
    # Every leg is a direct child of torso (depth 1).
    leg_depths = {depth for depth, pid in rows if pid.startswith("leg_")}
    assert leg_depths == {1}


def test_hierarchy_markdown_bolds_selected_and_covers_all_parts():
    creature = presets.generate_creature("worm", {"segments": 4})
    text = hierarchy_markdown(creature, "seg2")

    assert "**Segment 3**" in text
    assert "Segment 1" in text and "**Segment 1**" not in text
    assert text.count("Segment") == 4
