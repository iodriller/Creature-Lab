"""Portable creature schema."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from creature_lab.schema.base import ColorRGB, JointLimit, Quaternion, StrictModel, Vector3


class ShapeType(StrEnum):
    BOX = "box"
    SPHERE = "sphere"
    CAPSULE = "capsule"
    CYLINDER = "cylinder"


class JointType(StrEnum):
    FIXED = "fixed"
    HINGE = "hinge"


class MotorType(StrEnum):
    SINUSOID = "sinusoid"


class PartSpec(StrictModel):
    id: str = Field(min_length=1)
    shape: ShapeType
    mass: float = Field(gt=0)
    color: ColorRGB | None = None
    size: Vector3 | None = None
    radius: float | None = Field(default=None, gt=0)
    length: float | None = Field(default=None, gt=0)

    @field_validator("id")
    @classmethod
    def clean_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("part id must not be blank")
        return value

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: Vector3 | None) -> Vector3 | None:
        if value is not None and any(component <= 0 for component in value):
            raise ValueError("size values must be positive")
        return value

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: ColorRGB | None) -> ColorRGB | None:
        if value is not None and any(component < 0 or component > 1 for component in value):
            raise ValueError("color values must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def validate_dimensions(self) -> PartSpec:
        if self.shape == ShapeType.BOX:
            if self.size is None:
                raise ValueError("box parts require size")
            if self.radius is not None or self.length is not None:
                raise ValueError("box parts must not set radius or length")
        elif self.shape == ShapeType.SPHERE:
            if self.radius is None:
                raise ValueError("sphere parts require radius")
            if self.size is not None or self.length is not None:
                raise ValueError("sphere parts must not set size or length")
        elif self.shape in {ShapeType.CAPSULE, ShapeType.CYLINDER}:
            if self.radius is None or self.length is None:
                raise ValueError("capsule and cylinder parts require radius and length")
            if self.size is not None:
                raise ValueError("capsule and cylinder parts must not set size")
        return self


class JointSpec(StrictModel):
    id: str = Field(min_length=1)
    parent: str = Field(min_length=1)
    child: str = Field(min_length=1)
    type: JointType
    anchor: Vector3 = (0.0, 0.0, 0.0)
    axis: Vector3 = (0.0, 1.0, 0.0)
    #: Resting orientation of the child part relative to the parent, scalar-first
    #: ``(w, x, y, z)``. Identity leaves the child axis-aligned with the parent; use
    #: this to angle limbs (e.g. splay legs outward).
    rest_orientation: Quaternion = (1.0, 0.0, 0.0, 0.0)
    limit: JointLimit | None = None

    @field_validator("id", "parent", "child")
    @classmethod
    def clean_names(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("joint identifiers must not be blank")
        return value

    @field_validator("rest_orientation")
    @classmethod
    def validate_rest_orientation(cls, value: Quaternion) -> Quaternion:
        if all(component == 0 for component in value):
            raise ValueError("rest_orientation must not be the zero quaternion")
        return value

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: JointLimit | None) -> JointLimit | None:
        if value is not None and value[0] >= value[1]:
            raise ValueError("joint limit minimum must be less than maximum")
        return value

    @model_validator(mode="after")
    def validate_joint(self) -> JointSpec:
        if self.parent == self.child:
            raise ValueError("joint parent and child must be different parts")
        if self.type == JointType.HINGE and all(component == 0 for component in self.axis):
            raise ValueError("hinge axis must not be zero")
        return self


class MotorSpec(StrictModel):
    joint: str = Field(min_length=1)
    type: MotorType = MotorType.SINUSOID
    amplitude: float = Field(ge=0)
    frequency: float = Field(ge=0)
    phase: float = 0.0

    @field_validator("joint")
    @classmethod
    def clean_joint(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("motor joint id must not be blank")
        return value


class CreatureSpec(StrictModel):
    name: str = Field(min_length=1)
    parts: list[PartSpec] = Field(min_length=1)
    joints: list[JointSpec] = Field(default_factory=list)
    motors: list[MotorSpec] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("creature name must not be blank")
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> CreatureSpec:
        part_ids = [part.id for part in self.parts]
        if len(part_ids) != len(set(part_ids)):
            raise ValueError("part ids must be unique")
        joint_ids = [joint.id for joint in self.joints]
        if len(joint_ids) != len(set(joint_ids)):
            raise ValueError("joint ids must be unique")
        part_id_set = set(part_ids)
        child_to_parent: dict[str, str] = {}
        adjacency: dict[str, list[str]] = {part_id: [] for part_id in part_id_set}
        for joint in self.joints:
            if joint.parent not in part_id_set:
                raise ValueError(f"joint {joint.id!r} parent {joint.parent!r} does not exist")
            if joint.child not in part_id_set:
                raise ValueError(f"joint {joint.id!r} child {joint.child!r} does not exist")
            if joint.child in child_to_parent:
                raise ValueError(f"part {joint.child!r} has more than one parent joint")
            child_to_parent[joint.child] = joint.parent
            adjacency[joint.parent].append(joint.child)
        roots = [part_id for part_id in part_ids if part_id not in child_to_parent]
        if len(roots) != 1:
            raise ValueError("creatures must have exactly one root part")
        self._validate_reachable_acyclic(roots[0], adjacency, part_id_set)
        known_joints = set(joint_ids)
        motor_joints: set[str] = set()
        for motor in self.motors:
            if motor.joint not in known_joints:
                raise ValueError(f"motor references unknown joint {motor.joint!r}")
            if motor.joint in motor_joints:
                raise ValueError(f"joint {motor.joint!r} has more than one motor")
            motor_joints.add(motor.joint)
        return self

    @staticmethod
    def _validate_reachable_acyclic(
        root: str, adjacency: dict[str, list[str]], all_parts: set[str]
    ) -> None:
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(part_id: str) -> None:
            if part_id in visiting:
                raise ValueError("creature joint graph must be acyclic")
            if part_id in visited:
                return
            visiting.add(part_id)
            for child_id in adjacency[part_id]:
                visit(child_id)
            visiting.remove(part_id)
            visited.add(part_id)

        visit(root)
        if visited != all_parts:
            raise ValueError("all parts must be reachable from the root part")
