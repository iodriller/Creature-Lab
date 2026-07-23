"""Portable controller configuration schema.

A ``ControllerSpec`` is the fourth durable artifact alongside creature/task/trace:
it captures which movement policy drove (or should drive) an episode and its tunable
parameters, so a controller choice is reproducible from JSON rather than living only
as a CLI string. See ``creature_lab.controllers.factory.build_controller`` for what
actually turns a spec into a running controller, and ``creature_lab.diagnosis``/
``creature_lab.controllers`` for the controllers themselves - this module only
describes them, matching the "schema/ contains data models, never physics" boundary.

Deliberately a flat model with a ``type`` discriminator (matching this codebase's
existing pattern - see ``PartSpec``'s shape-dependent fields) rather than a pydantic
discriminated union, which isn't used anywhere else in this schema package yet.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePath

from pydantic import Field, model_validator

from creature_lab.schema.base import StrictModel
from creature_lab.schema.control import ActionSpec, ObservationSpec


class ControllerType(StrEnum):
    HOLD = "hold"
    SINUSOID = "sinusoid"
    CPG = "cpg"
    TARGET_SEEK = "target_seek"
    POSTURE = "posture"
    POLICY = "policy"


class MotorGaitSpec(StrictModel):
    """One joint's sinusoidal gait.

    Embedded directly in a sinusoid ``ControllerSpec`` (rather than referencing a
    creature's own motors) so the spec is self-contained and portable independent of
    which creature it's paired with - mirrors ``CreatureSpec.MotorSpec``'s
    amplitude/frequency/phase.
    """

    joint: str = Field(min_length=1)
    amplitude: float = Field(ge=0)
    frequency: float = Field(ge=0)
    phase: float = 0.0
    offset: float = 0.0

    @model_validator(mode="after")
    def clean_joint(self) -> MotorGaitSpec:
        if not self.joint.strip():
            raise ValueError("motor gait joint id must not be blank")
        return self


class ControllerSpec(StrictModel):
    """Movement policy configuration: which controller, and its parameters.

    ``type`` selects which controller ``creature_lab.controllers.factory.
    build_controller`` constructs. The type-specific tuning fields below (cpg gait
    shape, target_seek steering) are optional overrides - when left unset, the
    controller's own built-in defaults apply, same as calling
    ``CPGController(creature)``/``TargetSeekController(creature, task)`` directly.
    Only ``motors`` is strictly gated by type (required and non-empty for
    ``sinusoid``, forbidden otherwise) since mixing that up is the most likely
    source of confusion; the numeric tuning fields are left permissive across types
    rather than maintaining a large forbidden-combination matrix for fields a given
    controller simply never reads.
    """

    name: str = Field(min_length=1, default="controller")
    type: ControllerType

    # -- sinusoid: an explicit, portable copy of each joint's gait ------------------
    motors: list[MotorGaitSpec] | None = None

    # -- cpg (also used as target_seek's underlying gait) ---------------------------
    amplitude: float | None = Field(default=None, ge=0)
    frequency: float | None = Field(default=None, ge=0)
    phase_lag: float | None = None
    coupling: float | None = None

    # -- target_seek steering ---------------------------------------------------------
    turn_gain: float | None = None
    max_turn_scale: float | None = Field(default=None, ge=0)
    slow_radius: float | None = Field(default=None, gt=0)
    stop_radius: float | None = Field(default=None, ge=0)

    # -- posture: PD pitch-stabilization (see creature_lab.controllers.posture) -------
    kp: float | None = Field(default=None, ge=0)
    kd: float | None = Field(default=None, ge=0)

    # -- policy: a trained SB3 model (see creature_lab.controllers.policy) ------------
    #: Filename of the saved model (e.g. an SB3 ``PPO.save()`` zip), resolved relative
    #: to the directory this ``ControllerSpec`` was loaded from - a policy is a
    #: two-file bundle (``controller.json`` + the model file) that travels together,
    #: the same way a run bundles ``creature.json``/``task.json``/``trace.json``. Never
    #: an absolute path in the JSON itself, so the bundle stays portable if moved.
    policy_file: str | None = Field(default=None, min_length=1)
    #: Exact policy input/output ABI. New trained policies always include these;
    #: they stay optional so older bundles can still be loaded with a warning.
    observation: ObservationSpec | None = None
    action: ActionSpec | None = None
    creature_hash: str | None = None
    task_hash: str | None = None
    policy_format: str | None = None
    runtime_versions: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_motors_match_type(self) -> ControllerSpec:
        if self.type == ControllerType.SINUSOID:
            if not self.motors:
                raise ValueError("a sinusoid controller requires a non-empty 'motors' list")
            joint_ids = [motor.joint for motor in self.motors]
            if len(joint_ids) != len(set(joint_ids)):
                raise ValueError("sinusoid motor gait joints must be unique")
        elif self.motors is not None:
            raise ValueError(f"'motors' is only used by a sinusoid controller, not {self.type!r}")
        return self

    @model_validator(mode="after")
    def validate_policy_file_matches_type(self) -> ControllerSpec:
        if self.type == ControllerType.POLICY:
            if not self.policy_file:
                raise ValueError("a policy controller requires 'policy_file'")
        elif self.policy_file is not None:
            raise ValueError(
                f"'policy_file' is only used by a policy controller, not {self.type!r}"
            )
        return self

    @model_validator(mode="after")
    def validate_policy_metadata_matches_type(self) -> ControllerSpec:
        metadata = {
            "observation": self.observation,
            "action": self.action,
            "creature_hash": self.creature_hash,
            "task_hash": self.task_hash,
            "policy_format": self.policy_format,
            "runtime_versions": self.runtime_versions,
        }
        if self.type != ControllerType.POLICY:
            used = [name for name, value in metadata.items() if value is not None]
            if used:
                raise ValueError(
                    f"policy metadata fields are only used by a policy controller: {used}"
                )
        return self

    @model_validator(mode="after")
    def validate_portable_policy_path(self) -> ControllerSpec:
        if self.policy_file is None:
            return self
        path = PurePath(self.policy_file)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError("policy_file must be a filename in the controller bundle")
        if path.name in {"", "."}:
            raise ValueError("policy_file must be a non-blank filename")
        return self

    @model_validator(mode="after")
    def validate_target_radii(self) -> ControllerSpec:
        if (
            self.slow_radius is not None
            and self.stop_radius is not None
            and self.stop_radius > self.slow_radius
        ):
            raise ValueError("stop_radius must be less than or equal to slow_radius")
        return self

    @model_validator(mode="after")
    def reject_irrelevant_tuning_fields(self) -> ControllerSpec:
        """Fail loudly instead of silently ignoring fields for another controller type."""
        groups = {
            ControllerType.HOLD: set(),
            ControllerType.SINUSOID: {"motors"},
            ControllerType.CPG: {"amplitude", "frequency", "phase_lag", "coupling"},
            ControllerType.TARGET_SEEK: {
                "amplitude",
                "frequency",
                "phase_lag",
                "coupling",
                "turn_gain",
                "max_turn_scale",
                "slow_radius",
                "stop_radius",
            },
            ControllerType.POSTURE: {"kp", "kd"},
            ControllerType.POLICY: {
                "policy_file",
                "observation",
                "action",
                "creature_hash",
                "task_hash",
                "policy_format",
                "runtime_versions",
            },
        }
        tuning_fields = set().union(*groups.values())
        used = {field_name for field_name in tuning_fields if getattr(self, field_name) is not None}
        irrelevant = sorted(used - groups[self.type])
        if irrelevant:
            raise ValueError(
                f"fields are not used by controller type {self.type.value!r}: {irrelevant}"
            )
        return self
