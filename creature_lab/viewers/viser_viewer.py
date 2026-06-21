"""Viser browser viewer for replaying or live-streaming creature motion.

This renders poses; it never runs physics. It consumes a stream of FrameState
objects (recorded or produced live by a backend), keeping the viewer
backend-agnostic per docs/MVP_PLAN.md. The schema's scalar-first ``(w, x, y, z)``
quaternion matches Viser's ``wxyz``, so no conversion is needed here.

Viser is an optional dependency (the ``viz`` extra); import this module lazily.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from creature_lab.schema import CreatureSpec, EpisodeTrace, FrameState, PartSpec, TaskSpec
from creature_lab.schema.creature import ShapeType

_DEFAULT_COLOR = (0.6, 0.6, 0.6)
_CONTACT_COLOR = (255, 60, 40)
_MAX_CONTACT_MARKERS = 16


@dataclass
class SceneHandles:
    """Mutable Viser handles for a built scene."""

    parts: dict[str, Any]
    contacts: list[Any] = field(default_factory=list)


def part_color_255(part: PartSpec) -> tuple[int, int, int]:
    """Convert a part's 0..1 RGB color to Viser's 0..255 integer triple."""
    rgb = part.color or _DEFAULT_COLOR
    return tuple(int(round(max(0.0, min(1.0, channel)) * 255)) for channel in rgb)


def _add_part(scene: Any, name: str, part: PartSpec) -> Any:
    color = part_color_255(part)
    if part.shape == ShapeType.BOX:
        assert part.size is not None
        return scene.add_box(name, color=color, dimensions=tuple(part.size))
    if part.shape == ShapeType.SPHERE:
        assert part.radius is not None
        return scene.add_icosphere(name, radius=part.radius, color=color)
    assert part.radius is not None and part.length is not None
    if part.shape == ShapeType.CYLINDER:
        # Native Viser cylinder, along the local z axis (matches the schema/backend).
        return scene.add_cylinder(name, radius=part.radius, height=part.length, color=color)
    # Capsule: Viser has no native primitive, so build a true capsule mesh (rounded
    # ends) with trimesh — matching the PyBullet export. trimesh ships with the viz extra.
    import numpy as np
    import trimesh

    centered = trimesh.transformations.translation_matrix((0.0, 0.0, -part.length / 2))
    mesh = trimesh.creation.capsule(height=part.length, radius=part.radius, transform=centered)
    mesh.visual.vertex_colors = np.array([*color, 255], dtype=np.uint8)
    return scene.add_mesh_trimesh(name, mesh)


def build_scene(
    server: Any,
    creature: CreatureSpec,
    task: TaskSpec | None = None,
    *,
    max_contacts: int = _MAX_CONTACT_MARKERS,
) -> SceneHandles:
    """Add a floor, optional target, one handle per part, and a contact-marker pool."""
    server.scene.add_grid("/floor", width=10.0, height=10.0, plane="xy")
    if task is not None and task.target is not None:
        target = server.scene.add_icosphere(
            "/target", radius=task.target.radius, color=(255, 180, 40)
        )
        target.position = task.target.position
    parts = {part.id: _add_part(server.scene, f"/parts/{part.id}", part) for part in creature.parts}
    # A fixed pool of contact dots, shown/hidden per frame as contacts come and go.
    contacts = []
    for index in range(max_contacts):
        marker = server.scene.add_icosphere(f"/contacts/{index}", radius=0.03, color=_CONTACT_COLOR)
        marker.visible = False
        contacts.append(marker)
    return SceneHandles(parts=parts, contacts=contacts)


def apply_frame(handles: SceneHandles, frame: FrameState) -> None:
    """Move part handles to their poses and show contact markers for this frame."""
    for part_id, pose in frame.parts.items():
        handle = handles.parts.get(part_id)
        if handle is not None:
            handle.position = pose.position
            handle.wxyz = pose.orientation
    for index, marker in enumerate(handles.contacts):
        if index < len(frame.contacts):
            marker.position = frame.contacts[index].position
            marker.visible = True
        else:
            marker.visible = False


def stream_frames(
    creature: CreatureSpec,
    frames: Iterable[FrameState],
    *,
    task: TaskSpec | None = None,
    fps: float = 30.0,
    port: int = 8080,
    hold: bool = True,
) -> list[FrameState]:
    """Open a Viser server and animate `frames` as they arrive.

    `frames` may be a live generator (e.g. a running simulation) or a recorded
    sequence. Frames are captured as they play; when the stream ends and `hold`
    is true, the captured frames loop so the scene keeps moving until interrupted.
    Returns the captured frames so a caller can save them as a trace.
    """
    import viser

    server = viser.ViserServer(port=port)
    handles = build_scene(server, creature, task)
    delay = 1.0 / fps
    captured: list[FrameState] = []
    try:
        for frame in frames:
            apply_frame(handles, frame)
            captured.append(frame)
            time.sleep(delay)
        while hold and captured:
            for frame in captured:
                apply_frame(handles, frame)
                time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return captured


def play_trace(
    creature: CreatureSpec,
    trace: EpisodeTrace,
    *,
    task: TaskSpec | None = None,
    fps: float = 30.0,
    loop: bool = True,
    port: int = 8080,
) -> None:
    """Open a Viser server and animate a recorded trace. Blocks until interrupted."""
    stream_frames(creature, trace.frames, task=task, fps=fps, port=port, hold=loop)
