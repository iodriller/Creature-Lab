"""Build a runtime controller callable from a portable ``ControllerSpec``.

This is the one place that turns the JSON artifact (``creature_lab.schema.
controller.ControllerSpec``) into an actual ``(t, prev_frame) -> targets`` callable,
by constructing the existing controller implementations. It never invents new control
logic - it is purely a spec-to-object translation layer, matching how
``cli._make_controller`` already dispatches on a name string; this is the equivalent
for a saved ``controller.json``. ``extract_sinusoid_spec`` below is the inverse
direction (creature -> spec), for migrating a creature's own gait into one.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

from creature_lab.controllers.cpg import CPGController
from creature_lab.controllers.posture import PostureController
from creature_lab.controllers.target_seek import TargetSeekController
from creature_lab.hashing import spec_hash
from creature_lab.schema import ControllerSpec, ControllerType, CreatureSpec, FrameState, TaskSpec
from creature_lab.schema.creature import JointType

#: (t, prev_frame) -> {joint_id: target_angle}, matching the existing open-loop
#: controller callables (CPGController, sinusoid_targets, TargetSeekController).
ControllerFn = Callable[[float, "FrameState | None"], dict[str, float]]


def _sinusoid_controller(spec: ControllerSpec) -> ControllerFn:
    if spec.motors is None:  # defensive if called with an unvalidated model copy
        raise ValueError("sinusoid controller requires motors")
    motors = list(spec.motors)

    def controller(t: float, prev_frame: FrameState | None = None) -> dict[str, float]:
        return {
            motor.joint: motor.offset
            + motor.amplitude * math.sin(2 * math.pi * motor.frequency * t + motor.phase)
            for motor in motors
        }

    return controller


def _cpg_kwargs(spec: ControllerSpec) -> dict[str, float]:
    kwargs: dict[str, float] = {}
    if spec.amplitude is not None:
        kwargs["amplitude"] = spec.amplitude
    if spec.frequency is not None:
        kwargs["frequency"] = spec.frequency
    if spec.phase_lag is not None:
        kwargs["phase_lag"] = spec.phase_lag
    if spec.coupling is not None:
        kwargs["coupling"] = spec.coupling
    return kwargs


def build_controller(
    spec: ControllerSpec,
    creature: CreatureSpec,
    task: TaskSpec | None = None,
    *,
    base_dir: Path | None = None,
) -> ControllerFn:
    """Construct the runtime controller a ``ControllerSpec`` describes.

    Unset tuning fields fall back to the wrapped controller's own defaults (e.g. a
    bare ``{"type": "cpg"}`` behaves exactly like ``CPGController(creature)``).
    Raises ``ValueError`` for a ``target_seek`` spec without a target-having task,
    matching ``cli._make_controller``'s equivalent check for the ``--controller
    target_seek`` CLI/editor path. ``base_dir`` (the directory the ``controller.json``
    itself lives in, if loaded from a file) resolves a ``policy`` spec's
    ``policy_file`` - required for that type, unused by every other type.
    """
    hinge_ids = {joint.id for joint in creature.joints if joint.type == JointType.HINGE}
    if spec.type == ControllerType.HOLD:
        return lambda _t, _prev=None: {}
    if spec.type == ControllerType.SINUSOID:
        if spec.motors is None:
            raise ValueError("sinusoid controller requires motors")
        unknown = {motor.joint for motor in spec.motors} - hinge_ids
        if unknown:
            raise ValueError(f"sinusoid controller references non-hinge joints: {sorted(unknown)}")
        return _sinusoid_controller(spec)

    if spec.type == ControllerType.CPG:
        return CPGController(creature, **_cpg_kwargs(spec))

    if spec.type == ControllerType.TARGET_SEEK:
        if task is None or task.target is None:
            raise ValueError("target_seek controller requires a task with a target")
        cpg_kwargs = _cpg_kwargs(spec)
        cpg = CPGController(creature, **cpg_kwargs) if cpg_kwargs else None
        steer_kwargs: dict[str, float] = {}
        if spec.turn_gain is not None:
            steer_kwargs["turn_gain"] = spec.turn_gain
        if spec.max_turn_scale is not None:
            steer_kwargs["max_turn_scale"] = spec.max_turn_scale
        if spec.slow_radius is not None:
            steer_kwargs["slow_radius"] = spec.slow_radius
        if spec.stop_radius is not None:
            steer_kwargs["stop_radius"] = spec.stop_radius
        return TargetSeekController(creature, task, cpg=cpg, **steer_kwargs)

    if spec.type == ControllerType.POSTURE:
        posture_kwargs: dict[str, float] = {}
        if spec.kp is not None:
            posture_kwargs["kp"] = spec.kp
        if spec.kd is not None:
            posture_kwargs["kd"] = spec.kd
        return PostureController(creature, **posture_kwargs)

    if spec.type == ControllerType.POLICY:
        if spec.policy_file is None:
            raise ValueError("policy controller requires policy_file")
        if task is None:
            raise ValueError("policy controller requires a task")
        if spec.creature_hash is not None and spec.creature_hash != spec_hash(creature):
            raise ValueError("policy was trained for a different creature artifact")
        if spec.task_hash is not None and spec.task_hash != spec_hash(task):
            raise ValueError("policy was trained for a different task artifact")
        if spec.action is not None:
            unknown = set(spec.action.joints) - hinge_ids
            if unknown:
                raise ValueError(
                    f"policy action ABI references non-hinge joints: {sorted(unknown)}"
                )
        from creature_lab.controllers.policy import PolicyController

        base = base_dir if base_dir is not None else Path()
        policy_path = base / spec.policy_file
        if not policy_path.exists():
            raise ValueError(f"policy file not found: {policy_path}")
        return PolicyController(
            creature,
            task,
            policy_path,
            obs_spec=spec.observation,
            action_spec=spec.action,
        )

    raise ValueError(f"unknown controller type {spec.type!r}")  # pragma: no cover - exhaustive enum


def controller_fits(controller_path: Path, creature: CreatureSpec) -> bool:
    """True when a packaged sinusoid controller can still drive this creature.

    Checks joint-id compatibility (every joint the gait commands is still a hinge
    on this body) - the same test ``controller validate`` uses - rather than an
    exact spec match. A packaged gait is keyed purely by joint id, so resizing a
    part, retuning an amplitude, or changing mass/color doesn't invalidate it; only
    removing/renaming the joints it drives does. Requiring an exact hash match
    instead would silently drop the packaged gait for the *first* edit a user makes
    in the build editor - see docs/KNOWN_ISSUES.md.
    """
    try:
        spec = ControllerSpec.model_validate_json(controller_path.read_text())
    except (OSError, ValueError):
        return False
    if spec.type != ControllerType.SINUSOID or not spec.motors:
        return False
    hinge_joints = {joint.id for joint in creature.joints if joint.type == JointType.HINGE}
    spec_joints = {motor.joint for motor in spec.motors}
    return spec_joints <= hinge_joints


def curated_controller(creature: CreatureSpec) -> str:
    """Best packaged first-run controller, with safe fallbacks for edited bodies.

    Used both by the CLI (``--controller curated``) and the build editor, so a
    creature's "curated" gait resolves identically whether it's run from the
    command line or the browser panel.
    """
    try:
        from creature_lab.zoo import zoo_optimized_controller

        optimized = zoo_optimized_controller(creature.name)
        if optimized is not None and controller_fits(optimized, creature):
            return str(optimized)
    except (KeyError, OSError, ValueError):
        pass
    if creature.name.startswith("humanoid"):
        return "posture"
    return "cpg" if creature.motors else "hold"


def extract_sinusoid_spec(creature: CreatureSpec, *, name: str = "controller") -> ControllerSpec:
    """Migrate a creature's own ``MotorSpec`` gait into an explicit, portable
    sinusoid ``ControllerSpec`` - the "legacy sinusoid" migration path: the result
    reproduces exactly what running that creature with ``--controller sinusoid``
    already does, just as a standalone, shareable artifact.
    """
    if not creature.motors:
        raise ValueError(f"creature {creature.name!r} has no motors to extract")
    return ControllerSpec(
        name=name,
        type=ControllerType.SINUSOID,
        motors=[
            {
                "joint": motor.joint,
                "amplitude": motor.amplitude,
                "frequency": motor.frequency,
                "phase": motor.phase,
                "offset": motor.offset,
            }
            for motor in creature.motors
        ],
    )
