"""Live Viser build editor."""

from __future__ import annotations

import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from creature_lab.editor.controls import BuildControls
from creature_lab.editor.session import EditorSession
from creature_lab.runs import DEFAULT_RUNS_DIR, save_run
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec
from creature_lab.viewers.viser_viewer import apply_frame, build_scene, remove_scene

SimulateFn = Callable[[CreatureSpec, TaskSpec], EpisodeTrace]


class EditorPreview:
    """3D preview scene for the current editor session."""

    def __init__(
        self,
        server: Any,
        session: EditorSession,
        *,
        on_select: Callable[[str], None],
        on_change: Callable[[], None],
    ) -> None:
        self.server = server
        self.session = session
        self.on_select = on_select
        self.on_change = on_change
        self._handles = None

    def refresh(self) -> None:
        remove_scene(self._handles)
        self._handles = build_scene(self.server, self.session.creature, self.session.task)
        for part_id, handle in self._handles.parts.items():
            handle.on_click(lambda _event, part_id=part_id: self.on_select(part_id))
        frame = self.session.preview_frame()
        apply_frame(self._handles, frame)
        self._add_editor_overlays(frame)

    def animate(self, trace: EpisodeTrace, *, fps: float = 60.0) -> None:
        if self._handles is None:
            self.refresh()
        assert self._handles is not None
        delay = 1.0 / fps
        for frame in trace.frames:
            apply_frame(self._handles, frame)
            time.sleep(delay)

    def _add_editor_overlays(self, frame) -> None:
        assert self._handles is not None
        selected = frame.parts.get(self.session.selected_part_id)
        if selected is not None:
            marker = self.server.scene.add_frame(
                "/editor/selected",
                axes_length=0.16,
                axes_radius=0.008,
                origin_radius=0.025,
                position=selected.position,
            )
            self._handles.extras.append(marker)
            has_parent_joint = any(
                joint.child == self.session.selected_part_id
                for joint in self.session.creature.joints
            )
            if has_parent_joint:
                gizmo = self.server.scene.add_transform_controls(
                    "/editor/anchor_gizmo",
                    scale=0.25,
                    disable_rotations=True,
                    position=selected.position,
                )
                gizmo.on_drag_end(lambda event: self._move_selected_anchor(event.target.position))
                self._handles.extras.append(gizmo)
        metrics = self.session.preview_metrics()
        com = self.server.scene.add_icosphere(
            "/editor/com",
            radius=0.035,
            color=(30, 220, 140),
            position=(metrics["com_x"], metrics["com_y"], metrics["com_z"]),
        )
        self._handles.extras.append(com)
        support = metrics["support_width"]
        if support > 0:
            points = np.asarray(
                [[0.0, -support / 2, 0.015], [0.0, support / 2, 0.015]],
                dtype=np.float32,
            )
            line = self.server.scene.add_line_segments(
                "/editor/support_width",
                points=points.reshape(1, 2, 3),
                colors=(30, 220, 140),
                line_width=3,
            )
            self._handles.extras.append(line)

    def _move_selected_anchor(self, position: tuple[float, float, float]) -> None:
        self.session.move_selected_anchor_to(tuple(float(value) for value in position))
        self.refresh()
        self.on_change()


def run_editor(
    session: EditorSession,
    *,
    simulate: SimulateFn,
    port: int = 8080,
    open_browser: bool = False,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> None:
    """Start the Viser build editor and block until interrupted."""
    import viser

    server = viser.ViserServer(port=port)
    if open_browser:
        webbrowser.open(f"http://localhost:{port}", new=2)

    controls_holder: dict[str, BuildControls] = {}

    def select_part(part_id: str) -> None:
        controls_holder["controls"].scene_selected(part_id)

    def scene_changed() -> None:
        controls = controls_holder.get("controls")
        if controls is not None:
            controls.scene_changed()

    preview = EditorPreview(server, session, on_select=select_part, on_change=scene_changed)

    def simulate_current() -> str:
        status = session.status()
        if not status.ok:
            return "Fix validation errors before simulating."
        trace = simulate(session.creature, session.task)
        run_dir = save_run(session.creature, trace, runs_dir=runs_dir, task=session.task)
        preview.animate(trace)
        return f"Simulated score={trace.score:.4f}; saved {run_dir}"

    controls_holder["controls"] = BuildControls(
        server.gui,
        session,
        on_preview=preview.refresh,
        on_simulate=simulate_current,
    )
    preview.refresh()

    try:
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
