"""Viser GUI controls for build mode."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from creature_lab.editor import presets
from creature_lab.editor.session import EditorSession
from creature_lab.schema.creature import ShapeType


class BuildControls:
    """Build and keep the Viser side panel in sync with an ``EditorSession``."""

    def __init__(
        self,
        gui: Any,
        session: EditorSession,
        *,
        on_preview: Callable[[], None],
        on_simulate: Callable[[], str],
    ) -> None:
        self.gui = gui
        self.session = session
        self.on_preview = on_preview
        self.on_simulate = on_simulate
        self._body_folder: Any | None = None
        self._part_folder: Any | None = None
        self._motion_folder: Any | None = None
        self._task_folder: Any | None = None
        self._message: Any | None = None
        self._simulate_button: Any | None = None
        self._build()

    def _build(self) -> None:
        with self.gui.add_folder("Start", expand_by_default=True):
            initial = (
                presets.preset_label(self.session.template)
                if self.session.template in presets.CREATURE_PRESETS
                else presets.preset_label("quadruped")
            )
            template = self.gui.add_dropdown(
                "Template", presets.preset_labels(), initial_value=initial
            )
            template.on_update(
                lambda event: self._safe(
                    lambda: self.session.apply_template(
                        presets.preset_name_from_label(event.target.value)
                    ),
                    rebuild_body=True,
                    rebuild_part=True,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )

            name = self.gui.add_text("Name", self.session.creature.name)
            name.on_update(
                lambda event: self._safe(
                    lambda: self.session.set_name(event.target.value),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

            load_path = self.gui.add_text(
                "Open JSON",
                str(self.session.source_path or self.session.out_path),
                hint="Path to an existing CreatureSpec JSON.",
            )
            open_button = self.gui.add_button("Open", icon="folder-open")
            open_button.on_click(
                lambda _event: self._safe(
                    lambda: self.session.load_path(Path(load_path.value)),
                    rebuild_body=True,
                    rebuild_part=True,
                    rebuild_motion=True,
                    rebuild_task=True,
                )
            )

            save_path = self.gui.add_text(
                "Save JSON",
                str(self.session.out_path),
                hint="CreatureSpec output path.",
            )
            save_button = self.gui.add_button("Save JSON", icon="device-floppy")
            save_button.on_click(
                lambda _event: self._safe(
                    lambda: self.session.save(Path(save_path.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

        self._rebuild_body_controls()
        self._rebuild_part_controls()
        self._rebuild_motion_controls()
        self._rebuild_task_controls()

        with self.gui.add_folder("Run", expand_by_default=True):
            validate = self.gui.add_button("Validate", icon="check")
            validate.on_click(lambda _event: self._update_status())
            self._simulate_button = self.gui.add_button("Simulate", icon="player-play")
            self._simulate_button.on_click(lambda _event: self._simulate())
            self._message = self.gui.add_markdown("")
        self._update_status()

    def scene_selected(self, part_id: str) -> None:
        self._safe(
            lambda: self.session.select_part(part_id),
            rebuild_body=False,
            rebuild_part=True,
            rebuild_motion=False,
            rebuild_task=False,
        )

    def scene_changed(self) -> None:
        self._update_status()

    def _safe(
        self,
        operation: Callable[[], Any],
        *,
        rebuild_body: bool,
        rebuild_part: bool,
        rebuild_motion: bool,
        rebuild_task: bool,
    ) -> None:
        try:
            operation()
        except Exception as exc:
            self.session.last_message = f"Error: {exc}"
        self._refresh(
            rebuild_body=rebuild_body,
            rebuild_part=rebuild_part,
            rebuild_motion=rebuild_motion,
            rebuild_task=rebuild_task,
        )

    def _refresh(
        self,
        *,
        rebuild_body: bool,
        rebuild_part: bool,
        rebuild_motion: bool,
        rebuild_task: bool,
    ) -> None:
        if rebuild_body:
            self._rebuild_body_controls()
        if rebuild_part:
            self._rebuild_part_controls()
        if rebuild_motion:
            self._rebuild_motion_controls()
        if rebuild_task:
            self._rebuild_task_controls()
        self.on_preview()
        self._update_status()

    def _remove_folder(self, attr: str) -> None:
        folder = getattr(self, attr)
        if folder is not None:
            try:
                folder.remove()
            except Exception:
                pass
        setattr(self, attr, None)

    def _rebuild_body_controls(self) -> None:
        self._remove_folder("_body_folder")
        self._body_folder = self.gui.add_folder("Body", expand_by_default=True)
        with self._body_folder:
            if self.session.template == "custom":
                self.gui.add_markdown(
                    "Loaded JSON is custom. Use **Selected part** and **Motion** controls."
                )
                return
            preset = presets.CREATURE_PRESETS[self.session.template]
            self.gui.add_markdown(f"Template: **{preset.label}**")
            for param in preset.params:
                value = self.session.params[param.key]
                slider = self.gui.add_slider(
                    param.label,
                    min=param.minimum,
                    max=param.maximum,
                    step=param.step,
                    initial_value=int(value) if param.kind == "int" else value,
                )
                slider.on_update(
                    lambda event, key=param.key: self._safe(
                        lambda: self.session.set_body_param(key, float(event.target.value)),
                        rebuild_body=False,
                        rebuild_part=True,
                        rebuild_motion=True,
                        rebuild_task=False,
                    )
                )

    def _rebuild_part_controls(self) -> None:
        self._remove_folder("_part_folder")
        self._part_folder = self.gui.add_folder("Selected part", expand_by_default=True)
        with self._part_folder:
            part = self.session.selected_part()
            part_select = self.gui.add_dropdown(
                "Part",
                self.session.part_ids(),
                initial_value=part.id,
            )
            part_select.on_update(
                lambda event: self._safe(
                    lambda: self.session.select_part(event.target.value),
                    rebuild_body=False,
                    rebuild_part=True,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

            shape = self.gui.add_dropdown(
                "Shape",
                [shape.value for shape in ShapeType],
                initial_value=part.shape.value,
            )
            shape.on_update(
                lambda event: self._safe(
                    lambda: self.session.update_selected_part(shape=event.target.value),
                    rebuild_body=False,
                    rebuild_part=True,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

            mass = self.gui.add_slider(
                "Mass",
                min=0.01,
                max=max(5.0, part.mass * 3),
                step=0.01,
                initial_value=part.mass,
            )
            mass.on_update(
                lambda event: self._safe(
                    lambda: self.session.update_selected_part(mass=float(event.target.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

            color = tuple(int(round(channel * 255)) for channel in (part.color or (0.6, 0.6, 0.6)))
            color_handle = self.gui.add_rgb("Color", color)
            color_handle.on_update(
                lambda event: self._safe(
                    lambda: self.session.update_selected_part(color=event.target.value),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

            if part.shape == ShapeType.BOX and part.size is not None:
                self._add_size_slider("Size X", 0, part.size)
                self._add_size_slider("Size Y", 1, part.size)
                self._add_size_slider("Size Z", 2, part.size)
            elif part.shape == ShapeType.SPHERE and part.radius is not None:
                radius = self.gui.add_slider(
                    "Radius", min=0.005, max=0.5, step=0.005, initial_value=part.radius
                )
                radius.on_update(
                    lambda event: self._safe(
                        lambda: self.session.update_selected_part(radius=float(event.target.value)),
                        rebuild_body=False,
                        rebuild_part=False,
                        rebuild_motion=False,
                        rebuild_task=False,
                    )
                )
            else:
                radius = self.gui.add_slider(
                    "Radius",
                    min=0.005,
                    max=0.25,
                    step=0.005,
                    initial_value=part.radius or 0.03,
                )
                radius.on_update(
                    lambda event: self._safe(
                        lambda: self.session.update_selected_part(radius=float(event.target.value)),
                        rebuild_body=False,
                        rebuild_part=False,
                        rebuild_motion=False,
                        rebuild_task=False,
                    )
                )
                length = self.gui.add_slider(
                    "Length",
                    min=0.02,
                    max=1.2,
                    step=0.01,
                    initial_value=part.length or 0.2,
                )
                length.on_update(
                    lambda event: self._safe(
                        lambda: self.session.update_selected_part(length=float(event.target.value)),
                        rebuild_body=False,
                        rebuild_part=False,
                        rebuild_motion=False,
                        rebuild_task=False,
                    )
                )

            add_limb = self.gui.add_button("Add limb", icon="plus")
            add_limb.on_click(
                lambda _event: self._safe(
                    self.session.add_limb,
                    rebuild_body=False,
                    rebuild_part=True,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )
            delete = self.gui.add_button("Delete part", icon="trash")
            delete.on_click(
                lambda _event: self._safe(
                    self.session.delete_selected_part,
                    rebuild_body=False,
                    rebuild_part=True,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )
            mirror_left = self.gui.add_button("Mirror left to right", icon="copy")
            mirror_left.on_click(
                lambda _event: self._safe(
                    lambda: self.session.mirror("left"),
                    rebuild_body=False,
                    rebuild_part=True,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )
            mirror_right = self.gui.add_button("Mirror right to left", icon="copy")
            mirror_right.on_click(
                lambda _event: self._safe(
                    lambda: self.session.mirror("right"),
                    rebuild_body=False,
                    rebuild_part=True,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )

    def _add_size_slider(
        self, label: str, index: int, current_size: tuple[float, float, float]
    ) -> None:
        slider = self.gui.add_slider(
            label,
            min=0.01,
            max=1.2,
            step=0.01,
            initial_value=current_size[index],
        )
        slider.on_update(
            lambda event: self._safe(
                lambda: self._set_box_size(index, float(event.target.value)),
                rebuild_body=False,
                rebuild_part=False,
                rebuild_motion=False,
                rebuild_task=False,
            )
        )

    def _set_box_size(self, index: int, value: float) -> None:
        part = self.session.selected_part()
        size = list(part.size or (0.2, 0.2, 0.1))
        size[index] = value
        self.session.update_selected_part(size=tuple(size))

    def _rebuild_motion_controls(self) -> None:
        self._remove_folder("_motion_folder")
        self._motion_folder = self.gui.add_folder("Motion", expand_by_default=False)
        with self._motion_folder:
            if not self.session.creature.motors:
                self.gui.add_markdown("No motors yet. Add a hinged limb to create one.")
                return
            gait = self.gui.add_dropdown(
                "Gait preset",
                ["current", "trot", "pace", "wave", "still"],
                initial_value="current",
            )
            gait.on_update(
                lambda event: self._safe(
                    lambda: self.session.apply_gait(event.target.value),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )
            motor_id = self.session.selected_motor()
            motor_select = self.gui.add_dropdown(
                "Joint motor",
                self.session.motor_ids(),
                initial_value=motor_id,
            )
            motor_select.on_update(
                lambda event: self._safe(
                    lambda: self.session.select_motor(event.target.value),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=True,
                    rebuild_task=False,
                )
            )
            motor = next(m for m in self.session.creature.motors if m.joint == motor_id)
            amplitude = self.gui.add_slider(
                "Amplitude", min=0.0, max=1.8, step=0.05, initial_value=motor.amplitude
            )
            amplitude.on_update(
                lambda event: self._safe(
                    lambda: self.session.update_selected_motor(amplitude=float(event.target.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )
            frequency = self.gui.add_slider(
                "Frequency", min=0.0, max=6.0, step=0.1, initial_value=motor.frequency
            )
            frequency.on_update(
                lambda event: self._safe(
                    lambda: self.session.update_selected_motor(frequency=float(event.target.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )
            phase = self.gui.add_slider(
                "Phase", min=-6.28, max=6.28, step=0.05, initial_value=motor.phase
            )
            phase.on_update(
                lambda event: self._safe(
                    lambda: self.session.update_selected_motor(phase=float(event.target.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

    def _rebuild_task_controls(self) -> None:
        self._remove_folder("_task_folder")
        self._task_folder = self.gui.add_folder("Task", expand_by_default=False)
        with self._task_folder:
            task = self.gui.add_dropdown(
                "Task",
                presets.task_names(),
                initial_value=(
                    self.session.task_preset
                    if self.session.task_preset in presets.TASK_PRESETS
                    else "crawl_forward"
                ),
            )
            task.on_update(
                lambda event: self._safe(
                    lambda: self.session.set_task_preset(event.target.value),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=True,
                )
            )
            duration = self.gui.add_slider(
                "Duration",
                min=0.5,
                max=12.0,
                step=0.5,
                initial_value=self.session.task.duration,
            )
            duration.on_update(
                lambda event: self._safe(
                    lambda: self.session.set_task_duration(float(event.target.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )
            friction = self.gui.add_slider(
                "Friction",
                min=0.0,
                max=2.0,
                step=0.05,
                initial_value=self.session.task.terrain.friction,
            )
            friction.on_update(
                lambda event: self._safe(
                    lambda: self.session.set_task_friction(float(event.target.value)),
                    rebuild_body=False,
                    rebuild_part=False,
                    rebuild_motion=False,
                    rebuild_task=False,
                )
            )

    def _simulate(self) -> None:
        if self._simulate_button is not None:
            self._simulate_button.disabled = True
        try:
            self.session.last_message = self.on_simulate()
        except Exception as exc:
            self.session.last_message = f"Simulation failed: {exc}"
        finally:
            if self._simulate_button is not None:
                self._simulate_button.disabled = False
            self._update_status()

    def _update_status(self) -> None:
        status = self.session.status()
        metrics = self.session.preview_metrics()
        lines = [
            f"**{self.session.last_message}**",
            "",
            f"- Creature: `{self.session.creature.name}`",
            "- Parts/joints/motors: "
            f"{int(metrics['parts'])}/{int(metrics['joints'])}/{int(metrics['motors'])}",
            f"- CoM height: {metrics['com_z']:.2f} m",
            f"- Support width: {metrics['support_width']:.2f} m",
        ]
        if status.errors:
            lines.append("")
            lines.append("**Errors**")
            lines.extend(f"- {error}" for error in status.errors)
        if status.warnings:
            lines.append("")
            lines.append("**Warnings**")
            lines.extend(f"- {warning}" for warning in status.warnings[:4])
        if self._message is not None:
            self._message.content = "\n".join(lines)
        if self._simulate_button is not None:
            self._simulate_button.disabled = not status.ok
