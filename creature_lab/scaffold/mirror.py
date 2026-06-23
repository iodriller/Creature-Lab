"""Mirror a creature's limbs across the sagittal (XZ) plane.

Takes the limbs on one side of the body (the side whose root joint anchor has the
matching Y sign) and adds mirrored copies on the other side: anchors get their Y
negated, hinge axes and rest orientations are reflected, and ids get a suffix so
they stay unique. Useful for turning a half-built creature symmetric.
"""

from __future__ import annotations

from collections import defaultdict

from creature_lab.schema import CreatureSpec

_TOL = 1e-9


def _reflect_quaternion(q: tuple[float, ...]) -> list[float]:
    """Reflect a scalar-first (w, x, y, z) rotation across the Y=0 plane."""
    w, x, y, z = q
    return [w, -x, y, -z]


def mirror_limb(spec: CreatureSpec, side: str = "left", *, suffix: str = "_m") -> CreatureSpec:
    """Return a copy of ``spec`` with the ``side`` limbs mirrored to the other side.

    Args:
        spec: Source creature.
        side: Which side to mirror *from* — ``"left"`` (Y > 0) or ``"right"`` (Y < 0).
        suffix: Appended to mirrored part/joint ids to keep them unique.
    """
    if side not in ("left", "right"):
        raise ValueError("side must be 'left' or 'right'")
    sign = 1.0 if side == "left" else -1.0

    child_to_joint = {joint.child: joint for joint in spec.joints}
    root = next(part.id for part in spec.parts if part.id not in child_to_joint)
    parts_by_id = {part.id: part for part in spec.parts}
    children: dict[str, list] = defaultdict(list)
    for joint in spec.joints:
        children[joint.parent].append(joint)
    motors_by_joint = {motor.joint: motor for motor in spec.motors}

    existing_ids = {part.id for part in spec.parts} | {joint.id for joint in spec.joints}
    new_parts: list[dict] = []
    new_joints: list[dict] = []
    new_motors: list[dict] = []

    def mirror_subtree(joint) -> None:
        """Copy a limb-root joint's subtree, mirrored across Y."""
        stack = [joint]
        while stack:
            j = stack.pop()
            new_part_id = j.child + suffix
            new_joint_id = j.id + suffix
            if new_part_id in existing_ids or new_joint_id in existing_ids:
                raise ValueError(f"mirrored id collides with an existing id: {new_part_id!r}")
            part = parts_by_id[j.child]
            new_parts.append(part.model_dump(exclude_none=True) | {"id": new_part_id})
            ax, ay, az = j.axis
            new_joints.append(
                j.model_dump(exclude_none=True)
                | {
                    "id": new_joint_id,
                    # The limb-root joint keeps the (unsuffixed) root as parent.
                    "parent": root if j.parent == root else j.parent + suffix,
                    "child": new_part_id,
                    "anchor": [j.anchor[0], -j.anchor[1], j.anchor[2]],
                    "axis": [ax, -ay, az],
                    "rest_orientation": _reflect_quaternion(j.rest_orientation),
                }
            )
            motor = motors_by_joint.get(j.id)
            if motor is not None:
                new_motors.append(motor.model_dump(exclude_none=True) | {"joint": new_joint_id})
            stack.extend(children.get(j.child, []))

    mirrored_any = False
    for joint in children.get(root, []):
        if sign * joint.anchor[1] > _TOL:  # limb root on the source side
            mirror_subtree(joint)
            mirrored_any = True
    if not mirrored_any:
        raise ValueError(f"no limbs found on the {side!r} side to mirror")

    data = spec.model_dump(exclude_none=True)
    data["parts"] = data["parts"] + new_parts
    data["joints"] = data["joints"] + new_joints
    data["motors"] = data["motors"] + new_motors
    return CreatureSpec.model_validate(data)
