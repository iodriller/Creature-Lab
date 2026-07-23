"""Export a CreatureSpec to MuJoCo's MJCF format.

MJCF is MuJoCo's native model format. Like the URDF exporter this is an outbound
bridge — ``CreatureSpec`` stays the source of truth. The kinematic tree maps to
nested ``<body>`` elements (one per part), hinge joints to ``<joint>``, motored
joints to ``<position>`` servo actuators (matching Creature Lab's position-control
model), and parent/child pairs to ``<contact><exclude>`` so adjacent links do not
self-collide. The schema's scalar-first ``(w, x, y, z)`` quaternion matches MJCF's
``quat``, so no conversion is needed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from creature_lab.schema import CreatureSpec, PartSpec, ShapeType
from creature_lab.schema.creature import JointSpec, JointType
from creature_lab.schema.task import TerrainSpec
from creature_lab.terrain import (
    DEFAULT_CELL_SIZE,
    DEFAULT_COLS,
    DEFAULT_ROWS,
    heightfield_range,
    is_flat,
)

_DEFAULT_KP = 20.0  # position-servo stiffness
# Joint damping + rotor armature keep the position servos numerically stable on
# light limbs (without them MuJoCo's solver can blow up to NaN in a few steps).
_JOINT_DAMPING = 0.5
_JOINT_ARMATURE = 0.02


def _num(value: float) -> str:
    return f"{value:.6g}"


def _vec(values: tuple[float, ...]) -> str:
    return " ".join(_num(v) for v in values)


def _geom_attrs(part: PartSpec) -> dict[str, str]:
    """MuJoCo <geom> attributes for a part (type/size, centred at the body origin)."""
    if part.shape == ShapeType.BOX:
        return {"type": "box", "size": _vec(tuple(s / 2 for s in part.size))}
    if part.shape == ShapeType.SPHERE:
        return {"type": "sphere", "size": _num(part.radius)}
    shape = "capsule" if part.shape == ShapeType.CAPSULE else "cylinder"
    # MuJoCo size for capsule/cylinder is (radius, half-length); long axis is z.
    return {"type": shape, "size": f"{_num(part.radius)} {_num(part.length / 2)}"}


def _add_body(
    parent_el: ET.Element,
    part: PartSpec,
    joint: JointSpec | None,
    parts_by_id: dict[str, PartSpec],
    children_by_parent: dict[str, list[JointSpec]],
) -> None:
    """Recursively add ``part`` as a nested <body> with its geom and joint."""
    attrs = {"name": part.id}
    if joint is not None:
        attrs["pos"] = _vec(joint.anchor)
        attrs["quat"] = _vec(joint.rest_orientation)
    else:
        attrs["pos"] = "0 0 1"  # root spawn height (matches the PyBullet backend)
    body = ET.SubElement(parent_el, "body", **attrs)

    if joint is None:
        ET.SubElement(body, "freejoint")  # root floats freely
    elif joint.type == JointType.HINGE:
        joint_attrs = {
            "name": joint.id,
            "type": "hinge",
            "axis": _vec(joint.axis),
            "damping": _num(_JOINT_DAMPING),
            "armature": _num(_JOINT_ARMATURE),
        }
        if joint.limit is not None:
            joint_attrs["range"] = _vec(joint.limit)
            joint_attrs["limited"] = "true"
        ET.SubElement(body, "joint", **joint_attrs)
    # A fixed joint is simply the absence of a <joint> (the body is welded).

    geom_attrs = {**_geom_attrs(part), "pos": "0 0 0", "mass": _num(part.mass)}
    if part.color is not None:
        geom_attrs["rgba"] = f"{_vec(part.color)} 1"
    ET.SubElement(body, "geom", **geom_attrs)

    for child_joint in children_by_parent.get(part.id, []):
        _add_body(
            body, parts_by_id[child_joint.child], child_joint, parts_by_id, children_by_parent
        )


def _add_ground(
    mujoco: ET.Element, worldbody: ET.Element, friction: float, terrain: TerrainSpec | None
) -> None:
    """Add a flat plane, or a <hfield> asset + geom sized from the shared terrain grid.

    The hfield's cell data is left at MuJoCo's zero default here; a runtime backend
    (which alone knows the ``mujoco`` Python API) fills it in via
    ``creature_lab.terrain.normalized_heightfield_data`` after loading the model.
    """
    if terrain is None or is_flat(terrain):
        ET.SubElement(
            worldbody,
            "geom",
            name="ground",
            type="plane",
            size="10 10 0.1",
            friction=f"{_num(friction)} 0.005 0.0001",
        )
        return

    lo, hi = heightfield_range(terrain)
    span = max(hi - lo, 1e-6)
    radius_x = (DEFAULT_ROWS * DEFAULT_CELL_SIZE) / 2
    radius_y = (DEFAULT_COLS * DEFAULT_CELL_SIZE) / 2
    asset = ET.SubElement(mujoco, "asset")
    ET.SubElement(
        asset,
        "hfield",
        name="terrain",
        nrow=str(DEFAULT_ROWS),
        ncol=str(DEFAULT_COLS),
        size=f"{_num(radius_x)} {_num(radius_y)} {_num(span)} 0.5",
    )
    ET.SubElement(
        worldbody,
        "geom",
        name="ground",
        type="hfield",
        hfield="terrain",
        pos=f"0 0 {_num(lo)}",
        friction=f"{_num(friction)} 0.005 0.0001",
    )


def export_mjcf(
    creature: CreatureSpec,
    *,
    friction: float = 1.0,
    timestep: float = 1.0 / 60.0,
    with_ground: bool = True,
    terrain: TerrainSpec | None = None,
) -> str:
    """Return an MJCF XML document describing ``creature`` (a loadable scene).

    ``terrain`` (non-flat) builds a <hfield> ground sized to match
    ``creature_lab.terrain.heightfield_grid``; see ``MuJoCoBackend.build`` for how the
    actual elevation data is injected at runtime.
    """
    parts_by_id = {part.id: part for part in creature.parts}
    children_by_parent: dict[str, list[JointSpec]] = {}
    child_ids = set()
    for joint in creature.joints:
        children_by_parent.setdefault(joint.parent, []).append(joint)
        child_ids.add(joint.child)
    root = next(part for part in creature.parts if part.id not in child_ids)

    mujoco = ET.Element("mujoco", model=creature.name)
    ET.SubElement(mujoco, "compiler", autolimits="true")
    # implicitfast integrator is more stable than the default for actuated joints.
    ET.SubElement(
        mujoco, "option", timestep=_num(timestep), gravity="0 0 -9.81", integrator="implicitfast"
    )

    worldbody = ET.SubElement(mujoco, "worldbody")
    if with_ground:
        _add_ground(mujoco, worldbody, friction, terrain)
    _add_body(worldbody, root, None, parts_by_id, children_by_parent)

    hinges = [joint for joint in creature.joints if joint.type == JointType.HINGE]
    if hinges:
        actuator = ET.SubElement(mujoco, "actuator")
        motor_force = {motor.joint: motor.max_force for motor in creature.motors}
        # Export a servo for every hinge. Open-loop controllers still command only
        # MotorSpec joints, while ActionSpec can intentionally address any hinge in
        # the same way on both backends.
        for joint in hinges:
            attrs = {
                "name": f"act_{joint.id}",
                "joint": joint.id,
                "kp": _num(_DEFAULT_KP),
            }
            force = motor_force.get(joint.id)
            if force is not None:
                attrs.update(forcelimited="true", forcerange=f"-{_num(force)} {_num(force)}")
            ET.SubElement(actuator, "position", **attrs)

    if creature.joints:
        contact = ET.SubElement(mujoco, "contact")
        for joint in creature.joints:
            ET.SubElement(contact, "exclude", body1=joint.parent, body2=joint.child)

    raw = ET.tostring(mujoco, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")
