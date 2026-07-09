"""Pure state and mutation logic for the Viser build editor."""

from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from creature_lab.editor import presets
from creature_lab.scaffold import mirror_limb
from creature_lab.schema import CreatureSpec, FrameState, PartSpec, TaskSpec
from creature_lab.schema.creature import MotorType, ShapeType
from creature_lab.validation import EpisodeInputError, validate_episode_inputs


@dataclass
class SessionStatus:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _clean_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "(root)"
        return f"{location}: {first['msg']}"
    return str(exc)


def _model_data(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


def _part_extent_z(part: PartSpec) -> float:
    if part.shape == ShapeType.BOX and part.size is not None:
        return part.size[2] / 2
    if part.shape == ShapeType.SPHERE and part.radius is not None:
        return part.radius
    if part.length is not None:
        return part.length / 2
    return 0.05


class EditorSession:
    """Editor state that can be unit-tested without Viser or physics imports."""

    def __init__(
        self,
        creature: CreatureSpec | None = None,
        task: TaskSpec | None = None,
        *,
        template: str = "quadruped",
        out_path: Path = Path("outputs/build_creature.json"),
        source_path: Path | None = None,
    ) -> None:
        if creature is None:
            self.template = template
            self.params = presets.default_params(template)
            creature = presets.generate_creature(template, self.params)
        else:
            self.template = "custom"
            self.params = {}
        self.creature = creature
        self.task_preset = "crawl_forward"
        self.task = task or presets.generate_task(self.task_preset)
        self.out_path = out_path
        self.source_path = source_path
        self.selected_part_id = self.creature.parts[0].id
        self.selected_motor_id = self.creature.motors[0].joint if self.creature.motors else ""
        self.last_message = "Ready."

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        task: TaskSpec | None = None,
        out_path: Path | None = None,
    ) -> EditorSession:
        creature = CreatureSpec.model_validate(json.loads(path.read_text()))
        return cls(creature, task, out_path=out_path or path, source_path=path)

    def load_path(self, path: Path) -> None:
        loaded = self.from_path(path, task=self.task, out_path=self.out_path)
        self.template = loaded.template
        self.params = loaded.params
        self.creature = loaded.creature
        self.source_path = path
        self.selected_part_id = self.creature.parts[0].id
        self.selected_motor_id = self.creature.motors[0].joint if self.creature.motors else ""
        self.last_message = f"Loaded {path}"

    def apply_template(self, template: str) -> None:
        self.template = template
        self.params = presets.default_params(template)
        self.creature = presets.generate_creature(template, self.params)
        self.selected_part_id = self.creature.parts[0].id
        self.selected_motor_id = self.creature.motors[0].joint if self.creature.motors else ""
        self.last_message = f"Started from {presets.preset_label(template)}"

    def set_body_param(self, key: str, value: float) -> None:
        if self.template == "custom":
            self.last_message = "Loaded JSON is custom; use part and motor controls to edit it."
            return
        self.params[key] = value
        previous_part = self.selected_part_id
        previous_motor = self.selected_motor_id
        self.creature = presets.generate_creature(self.template, self.params)
        next_part = previous_part if previous_part in self.part_ids() else self.creature.parts[0].id
        self.select_part(next_part)
        if previous_motor in self.motor_ids():
            self.selected_motor_id = previous_motor
        elif self.creature.motors:
            self.selected_motor_id = self.creature.motors[0].joint
        else:
            self.selected_motor_id = ""
        self.last_message = f"Updated {key}"

    def set_name(self, name: str) -> None:
        data = _model_data(self.creature)
        data["name"] = name.strip() or self.creature.name
        self.creature = CreatureSpec.model_validate(data)
        self.last_message = f"Renamed to {self.creature.name}"

    def set_task_preset(self, name: str) -> None:
        self.task_preset = name
        self.task = presets.generate_task(name)
        self.last_message = f"Task set to {name}"

    def set_task_duration(self, duration: float) -> None:
        self.task = presets.generate_task(
            self.task_preset, duration=duration, friction=self.task.terrain.friction
        )
        self.last_message = f"Task duration set to {duration:.1f}s"

    def set_task_friction(self, friction: float) -> None:
        self.task = presets.generate_task(
            self.task_preset, duration=self.task.duration, friction=friction
        )
        self.last_message = f"Terrain friction set to {friction:.2f}"

    def part_ids(self) -> list[str]:
        return [part.id for part in self.creature.parts]

    def motor_ids(self) -> list[str]:
        return [motor.joint for motor in self.creature.motors]

    def selected_part(self) -> PartSpec:
        for part in self.creature.parts:
            if part.id == self.selected_part_id:
                return part
        self.selected_part_id = self.creature.parts[0].id
        return self.creature.parts[0]

    def select_part(self, part_id: str) -> None:
        if part_id in self.part_ids():
            self.selected_part_id = part_id
            self.last_message = f"Selected {part_id}"

    def selected_motor(self) -> str:
        if self.selected_motor_id in self.motor_ids():
            return self.selected_motor_id
        self.selected_motor_id = self.creature.motors[0].joint if self.creature.motors else ""
        return self.selected_motor_id

    def select_motor(self, joint_id: str) -> None:
        if joint_id in self.motor_ids():
            self.selected_motor_id = joint_id
            self.last_message = f"Selected motor {joint_id}"

    def update_selected_part(
        self,
        *,
        shape: str | None = None,
        mass: float | None = None,
        radius: float | None = None,
        length: float | None = None,
        size: tuple[float, float, float] | None = None,
        color: tuple[int, int, int] | None = None,
    ) -> None:
        part_id = self.selected_part_id
        data = _model_data(self.creature)
        for part in data["parts"]:
            if part["id"] != part_id:
                continue
            if mass is not None:
                part["mass"] = max(0.001, mass)
            if color is not None:
                part["color"] = [channel / 255 for channel in color]
            if shape is not None and shape != part["shape"]:
                part["shape"] = shape
                part.pop("size", None)
                part.pop("radius", None)
                part.pop("length", None)
                if shape == ShapeType.BOX:
                    part["size"] = [0.2, 0.2, 0.1]
                elif shape == ShapeType.SPHERE:
                    part["radius"] = 0.08
                else:
                    part["radius"] = 0.03
                    part["length"] = 0.2
            if part["shape"] == ShapeType.BOX and size is not None:
                part["size"] = [max(0.001, value) for value in size]
            elif part["shape"] == ShapeType.SPHERE and radius is not None:
                part["radius"] = max(0.001, radius)
            elif part["shape"] in {ShapeType.CAPSULE, ShapeType.CYLINDER}:
                if radius is not None:
                    part["radius"] = max(0.001, radius)
                if length is not None:
                    part["length"] = max(0.001, length)
            break
        self.creature = CreatureSpec.model_validate(data)
        self.last_message = f"Updated {part_id}"

    def update_selected_motor(
        self,
        *,
        amplitude: float | None = None,
        frequency: float | None = None,
        phase: float | None = None,
    ) -> None:
        joint_id = self.selected_motor()
        if not joint_id:
            return
        data = _model_data(self.creature)
        for motor in data["motors"]:
            if motor["joint"] == joint_id:
                if amplitude is not None:
                    motor["amplitude"] = max(0.0, amplitude)
                if frequency is not None:
                    motor["frequency"] = max(0.0, frequency)
                if phase is not None:
                    motor["phase"] = phase
                break
        self.creature = CreatureSpec.model_validate(data)
        self.last_message = f"Updated motor {joint_id}"

    def move_selected_anchor_to(self, world_position: tuple[float, float, float]) -> None:
        """Move the selected part's parent joint anchor to a preview-space position."""
        part_id = self.selected_part_id
        joint = next((joint for joint in self.creature.joints if joint.child == part_id), None)
        if joint is None:
            self.last_message = "Root part has no parent joint anchor to move."
            return
        frame = self.preview_frame()
        parent_pose = frame.parts[joint.parent]
        anchor = [
            world_position[0] - parent_pose.position[0],
            world_position[1] - parent_pose.position[1],
            world_position[2] - parent_pose.position[2],
        ]
        data = _model_data(self.creature)
        for joint_data in data["joints"]:
            if joint_data["id"] == joint.id:
                joint_data["anchor"] = anchor
                break
        self.creature = CreatureSpec.model_validate(data)
        self.last_message = f"Moved anchor {joint.id}"

    def apply_gait(self, gait: str) -> None:
        data = _model_data(self.creature)
        motors = data.get("motors", [])
        if gait == "still":
            for motor in motors:
                motor["amplitude"] = 0.0
        elif gait == "pace":
            for motor in motors:
                joint = motor["joint"]
                motor["phase"] = math.pi if joint.endswith("r") else 0.0
        elif gait == "trot":
            for index, motor in enumerate(motors):
                motor["phase"] = math.pi if index % 2 else 0.0
        elif gait == "wave":
            for index, motor in enumerate(motors):
                motor["phase"] = -1.2 * index
        else:
            return
        self.creature = CreatureSpec.model_validate(data)
        if self.creature.motors:
            self.selected_motor_id = self.creature.motors[0].joint
        self.last_message = f"Applied {gait} gait"

    def add_limb(self) -> None:
        parent = self.selected_part_id
        data = _model_data(self.creature)
        index = 1
        existing = set(self.part_ids())
        while f"limb_{index}" in existing:
            index += 1
        limb_id = f"limb_{index}"
        joint_id = f"{parent}_to_{limb_id}"
        data["parts"].append(
            {
                "id": limb_id,
                "shape": "capsule",
                "length": 0.22,
                "radius": 0.03,
                "mass": 0.15,
                "color": [0.35, 0.75, 0.95],
            }
        )
        data.setdefault("joints", []).append(
            {
                "id": joint_id,
                "parent": parent,
                "child": limb_id,
                "type": "hinge",
                "anchor": [0.0, 0.0, -max(0.04, _part_extent_z(self.selected_part()))],
                "axis": [0, 1, 0],
                "limit": [-1.2, 1.2],
            }
        )
        data.setdefault("motors", []).append(
            {
                "joint": joint_id,
                "type": MotorType.SINUSOID,
                "amplitude": 0.6,
                "frequency": 2.0,
                "phase": 0.0,
            }
        )
        self.creature = CreatureSpec.model_validate(data)
        self.selected_part_id = limb_id
        self.selected_motor_id = joint_id
        self.last_message = f"Added {limb_id}"

    def delete_selected_part(self) -> None:
        part_id = self.selected_part_id
        roots = set(self.part_ids()) - {joint.child for joint in self.creature.joints}
        if part_id in roots:
            self.last_message = "Root part cannot be deleted."
            return

        children = defaultdict(list)
        for joint in self.creature.joints:
            children[joint.parent].append(joint.child)
        remove = {part_id}
        queue: deque[str] = deque([part_id])
        while queue:
            current = queue.popleft()
            for child in children[current]:
                if child not in remove:
                    remove.add(child)
                    queue.append(child)

        data = _model_data(self.creature)
        removed_joints = {
            joint["id"]
            for joint in data["joints"]
            if joint["child"] in remove or joint["parent"] in remove
        }
        data["parts"] = [part for part in data["parts"] if part["id"] not in remove]
        data["joints"] = [joint for joint in data["joints"] if joint["id"] not in removed_joints]
        data["motors"] = [
            motor for motor in data.get("motors", []) if motor["joint"] not in removed_joints
        ]
        self.creature = CreatureSpec.model_validate(data)
        self.selected_part_id = self.creature.parts[0].id
        self.selected_motor_id = self.creature.motors[0].joint if self.creature.motors else ""
        self.last_message = f"Deleted {', '.join(sorted(remove))}"

    def mirror(self, side: str) -> None:
        self.creature = mirror_limb(self.creature, side=side)
        self.selected_part_id = self.creature.parts[0].id
        self.selected_motor_id = self.creature.motors[0].joint if self.creature.motors else ""
        self.last_message = f"Mirrored {side} limbs"

    def status(self) -> SessionStatus:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            CreatureSpec.model_validate(_model_data(self.creature))
        except ValidationError as exc:
            errors.append(_clean_message(exc))
        try:
            TaskSpec.model_validate(_model_data(self.task))
        except ValidationError as exc:
            errors.append(_clean_message(exc))
        if not errors:
            try:
                warnings.extend(validate_episode_inputs(self.creature, self.task))
            except EpisodeInputError as exc:
                errors.append(str(exc))
        return SessionStatus(ok=not errors, errors=errors, warnings=warnings)

    def save(self, path: Path | None = None) -> Path:
        target = path or self.out_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.creature.model_dump_json(indent=2, exclude_none=True))
        self.out_path = target
        self.last_message = f"Saved {target}"
        return target

    def preview_frame(self) -> FrameState:
        child_to_joint = {joint.child: joint for joint in self.creature.joints}
        children = defaultdict(list)
        for joint in self.creature.joints:
            children[joint.parent].append(joint.child)
        roots = [part.id for part in self.creature.parts if part.id not in child_to_joint]
        root = roots[0]
        parts_by_id = {part.id: part for part in self.creature.parts}
        positions: dict[str, tuple[float, float, float]] = {}
        orientations: dict[str, tuple[float, float, float, float]] = {}
        positions[root] = (0.0, 0.0, _part_extent_z(parts_by_id[root]))
        orientations[root] = (1.0, 0.0, 0.0, 0.0)

        queue: deque[str] = deque([root])
        while queue:
            parent = queue.popleft()
            parent_position = positions[parent]
            for child in children[parent]:
                joint = child_to_joint[child]
                child_part = parts_by_id[child]
                anchor = joint.anchor
                z_offset = 0.0
                if child_part.shape in {ShapeType.CAPSULE, ShapeType.CYLINDER} and anchor[2] < 0:
                    z_offset = -_part_extent_z(child_part)
                positions[child] = (
                    parent_position[0] + anchor[0],
                    parent_position[1] + anchor[1],
                    max(0.02, parent_position[2] + anchor[2] + z_offset),
                )
                orientations[child] = joint.rest_orientation
                queue.append(child)

        return FrameState.model_validate(
            {
                "t": 0.0,
                "parts": {
                    part_id: {"position": positions[part_id], "orientation": orientations[part_id]}
                    for part_id in positions
                },
                "score": 0.0,
            }
        )

    def preview_metrics(self) -> dict[str, float]:
        frame = self.preview_frame()
        mass_total = 0.0
        weighted = [0.0, 0.0, 0.0]
        support_y: list[float] = []
        for part in self.creature.parts:
            pose = frame.parts.get(part.id)
            if pose is None:
                continue
            mass_total += part.mass
            for i, value in enumerate(pose.position):
                weighted[i] += value * part.mass
            if pose.position[2] <= _part_extent_z(part) + 0.04:
                support_y.append(pose.position[1])
        com = [value / mass_total for value in weighted] if mass_total else [0.0, 0.0, 0.0]
        support_width = max(support_y) - min(support_y) if len(support_y) >= 2 else 0.0
        return {
            "com_x": com[0],
            "com_y": com[1],
            "com_z": com[2],
            "support_width": support_width,
            "parts": float(len(self.creature.parts)),
            "joints": float(len(self.creature.joints)),
            "motors": float(len(self.creature.motors)),
        }
