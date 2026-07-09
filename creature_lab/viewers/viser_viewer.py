"""Viser browser viewer for replaying or live-streaming creature motion.

This renders poses; it never runs physics. It consumes a stream of FrameState
objects (recorded or produced live by a backend), keeping the viewer
backend-agnostic per docs/MVP_PLAN.md. The schema's scalar-first ``(w, x, y, z)``
quaternion matches Viser's ``wxyz``, so no conversion is needed here.

Viser is an optional dependency (the ``viz`` extra); import this module lazily.
"""

from __future__ import annotations

import time
import webbrowser
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
    extras: list[Any] = field(default_factory=list)


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
    prefix: str = "",
    add_floor: bool = True,
) -> SceneHandles:
    """Add a floor, optional target, one handle per part, and a contact-marker pool.

    ``prefix`` namespaces every node (``/<prefix>/parts/...``) so several creatures
    can share one server (used by ``compare``); ``add_floor`` lets the caller draw a
    single shared floor.
    """
    extras: list[Any] = []
    if add_floor:
        extras.append(server.scene.add_grid("/floor", width=10.0, height=10.0, plane="xy"))
    if task is not None and task.target is not None:
        target = server.scene.add_icosphere(
            f"{prefix}/target", radius=task.target.radius, color=(255, 180, 40)
        )
        target.position = task.target.position
        extras.append(target)
    parts = {
        part.id: _add_part(server.scene, f"{prefix}/parts/{part.id}", part)
        for part in creature.parts
    }
    # A fixed pool of contact dots, shown/hidden per frame as contacts come and go.
    contacts = []
    for index in range(max_contacts):
        marker = server.scene.add_icosphere(
            f"{prefix}/contacts/{index}", radius=0.03, color=_CONTACT_COLOR
        )
        marker.visible = False
        contacts.append(marker)
    return SceneHandles(parts=parts, contacts=contacts, extras=extras)


def remove_scene(handles: SceneHandles | None) -> None:
    """Remove all Viser handles created by ``build_scene``."""
    if handles is None:
        return
    for handle in [*handles.parts.values(), *handles.contacts, *handles.extras]:
        try:
            handle.remove()
        except Exception:
            # Best-effort cleanup: stale Viser handles should not make a refresh fail.
            pass


def add_debug_overlays(server: Any, creature: CreatureSpec, trace: EpisodeTrace) -> None:
    """Draw static debug overlays: CoM trail, root ground path, and a fall marker."""
    import numpy as np

    from creature_lab.diagnosis import diagnose
    from creature_lab.viewers.overlays import center_of_mass_trail, root_path

    com = center_of_mass_trail(creature, trace)
    if com:
        server.scene.add_point_cloud(
            "/debug/com_trail",
            points=np.asarray(com, dtype=np.float32),
            colors=(40, 200, 255),
            point_size=0.02,
        )
    path = root_path(creature, trace)
    if path:
        floor_path = np.asarray([(x, y, 0.005) for x, y, _ in path], dtype=np.float32)
        server.scene.add_point_cloud(
            "/debug/root_path", points=floor_path, colors=(255, 220, 40), point_size=0.015
        )
    # Mark where the body first toppled, if it did.
    result = diagnose(trace, creature)
    fall_time = result.metrics.get("fall_time", -1.0)
    if fall_time >= 0 and com:
        index = min(range(len(trace.frames)), key=lambda i: abs(trace.frames[i].t - fall_time))
        marker = server.scene.add_icosphere("/debug/fall", radius=0.06, color=(255, 40, 40))
        marker.position = com[index]


def apply_frame(
    handles: SceneHandles,
    frame: FrameState,
    *,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """Move part handles to their poses and show contact markers for this frame.

    ``offset`` shifts the whole creature (used by ``compare`` to place two runs
    side by side in one scene).
    """

    def shift(position: tuple[float, float, float]) -> tuple[float, float, float]:
        return (position[0] + offset[0], position[1] + offset[1], position[2] + offset[2])

    for part_id, pose in frame.parts.items():
        handle = handles.parts.get(part_id)
        if handle is not None:
            handle.position = shift(pose.position)
            handle.wxyz = pose.orientation
    for index, marker in enumerate(handles.contacts):
        if index < len(frame.contacts):
            marker.position = shift(frame.contacts[index].position)
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
    open_browser: bool = False,
    debug_trace: EpisodeTrace | None = None,
) -> list[FrameState]:
    """Open a Viser server and animate `frames` as they arrive.

    `frames` may be a live generator (e.g. a running simulation) or a recorded
    sequence. Frames are captured as they play; when the stream ends and `hold`
    is true, the captured frames loop so the scene keeps moving until interrupted.
    Returns the captured frames so a caller can save them as a trace. When
    ``debug_trace`` is given, static debug overlays (CoM/root trails, fall marker)
    are drawn from it before animating.
    """
    import viser

    server = viser.ViserServer(port=port)
    if open_browser:
        webbrowser.open(f"http://localhost:{port}", new=2)
    handles = build_scene(server, creature, task)
    if debug_trace is not None:
        add_debug_overlays(server, creature, debug_trace)
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
    debug: bool = False,
    open_browser: bool = False,
) -> None:
    """Open a Viser server and animate a recorded trace. Blocks until interrupted."""
    stream_frames(
        creature,
        trace.frames,
        task=task,
        fps=fps,
        port=port,
        hold=loop,
        open_browser=open_browser,
        debug_trace=trace if debug else None,
    )


def compare_traces(
    creature_a: CreatureSpec,
    trace_a: EpisodeTrace,
    creature_b: CreatureSpec,
    trace_b: EpisodeTrace,
    *,
    task_a: TaskSpec | None = None,
    task_b: TaskSpec | None = None,
    gap: float = 1.0,
    fps: float = 30.0,
    port: int = 8080,
    hold: bool = True,
    open_browser: bool = False,
) -> None:
    """Replay two runs side by side in one Viser scene (B offset by ``gap`` in y)."""
    import viser

    server = viser.ViserServer(port=port)
    if open_browser:
        webbrowser.open(f"http://localhost:{port}", new=2)
    handles_a = build_scene(server, creature_a, task_a, prefix="/a", add_floor=True)
    handles_b = build_scene(server, creature_b, task_b, prefix="/b", add_floor=False)
    offset_a = (0.0, gap / 2, 0.0)
    offset_b = (0.0, -gap / 2, 0.0)
    frames_a, frames_b = trace_a.frames, trace_b.frames
    n = max(len(frames_a), len(frames_b))
    delay = 1.0 / fps
    try:
        while True:
            for i in range(n):
                apply_frame(handles_a, frames_a[min(i, len(frames_a) - 1)], offset=offset_a)
                apply_frame(handles_b, frames_b[min(i, len(frames_b) - 1)], offset=offset_b)
                time.sleep(delay)
            if not hold:
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
