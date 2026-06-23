"""Export a CreatureSpec to a URDF document.

URDF is the de-facto robot description format consumed by ROS, PyBullet, and many
viewers. This is an outbound bridge: ``CreatureSpec`` stays the source of truth and
URDF is generated from it. Capsules are approximated as cylinders (URDF has no
capsule primitive); inertias are computed from each part's shape and mass.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from xml.dom import minidom

from creature_lab.schema import CreatureSpec, PartSpec, ShapeType
from creature_lab.schema.creature import JointType

# URDF revolute joints require effort/velocity limits; these are generous defaults.
_DEFAULT_EFFORT = 20.0
_DEFAULT_VELOCITY = 10.0


def _quat_to_rpy(quat: tuple[float, ...]) -> tuple[float, float, float]:
    """Convert a scalar-first (w, x, y, z) quaternion to URDF roll-pitch-yaw."""
    w, x, y, z = quat
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    sin_pitch = max(-1.0, min(1.0, 2 * (w * y - z * x)))
    pitch = math.asin(sin_pitch)
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


def _inertia(part: PartSpec) -> tuple[float, float, float]:
    """Principal moments (Ixx, Iyy, Izz) about the part centroid."""
    m = part.mass
    if part.shape == ShapeType.BOX:
        sx, sy, sz = part.size
        return (
            m / 12 * (sy * sy + sz * sz),
            m / 12 * (sx * sx + sz * sz),
            m / 12 * (sx * sx + sy * sy),
        )
    if part.shape == ShapeType.SPHERE:
        i = 2 / 5 * m * part.radius * part.radius
        return i, i, i
    # Capsule/cylinder: long axis is Z (matches PyBullet's primitive orientation).
    r, h = part.radius, part.length
    radial = m / 12 * (3 * r * r + h * h)
    return radial, radial, 0.5 * m * r * r


def _geometry_element(part: PartSpec) -> ET.Element:
    geometry = ET.Element("geometry")
    if part.shape == ShapeType.BOX:
        ET.SubElement(geometry, "box", size=_vec(part.size))
    elif part.shape == ShapeType.SPHERE:
        ET.SubElement(geometry, "sphere", radius=_num(part.radius))
    else:  # capsule -> cylinder approximation, cylinder -> cylinder
        ET.SubElement(geometry, "cylinder", radius=_num(part.radius), length=_num(part.length))
    return geometry


def _num(value: float) -> str:
    return f"{value:.6g}"


def _vec(values: tuple[float, ...]) -> str:
    return " ".join(_num(v) for v in values)


def _link_element(part: PartSpec) -> ET.Element:
    link = ET.Element("link", name=part.id)

    visual = ET.SubElement(link, "visual")
    visual.append(_geometry_element(part))
    if part.color is not None:
        material = ET.SubElement(visual, "material", name=f"{part.id}_color")
        ET.SubElement(material, "color", rgba=f"{_vec(part.color)} 1")

    collision = ET.SubElement(link, "collision")
    collision.append(_geometry_element(part))

    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "mass", value=_num(part.mass))
    ixx, iyy, izz = _inertia(part)
    ET.SubElement(
        inertial,
        "inertia",
        ixx=_num(ixx),
        ixy="0",
        ixz="0",
        iyy=_num(iyy),
        iyz="0",
        izz=_num(izz),
    )
    return link


def export_urdf(creature: CreatureSpec, *, robot_name: str | None = None) -> str:
    """Return a URDF XML document describing ``creature``."""
    robot = ET.Element("robot", name=robot_name or creature.name)
    for part in creature.parts:
        robot.append(_link_element(part))

    for joint in creature.joints:
        is_hinge = joint.type == JointType.HINGE
        element = ET.SubElement(
            robot,
            "joint",
            name=joint.id,
            type="revolute" if is_hinge else "fixed",
        )
        ET.SubElement(element, "parent", link=joint.parent)
        ET.SubElement(element, "child", link=joint.child)
        roll, pitch, yaw = _quat_to_rpy(joint.rest_orientation)
        ET.SubElement(
            element,
            "origin",
            xyz=_vec(joint.anchor),
            rpy=f"{_num(roll)} {_num(pitch)} {_num(yaw)}",
        )
        if is_hinge:
            ET.SubElement(element, "axis", xyz=_vec(joint.axis))
            lower, upper = joint.limit if joint.limit else (-math.pi, math.pi)
            ET.SubElement(
                element,
                "limit",
                lower=_num(lower),
                upper=_num(upper),
                effort=_num(_DEFAULT_EFFORT),
                velocity=_num(_DEFAULT_VELOCITY),
            )

    # Transmission blocks for each motored joint (ros_control convention).
    motored = {motor.joint for motor in creature.motors}
    for joint in creature.joints:
        if joint.id not in motored or joint.type != JointType.HINGE:
            continue
        transmission = ET.SubElement(robot, "transmission", name=f"trans_{joint.id}")
        ET.SubElement(transmission, "type").text = "transmission_interface/SimpleTransmission"
        trans_joint = ET.SubElement(transmission, "joint", name=joint.id)
        ET.SubElement(
            trans_joint, "hardwareInterface"
        ).text = "hardware_interface/PositionJointInterface"
        actuator = ET.SubElement(transmission, "actuator", name=f"motor_{joint.id}")
        ET.SubElement(actuator, "mechanicalReduction").text = "1"

    raw = ET.tostring(robot, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")
