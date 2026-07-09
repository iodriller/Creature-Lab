"""Tests for the build editor's pure session logic."""

import json

import pytest

from creature_lab.editor import presets
from creature_lab.editor.session import EditorSession
from creature_lab.schema import CreatureSpec


def test_editor_session_default_is_valid():
    session = EditorSession()

    assert session.creature.name == "quadruped"
    assert session.status().ok
    assert session.preview_frame().parts


def test_editor_preset_body_params_regenerate_valid_humanoid():
    session = EditorSession(template="humanoid")

    session.set_body_param("dof", 12)
    session.set_body_param("upper_leg_ratio", 0.30)
    session.set_body_param("limb_radius_ratio", 0.04)

    assert session.status().ok
    assert len(session.creature.motors) == 12
    assert any(part.id == "foot_l" for part in session.creature.parts)


def test_editor_part_and_motor_edits_validate():
    session = EditorSession()
    session.select_part("leg_0l")
    session.update_selected_part(length=0.31, radius=0.04, color=(255, 64, 32))
    session.select_motor("hip_0l")
    session.update_selected_motor(amplitude=0.5, frequency=1.25, phase=0.2)

    part = next(part for part in session.creature.parts if part.id == "leg_0l")
    motor = next(motor for motor in session.creature.motors if motor.joint == "hip_0l")

    assert part.length == 0.31
    assert part.radius == 0.04
    assert part.color == (1.0, 64 / 255, 32 / 255)
    assert motor.amplitude == 0.5
    assert motor.frequency == 1.25
    assert motor.phase == 0.2
    assert session.status().ok


def test_editor_moves_selected_joint_anchor_from_preview_position():
    session = EditorSession()
    session.select_part("leg_0l")

    session.move_selected_anchor_to((0.2, 0.2, 0.1))

    joint = next(joint for joint in session.creature.joints if joint.child == "leg_0l")
    assert joint.anchor == pytest.approx((0.2, 0.2, 0.06))
    assert session.status().ok


def test_editor_add_delete_limb_round_trips():
    session = EditorSession()
    original_parts = len(session.creature.parts)

    session.select_part("torso")
    session.add_limb()
    assert len(session.creature.parts) == original_parts + 1
    assert session.selected_part_id.startswith("limb_")
    assert session.status().ok

    session.delete_selected_part()
    assert len(session.creature.parts) == original_parts
    assert session.status().ok


def test_editor_save_and_load(tmp_path):
    out = tmp_path / "built.json"
    session = EditorSession(template="worm", out_path=out)
    session.set_body_param("segments", 7)
    saved = session.save()

    loaded = EditorSession.from_path(saved)

    assert saved == out
    assert loaded.creature.name == "worm"
    assert len(loaded.creature.parts) == 7
    assert CreatureSpec.model_validate(json.loads(saved.read_text())) == loaded.creature


def test_task_presets_are_valid():
    for name in presets.task_names():
        task = presets.generate_task(name)
        assert task.name == name
        assert task.step_count() > 0
