"""MuJoCo implementation of the SimBackend protocol.

Only this module imports ``mujoco``. The model is built at runtime from the MJCF
exporter (``export_mjcf``), so the creature spec stays the single source of truth.
Scoring reuses the backend-neutral ``scoring`` module, exactly like the PyBullet
backend, so the two engines score episodes the same way (even though their exact
dynamics differ — see docs/archive/MVP_PLAN.md on portability).
"""

from __future__ import annotations

import math

import mujoco
import numpy as np

from creature_lab.export.mjcf import export_mjcf
from creature_lab.schema import CreatureSpec, PartPose, TaskSpec
from creature_lab.schema.creature import JointType
from creature_lab.schema.trace import ContactSpec, FrameState
from creature_lab.scoring import score_components
from creature_lab.terrain import is_flat, normalized_heightfield_data


def backend_version() -> str:
    """Human-readable MuJoCo backend version."""
    return f"mujoco {mujoco.__version__}"


class MuJoCoBackend:
    """Builds a creature as a MuJoCo model and steps it."""

    def __init__(self, gui: bool = False) -> None:
        # gui is accepted for protocol parity; this backend renders via traces.
        self._creature: CreatureSpec | None = None
        self._task: TaskSpec | None = None
        self._model: mujoco.MjModel | None = None
        self._data: mujoco.MjData | None = None
        self._root_body = ""
        self._ground_geom = -1
        self._geom_part: dict[int, str] = {}
        self._damaged: set[str] = set()
        self._t = 0.0
        self._energy = 0.0
        self._initial_root_x = 0.0
        self._initial_target_distance = 0.0
        self._last_score_components: dict[str, float] = {}
        self._damage_fired = False
        self._impulse_fired = False
        self._seed: int | None = None

    def build(self, creature: CreatureSpec, task: TaskSpec, *, seed: int | None = None) -> None:
        self._creature = creature
        self._task = task
        self._seed = seed
        xml = export_mjcf(
            creature, friction=task.terrain.friction, timestep=task.timestep, terrain=task.terrain
        )
        self._model = mujoco.MjModel.from_xml_string(xml)
        if not is_flat(task.terrain):
            self._model.hfield_data[:] = normalized_heightfield_data(task.terrain)
        self._data = mujoco.MjData(self._model)

        child_ids = {joint.child for joint in creature.joints}
        self._root_body = next(p.id for p in creature.parts if p.id not in child_ids)
        self._ground_geom = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_GEOM, "ground")
        # geom index -> part id (each part has exactly one geom, added in part order).
        self._geom_part = {}
        for part in creature.parts:
            body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, part.id)
            for geom in range(
                self._model.body_geomadr[body_id],
                self._model.body_geomadr[body_id] + self._model.body_geomnum[body_id],
            ):
                self._geom_part[geom] = part.id

        self._t = 0.0
        self._energy = 0.0
        self._damaged.clear()
        self._damage_fired = False
        self._impulse_fired = False
        mujoco.mj_forward(self._model, self._data)
        self._initial_root_x = float(self._root_pos()[0])
        self._initial_target_distance = (
            math.dist(self._root_pos(), task.target.position) if task.target is not None else 0.0
        )

    def reset(self) -> None:
        if self._creature is None or self._task is None:
            raise RuntimeError("build() must be called before reset()")
        self.build(self._creature, self._task, seed=self._seed)

    def step(self, dt: float) -> FrameState:
        if self._model is None or self._data is None or self._task is None:
            raise RuntimeError("build() must be called before step()")
        self._t += dt
        events: list[str] = []

        damage = self._task.damage_event
        if damage is not None and not self._damage_fired and self._t >= damage.time:
            self.damage_part(damage.part_id)
            self._damage_fired = True
            events.append(f"damage:{damage.part_id}")

        impulse = self._task.impulse_event
        if impulse is not None and not self._impulse_fired and self._t >= impulse.time:
            body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, impulse.part_id)
            self._data.xfrc_applied[body_id, :3] = impulse.force
            self._impulse_fired = True
            events.append(f"impulse:{impulse.part_id}")

        # ``step(dt)`` is part of the backend contract. Keep MuJoCo's actual
        # integrator step aligned with the requested duration instead of advancing
        # physics by a stale model timestep while only bookkeeping uses ``dt``.
        self._model.opt.timestep = dt
        mujoco.mj_step(self._model, self._data)
        if impulse is not None and self._impulse_fired:
            body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, impulse.part_id)
            self._data.xfrc_applied[body_id, :3] = 0.0  # one-step push only
        self._accumulate_energy(dt)

        frame = self._read_frame()
        if events:
            frame = frame.model_copy(update={"events": events})
        return frame

    def apply_motor_targets(self, targets: dict[str, float]) -> None:
        if self._model is None or self._data is None:
            raise RuntimeError("build() must be called before apply_motor_targets()")
        for joint_id, value in targets.items():
            if joint_id in self._damaged:
                continue
            actuator_id = mujoco.mj_name2id(
                self._model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"act_{joint_id}"
            )
            if actuator_id >= 0:
                self._data.ctrl[actuator_id] = value

    def apply_joint_control(self, targets: dict[str, float], mode: str = "position") -> None:
        """Position control of motored joints (used by CreatureEnv).

        The MJCF exports ``<position>`` servos, so only position mode is supported;
        velocity/torque control would need a different actuator model.
        """
        if mode != "position":
            raise NotImplementedError(
                f"MuJoCo backend supports position control only, not {mode!r}"
            )
        self.apply_motor_targets(targets)

    def damage_part(self, part_id: str) -> None:
        if self._creature is None:
            raise RuntimeError("build() must be called before damage_part()")
        # Disable the actuator on the joint that drives this part (best-effort parity
        # with PyBullet: the limb goes limp).
        for joint in self._creature.joints:
            if joint.child == part_id:
                self._damaged.add(joint.id)
                actuator_id = mujoco.mj_name2id(
                    self._model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"act_{joint.id}"
                )
                if actuator_id >= 0:
                    self._data.ctrl[actuator_id] = 0.0

    def close(self) -> None:
        self._model = None
        self._data = None

    def score_summary(self) -> dict[str, float]:
        return dict(self._last_score_components)

    def observe(self) -> FrameState:
        return self._read_frame()

    # -- internals --------------------------------------------------------------

    def _root_pos(self) -> tuple[float, float, float]:
        body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, self._root_body)
        return tuple(float(v) for v in self._data.xpos[body_id])

    def _accumulate_energy(self, dt: float) -> None:
        for joint in self._creature.joints:
            if joint.type != JointType.HINGE:
                continue
            jid = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_JOINT, joint.id)
            if jid < 0:
                continue
            velocity = float(self._data.qvel[self._model.jnt_dofadr[jid]])
            self._energy += velocity * velocity * dt

    def _read_frame(self) -> FrameState:
        parts: dict[str, PartPose] = {}
        for part in self._creature.parts:
            body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, part.id)
            position = tuple(float(v) for v in self._data.xpos[body_id])
            orientation = tuple(float(v) for v in self._data.xquat[body_id])  # MuJoCo: w,x,y,z
            parts[part.id] = PartPose(position=position, orientation=orientation)

        joint_angles: dict[str, float] = {}
        for joint in self._creature.joints:
            if joint.type != JointType.HINGE:
                continue
            jid = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_JOINT, joint.id)
            if jid >= 0:
                joint_angles[joint.id] = float(self._data.qpos[self._model.jnt_qposadr[jid]])

        root_position = self._root_pos()
        forward_distance = root_position[0] - self._initial_root_x
        target_progress = 0.0
        if self._task.target is not None:
            target_progress = self._initial_target_distance - math.dist(
                root_position, self._task.target.position
            )
        root_body = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, self._root_body)
        up_z = float(self._data.xmat[root_body].reshape(3, 3)[2, 2])

        self._last_score_components = score_components(
            self._task.reward,
            forward_distance=forward_distance,
            target_progress=target_progress,
            energy=self._energy,
            fallen=up_z < 0.5,
        )
        return FrameState(
            t=self._t,
            parts=parts,
            joint_angles=joint_angles,
            contacts=self._read_contacts(),
            score=self._last_score_components["total"],
        )

    def _read_contacts(self) -> list[ContactSpec]:
        contacts: list[ContactSpec] = []
        force = np.zeros(6)
        for i in range(self._data.ncon):
            contact = self._data.contact[i]
            part_geom = None
            if contact.geom1 == self._ground_geom:
                part_geom = contact.geom2
            elif contact.geom2 == self._ground_geom:
                part_geom = contact.geom1
            if part_geom is None or part_geom not in self._geom_part:
                continue
            mujoco.mj_contactForce(self._model, self._data, i, force)
            contacts.append(
                ContactSpec(
                    part_id=self._geom_part[part_geom],
                    position=tuple(float(v) for v in contact.pos),
                    normal=tuple(float(v) for v in contact.frame[:3]),
                    force=max(0.0, float(force[0])),  # normal component
                )
            )
        return contacts
