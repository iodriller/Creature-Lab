"""PyBullet implementation of the SimBackend protocol.

Only this module may import pybullet. A joint's ``anchor`` is the child link's
origin in the parent's local frame, and its ``rest_orientation`` is the child's
resting orientation relative to the parent (so limbs can be angled, not just
axis-aligned).
"""

from __future__ import annotations

import math

import pybullet
import pybullet_data

from creature_lab.schema import CreatureSpec, PartPose, PartSpec, ShapeType, TaskSpec
from creature_lab.schema.creature import JointType
from creature_lab.schema.trace import EpisodeTrace, FrameState
from creature_lab.scoring import episode_score

_DEFAULT_COLOR = (0.6, 0.6, 0.6)
_DEFAULT_HINGE_LIMIT = (-math.pi, math.pi)
_MOTOR_MAX_FORCE = 5.0


def _collision_geometry(part: PartSpec) -> tuple[int, dict]:
    # createCollisionShape spells the capsule/cylinder height parameter "height".
    if part.shape == ShapeType.BOX:
        return pybullet.GEOM_BOX, {"halfExtents": [size / 2 for size in part.size]}
    if part.shape == ShapeType.SPHERE:
        return pybullet.GEOM_SPHERE, {"radius": part.radius}
    if part.shape in (ShapeType.CAPSULE, ShapeType.CYLINDER):
        geom = pybullet.GEOM_CAPSULE if part.shape == ShapeType.CAPSULE else pybullet.GEOM_CYLINDER
        return geom, {"radius": part.radius, "height": part.length}
    raise ValueError(f"unsupported shape {part.shape!r}")


def _visual_geometry(part: PartSpec) -> tuple[int, dict]:
    # createVisualShape spells the same parameter "length" instead of "height".
    if part.shape == ShapeType.BOX:
        return pybullet.GEOM_BOX, {"halfExtents": [size / 2 for size in part.size]}
    if part.shape == ShapeType.SPHERE:
        return pybullet.GEOM_SPHERE, {"radius": part.radius}
    if part.shape in (ShapeType.CAPSULE, ShapeType.CYLINDER):
        geom = pybullet.GEOM_CAPSULE if part.shape == ShapeType.CAPSULE else pybullet.GEOM_CYLINDER
        return geom, {"radius": part.radius, "length": part.length}
    raise ValueError(f"unsupported shape {part.shape!r}")


class PyBulletBackend:
    """Builds a creature as a single PyBullet multi-body and steps it."""

    def __init__(self, gui: bool = False) -> None:
        self._client = pybullet.connect(pybullet.GUI if gui else pybullet.DIRECT)
        pybullet.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._client)
        self._creature: CreatureSpec | None = None
        self._task: TaskSpec | None = None
        self._body_id: int | None = None
        self._link_index: dict[str, int] = {}
        self._joint_link: dict[str, int] = {}
        self._root_id = ""
        self._damaged_parts: set[str] = set()
        self._t = 0.0
        self._initial_root_x = 0.0
        self._initial_target_distance = 0.0
        self._energy = 0.0
        self._damage_fired = False

    def build(self, creature: CreatureSpec, task: TaskSpec) -> None:
        self._creature = creature
        self._task = task
        pybullet.resetSimulation(physicsClientId=self._client)
        pybullet.setGravity(0, 0, -9.81, physicsClientId=self._client)
        plane_id = pybullet.loadURDF("plane.urdf", physicsClientId=self._client)
        pybullet.changeDynamics(
            plane_id, -1, lateralFriction=task.terrain.friction, physicsClientId=self._client
        )
        self._build_body(creature)
        self._t = 0.0
        self._energy = 0.0
        self._damaged_parts.clear()
        self._damage_fired = False
        base_position, _ = pybullet.getBasePositionAndOrientation(
            self._body_id, physicsClientId=self._client
        )
        self._initial_root_x = base_position[0]
        self._initial_target_distance = (
            math.dist(base_position, task.target.position) if task.target is not None else 0.0
        )

    def reset(self) -> None:
        if self._creature is None or self._task is None:
            raise RuntimeError("build() must be called before reset()")
        self.build(self._creature, self._task)

    def step(self, dt: float) -> FrameState:
        if self._creature is None or self._task is None:
            raise RuntimeError("build() must be called before step()")
        self._t += dt
        events: list[str] = []
        damage_event = self._task.damage_event
        if damage_event is not None and not self._damage_fired and self._t >= damage_event.time:
            self.damage_part(damage_event.part_id)
            self._damage_fired = True
            events.append(f"damage:{damage_event.part_id}")
        pybullet.setTimeStep(dt, physicsClientId=self._client)
        pybullet.stepSimulation(physicsClientId=self._client)
        self._accumulate_energy(dt)
        frame = self._read_frame()
        if events:
            frame = frame.model_copy(update={"events": events})
        return frame

    def _accumulate_energy(self, dt: float) -> None:
        # Proxy for actuation effort: integral of squared hinge-joint speed.
        for joint in self._creature.joints:
            if joint.type != JointType.HINGE:
                continue
            velocity = pybullet.getJointState(
                self._body_id, self._joint_link[joint.id], physicsClientId=self._client
            )[1]
            self._energy += velocity * velocity * dt

    def apply_motor_targets(self, targets: dict[str, float]) -> None:
        if self._creature is None or self._body_id is None:
            raise RuntimeError("build() must be called before apply_motor_targets()")
        joint_child = {joint.id: joint.child for joint in self._creature.joints}
        for motor in self._creature.motors:
            if motor.joint not in targets or joint_child[motor.joint] in self._damaged_parts:
                continue
            pybullet.setJointMotorControl2(
                self._body_id,
                self._joint_link[motor.joint],
                controlMode=pybullet.POSITION_CONTROL,
                targetPosition=targets[motor.joint],
                force=_MOTOR_MAX_FORCE,
                physicsClientId=self._client,
            )

    def damage_part(self, part_id: str) -> None:
        if self._creature is None or self._body_id is None:
            raise RuntimeError("build() must be called before damage_part()")
        self._damaged_parts.add(part_id)
        for joint in self._creature.joints:
            if joint.child == part_id and joint.id in self._joint_link:
                pybullet.setJointMotorControl2(
                    self._body_id,
                    self._joint_link[joint.id],
                    controlMode=pybullet.VELOCITY_CONTROL,
                    force=0.0,
                    physicsClientId=self._client,
                )

    def close(self) -> None:
        pybullet.disconnect(physicsClientId=self._client)

    def set_pose(self, frame: FrameState) -> None:
        """Kinematically pose the body from a recorded frame, without stepping physics.

        Sets the root part's pose and each hinge joint angle so links follow. Used to
        replay a saved trace for rendering (no physics is simulated).
        """
        if self._creature is None or self._body_id is None:
            raise RuntimeError("build() must be called before set_pose()")
        base = frame.parts[self._root_id]
        w, x, y, z = base.orientation
        pybullet.resetBasePositionAndOrientation(
            self._body_id, base.position, (x, y, z, w), physicsClientId=self._client
        )
        for joint in self._creature.joints:
            if joint.type == JointType.HINGE and joint.id in frame.joint_angles:
                pybullet.resetJointState(
                    self._body_id,
                    self._joint_link[joint.id],
                    frame.joint_angles[joint.id],
                    physicsClientId=self._client,
                )

    def _build_body(self, creature: CreatureSpec) -> None:
        parts_by_id = {part.id: part for part in creature.parts}
        joints_by_parent: dict[str, list] = {part.id: [] for part in creature.parts}
        joint_by_child = {}
        for joint in creature.joints:
            joints_by_parent[joint.parent].append(joint)
            joint_by_child[joint.child] = joint
        root_id = next(part.id for part in creature.parts if part.id not in joint_by_child)
        root_part = parts_by_id[root_id]
        self._root_id = root_id

        # Breadth-first traversal assigns each non-root part a 0-based link index
        # matching its position in the link arrays below.
        order: list[tuple] = []
        self._link_index = {root_id: -1}
        queue = [root_id]
        while queue:
            current_id = queue.pop(0)
            parent_link = self._link_index[current_id]
            for joint in joints_by_parent[current_id]:
                order.append((parts_by_id[joint.child], joint, parent_link))
                self._link_index[joint.child] = len(order) - 1
                queue.append(joint.child)

        base_collision_geom, base_collision_kwargs = _collision_geometry(root_part)
        base_collision = pybullet.createCollisionShape(
            base_collision_geom, physicsClientId=self._client, **base_collision_kwargs
        )
        base_visual_geom, base_visual_kwargs = _visual_geometry(root_part)
        base_visual = pybullet.createVisualShape(
            base_visual_geom,
            rgbaColor=[*(root_part.color or _DEFAULT_COLOR), 1.0],
            physicsClientId=self._client,
            **base_visual_kwargs,
        )

        link_masses: list[float] = []
        link_collision_shapes: list[int] = []
        link_visual_shapes: list[int] = []
        link_positions: list[list[float]] = []
        link_orientations: list[list[float]] = []
        link_inertial_positions: list[list[float]] = []
        link_inertial_orientations: list[list[float]] = []
        link_parent_indices: list[int] = []
        link_joint_types: list[int] = []
        link_joint_axes: list[list[float]] = []
        self._joint_link = {}

        for part, joint, parent_link in order:
            collision_geom, collision_kwargs = _collision_geometry(part)
            collision = pybullet.createCollisionShape(
                collision_geom, physicsClientId=self._client, **collision_kwargs
            )
            visual_geom, visual_kwargs = _visual_geometry(part)
            visual = pybullet.createVisualShape(
                visual_geom,
                rgbaColor=[*(part.color or _DEFAULT_COLOR), 1.0],
                physicsClientId=self._client,
                **visual_kwargs,
            )
            link_masses.append(part.mass)
            link_collision_shapes.append(collision)
            link_visual_shapes.append(visual)
            link_positions.append(list(joint.anchor))
            # Schema stores scalar-first (w, x, y, z); PyBullet wants (x, y, z, w).
            w, qx, qy, qz = joint.rest_orientation
            link_orientations.append([qx, qy, qz, w])
            link_inertial_positions.append([0.0, 0.0, 0.0])
            link_inertial_orientations.append([0.0, 0.0, 0.0, 1.0])
            # PyBullet's multi-body parent indices are 1-based; 0 means the base.
            link_parent_indices.append(parent_link + 1)
            is_hinge = joint.type == JointType.HINGE
            link_joint_types.append(pybullet.JOINT_REVOLUTE if is_hinge else pybullet.JOINT_FIXED)
            link_joint_axes.append(list(joint.axis))
            self._joint_link[joint.id] = len(link_masses) - 1

        self._body_id = pybullet.createMultiBody(
            baseMass=root_part.mass,
            baseCollisionShapeIndex=base_collision,
            baseVisualShapeIndex=base_visual,
            basePosition=[0.0, 0.0, 1.0],
            linkMasses=link_masses,
            linkCollisionShapeIndices=link_collision_shapes,
            linkVisualShapeIndices=link_visual_shapes,
            linkPositions=link_positions,
            linkOrientations=link_orientations,
            linkInertialFramePositions=link_inertial_positions,
            linkInertialFrameOrientations=link_inertial_orientations,
            linkParentIndices=link_parent_indices,
            linkJointTypes=link_joint_types,
            linkJointAxis=link_joint_axes,
            physicsClientId=self._client,
        )

        for joint in creature.joints:
            if joint.type == JointType.HINGE:
                lower, upper = joint.limit if joint.limit else _DEFAULT_HINGE_LIMIT
                pybullet.changeDynamics(
                    self._body_id,
                    self._joint_link[joint.id],
                    jointLowerLimit=lower,
                    jointUpperLimit=upper,
                    physicsClientId=self._client,
                )

    def _read_frame(self) -> FrameState:
        if self._creature is None or self._task is None or self._body_id is None:
            raise RuntimeError("build() must be called before reading a frame")

        parts: dict[str, PartPose] = {}
        base_position, base_orientation = pybullet.getBasePositionAndOrientation(
            self._body_id, physicsClientId=self._client
        )
        for part in self._creature.parts:
            link_index = self._link_index[part.id]
            if link_index == -1:
                parts[part.id] = self._pose(base_position, base_orientation)
            else:
                link_state = pybullet.getLinkState(
                    self._body_id, link_index, physicsClientId=self._client
                )
                parts[part.id] = self._pose(link_state[0], link_state[1])

        joint_angles: dict[str, float] = {}
        for joint in self._creature.joints:
            if joint.type != JointType.HINGE:
                continue
            joint_state = pybullet.getJointState(
                self._body_id, self._joint_link[joint.id], physicsClientId=self._client
            )
            joint_angles[joint.id] = joint_state[0]

        forward_distance = base_position[0] - self._initial_root_x
        target_progress = 0.0
        if self._task.target is not None:
            current_distance = math.dist(base_position, self._task.target.position)
            target_progress = self._initial_target_distance - current_distance
        # Body's local +z expressed in world coordinates; small z-component => toppled.
        body_up_z = pybullet.getMatrixFromQuaternion(base_orientation)[8]
        score = episode_score(
            self._task.reward,
            forward_distance=forward_distance,
            target_progress=target_progress,
            energy=self._energy,
            fallen=body_up_z < 0.5,
        )

        return FrameState(t=self._t, parts=parts, joint_angles=joint_angles, score=score)

    @staticmethod
    def _pose(
        position: tuple[float, float, float],
        orientation: tuple[float, float, float, float],
    ) -> PartPose:
        x, y, z, w = orientation
        return PartPose(position=tuple(position), orientation=(w, x, y, z))


def render_trace(
    creature: CreatureSpec,
    trace: EpisodeTrace,
    *,
    width: int = 640,
    height: int = 480,
    fov: float = 60.0,
    camera_distance: float = 2.0,
    camera_yaw: float = 50.0,
    camera_pitch: float = -30.0,
) -> list:
    """Render a trace to a list of RGB frames by replaying poses (no physics step).

    Builds the creature once, then for each frame re-poses the body from the recorded
    state and captures an image with PyBullet's headless software renderer. Returns a
    list of ``(height, width, 3)`` uint8 numpy arrays.
    """
    import numpy as np

    # Round up to even dimensions so the frames are valid MP4 input for libx264.
    width += width % 2
    height += height % 2

    backend = PyBulletBackend()
    frames: list = []
    try:
        backend.build(creature, TaskSpec(name="render", duration=1.0))
        projection = pybullet.computeProjectionMatrixFOV(
            fov, width / height, 0.1, 100.0, physicsClientId=backend._client
        )
        for frame in trace.frames:
            backend.set_pose(frame)
            target = frame.parts[backend._root_id].position
            view = pybullet.computeViewMatrixFromYawPitchRoll(
                target,
                camera_distance,
                camera_yaw,
                camera_pitch,
                0,
                2,
                physicsClientId=backend._client,
            )
            _, _, rgba, _, _ = pybullet.getCameraImage(
                width,
                height,
                viewMatrix=view,
                projectionMatrix=projection,
                renderer=pybullet.ER_TINY_RENDERER,
                physicsClientId=backend._client,
            )
            rgb = np.reshape(np.asarray(rgba, dtype=np.uint8), (height, width, 4))[:, :, :3]
            frames.append(rgb)
    finally:
        backend.close()
    return frames
