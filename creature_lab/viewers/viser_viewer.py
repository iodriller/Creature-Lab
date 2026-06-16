"""Viser browser viewer for replaying episode traces.

This renders recorded poses; it never runs physics. Per docs/MVP_PLAN.md, replay
is portable (any renderer can draw recorded poses) while physics is not. The
schema's scalar-first ``(w, x, y, z)`` quaternion matches Viser's ``wxyz``, so no
conversion is needed here.

Viser is an optional dependency (the ``viz`` extra); import this module lazily.
"""

from __future__ import annotations

import time
from typing import Any

from creature_lab.schema import CreatureSpec, EpisodeTrace, FrameState, PartSpec, TaskSpec
from creature_lab.schema.creature import ShapeType

_DEFAULT_COLOR = (0.6, 0.6, 0.6)


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
    # Capsule/cylinder: approximate with a bounding box along the local z axis.
    assert part.radius is not None and part.length is not None
    diameter = 2 * part.radius
    return scene.add_box(name, color=color, dimensions=(diameter, diameter, part.length))


def build_scene(
    server: Any, creature: CreatureSpec, task: TaskSpec | None = None
) -> dict[str, Any]:
    """Add a floor, optional target marker, and one handle per part. Returns the handles."""
    server.scene.add_grid("/floor", width=10.0, height=10.0, plane="xy")
    if task is not None and task.target is not None:
        target = server.scene.add_icosphere(
            "/target", radius=task.target.radius, color=(255, 180, 40)
        )
        target.position = task.target.position
    return {part.id: _add_part(server.scene, f"/parts/{part.id}", part) for part in creature.parts}


def apply_frame(handles: dict[str, Any], frame: FrameState) -> None:
    """Move each part handle to its pose in `frame`."""
    for part_id, pose in frame.parts.items():
        handle = handles.get(part_id)
        if handle is not None:
            handle.position = pose.position
            handle.wxyz = pose.orientation


def play_trace(
    creature: CreatureSpec,
    trace: EpisodeTrace,
    *,
    task: TaskSpec | None = None,
    fps: float = 30.0,
    loop: bool = True,
    port: int = 8080,
) -> None:
    """Open a Viser server and animate the trace. Blocks until interrupted."""
    import viser

    server = viser.ViserServer(port=port)
    handles = build_scene(server, creature, task)
    delay = 1.0 / fps
    try:
        while True:
            for frame in trace.frames:
                apply_frame(handles, frame)
                time.sleep(delay)
            if not loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
