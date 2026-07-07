"""Tests for the Viser viewer's pose/geometry logic.

The pure helpers are tested directly; the scene build + frame application are
tested against a headless Viser server (no browser needed). Tests skip if viser
is not installed.
"""

import pytest

from creature_lab.schema import CreatureSpec, EpisodeTrace, FrameState, PartSpec, TaskSpec
from creature_lab.viewers.viser_viewer import (
    add_debug_overlays,
    apply_frame,
    build_scene,
    part_color_255,
    stream_frames,
)

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
            "contacts": [{"part_id": "leg", "position": [0.0, 0.0, 0.0]}],
        }
    )

    server = viser.ViserServer(port=8129, verbose=False)
    try:
        handles = build_scene(server, creature, task, max_contacts=4)
        assert set(handles.parts) == {"torso", "leg", "head"}
        assert all(not marker.visible for marker in handles.contacts)

        apply_frame(handles, frame)
        assert tuple(handles.parts["torso"].position) == (1.0, 2.0, 3.0)
        assert tuple(handles.parts["torso"].wxyz) == (1.0, 0.0, 0.0, 0.0)
        # One contact this frame: first marker shown at the contact, the rest hidden.
        assert handles.contacts[0].visible is True
        assert tuple(handles.contacts[0].position) == (0.0, 0.0, 0.0)
        assert all(not marker.visible for marker in handles.contacts[1:])
    finally:
        server.stop()


def test_capsule_and_cylinder_render_as_true_primitives():
    viser = pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(
        {
            "name": "shapes",
            "parts": [
                {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
                {"id": "cap", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
                {"id": "cyl", "shape": "cylinder", "length": 0.3, "radius": 0.05, "mass": 0.2},
            ],
            "joints": [
                {"id": "j1", "parent": "torso", "child": "cap", "type": "fixed"},
                {"id": "j2", "parent": "torso", "child": "cyl", "type": "fixed"},
            ],
        }
    )
    frame = FrameState.model_validate(
        {
            "t": 0.0,
            "parts": {
                "torso": {"position": [0.0, 0.0, 0.0]},
                "cap": {"position": [0.1, 0.0, 0.0]},
                "cyl": {"position": [-0.1, 0.0, 0.0]},
            },
        }
    )

    server = viser.ViserServer(port=8131, verbose=False)
    try:
        handles = build_scene(server, creature, task=None, max_contacts=1)
        # Cylinder uses the native primitive; capsule is a true mesh (not a box).
        assert type(handles.parts["cyl"]).__name__ == "CylinderHandle"
        assert type(handles.parts["cap"]).__name__ == "GlbHandle"
        assert type(handles.parts["torso"]).__name__ == "BoxHandle"

        apply_frame(handles, frame)  # still positionable
        assert tuple(handles.parts["cap"].position) == (0.1, 0.0, 0.0)
        assert tuple(handles.parts["cyl"].position) == (-0.1, 0.0, 0.0)
    finally:
        server.stop()


def test_stream_frames_captures_and_returns_frames():
    pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(CREATURE)

    def make_frame(x: float) -> FrameState:
        return FrameState.model_validate(
            {
                "t": x,
                "parts": {
                    "torso": {"position": [x, 0.0, 0.0]},
                    "leg": {"position": [0.0, 0.0, 0.0]},
                    "head": {"position": [0.0, 0.0, 0.0]},
                },
            }
        )

    incoming = [make_frame(0.0), make_frame(1.0), make_frame(2.0)]
    # hold=False so the call returns after one pass; high fps keeps the test fast.
    captured = stream_frames(creature, iter(incoming), fps=1000.0, port=8130, hold=False)
    assert captured == incoming


def test_build_scene_draws_a_flat_grid_for_flat_terrain():
    viser = pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(CREATURE)
    task = TaskSpec.model_validate({"name": "t", "duration": 1.0})

    server = viser.ViserServer(port=8132, verbose=False)
    try:
        handles = build_scene(server, creature, task)
        assert type(handles.floor).__name__ == "GridHandle"
    finally:
        server.stop()


def test_build_scene_draws_a_terrain_mesh_for_non_flat_terrain():
    viser = pytest.importorskip("viser")
    pytest.importorskip("trimesh")

    creature = CreatureSpec.model_validate(CREATURE)
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 1.0, "terrain": {"type": "slope", "slope_angle": 0.2}}
    )

    server = viser.ViserServer(port=8133, verbose=False)
    try:
        handles = build_scene(server, creature, task)
        # A heightfield mesh, not the flat grid drawn for plane terrain.
        assert type(handles.floor).__name__ != "GridHandle"
    finally:
        server.stop()


def test_build_scene_no_floor_when_add_floor_is_false():
    viser = pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(CREATURE)
    server = viser.ViserServer(port=8134, verbose=False)
    try:
        handles = build_scene(server, creature, None, add_floor=False)
        assert handles.floor is None
    finally:
        server.stop()


def test_debug_overlays_root_path_follows_terrain_height():
    import math

    viser = pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(CREATURE)
    slope_angle = 0.5
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 1.0, "terrain": {"type": "slope", "slope_angle": slope_angle}}
    )
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r",
            "creature_name": "tripod",
            "task_name": "t",
            "backend": "pybullet",
            "score": 0.0,
            "frames": [
                {"t": 0.0, "parts": {"torso": {"position": [3.0, 0.0, 1.0]}}, "score": 0.0},
            ],
        }
    )

    server = viser.ViserServer(port=8135, verbose=False)
    try:
        handle = add_debug_overlays(server, creature, trace, task)
        assert handle is not None
        # ~3.0 * tan(0.5) of terrain height at that point (nearest-cell, so approximate);
        # a flat-ground overlay would have placed this point near z=0.005 instead.
        expected_height = 3.0 * math.tan(slope_angle)
        assert handle.points[0][2] == pytest.approx(expected_height, abs=0.1)
    finally:
        server.stop()


def test_debug_overlays_root_path_is_flat_without_a_task():
    viser = pytest.importorskip("viser")

    creature = CreatureSpec.model_validate(CREATURE)
    trace = EpisodeTrace.model_validate(
        {
            "run_id": "r",
            "creature_name": "tripod",
            "task_name": "t",
            "backend": "pybullet",
            "score": 0.0,
            "frames": [
                {"t": 0.0, "parts": {"torso": {"position": [3.0, 0.0, 1.0]}}, "score": 0.0},
            ],
        }
    )

    server = viser.ViserServer(port=8136, verbose=False)
    try:
        handle = add_debug_overlays(server, creature, trace, None)
        assert handle.points[0][2] == pytest.approx(0.005, abs=1e-6)
    finally:
        server.stop()
