"""Tests for the Viser viewer's pose/geometry logic.

The pure helpers are tested directly; the scene build + frame application are
tested against a headless Viser server (no browser needed). Tests skip if viser
is not installed.
"""

import pytest

from creature_lab.schema import CreatureSpec, FrameState, PartSpec, TaskSpec
from creature_lab.viewers.viser_viewer import apply_frame, build_scene, part_color_255

CREATURE = {
    "name": "tripod",
    "parts": [
        {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
        {"id": "leg", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
        {"id": "head", "shape": "sphere", "radius": 0.08, "mass": 0.1},
    ],
    "joints": [
        {"id": "hip", "parent": "torso", "child": "leg", "type": "hinge", "axis": [0, 1, 0]},
        {"id": "neck", "parent": "torso", "child": "head", "type": "fixed"},
    ],
}


def test_part_color_defaults_to_grey():
    part = PartSpec.model_validate({"id": "a", "shape": "sphere", "radius": 0.1, "mass": 1.0})
    assert part_color_255(part) == (153, 153, 153)


def test_part_color_scales_to_255():
    part = PartSpec.model_validate(
        {"id": "a", "shape": "sphere", "radius": 0.1, "mass": 1.0, "color": [1.0, 0.0, 0.5]}
    )
    assert part_color_255(part) == (255, 0, 128)


def test_build_scene_and_apply_frame_headless():
    viser = pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(CREATURE)
    task = TaskSpec.model_validate(
        {"name": "reach", "duration": 1.0, "target": {"position": [1.0, 0.0, 0.0]}}
    )
    frame = FrameState.model_validate(
        {
            "t": 0.0,
            "parts": {
                "torso": {"position": [1.0, 2.0, 3.0], "orientation": [1.0, 0.0, 0.0, 0.0]},
                "leg": {"position": [0.0, 0.0, 0.5]},
                "head": {"position": [0.0, 0.0, 1.0]},
            },
        }
    )

    server = viser.ViserServer(port=8129, verbose=False)
    try:
        handles = build_scene(server, creature, task)
        assert set(handles) == {"torso", "leg", "head"}

        apply_frame(handles, frame)
        assert tuple(handles["torso"].position) == (1.0, 2.0, 3.0)
        assert tuple(handles["torso"].wxyz) == (1.0, 0.0, 0.0, 0.0)
    finally:
        server.stop()
