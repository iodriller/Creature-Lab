"""Best-effort URDF -> CreatureSpec import.

A bridge *inbound* from URDF, deliberately limited: it parses links with simple
primitive geometry (box/sphere/cylinder) and revolute/continuous/fixed joints, and
skips meshes, materials, sensors, and anything else — collecting a warning per
skipped element. The goal is to ingest simple robots (ant, hopper), not to be a
complete URDF parser. Capsules are not a URDF primitive, so cylinders import as
``cylinder`` parts.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from creature_lab.schema import CreatureSpec


@dataclass
class ImportResult:
    creature: CreatureSpec
    warnings: list[str] = field(default_factory=list)


def _rpy_to_quat(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """URDF fixed-axis roll-pitch-yaw -> scalar-first (w, x, y, z) quaternion."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    )


def _floats(text: str | None, count: int, default: float = 0.0) -> list[float]:
    if not text:
        return [default] * count
    values = [float(v) for v in text.split()]
    return (values + [default] * count)[:count]


def _parse_link(link: ET.Element, warnings: list[str]) -> dict | None:
    name = link.get("name", "")
    geometry = link.find("visual/geometry")
    if geometry is None:
        geometry = link.find("collision/geometry")
    if geometry is None:
        warnings.append(f"link {name!r}: no primitive geometry, skipped")
        return None

    mass_el = link.find("inertial/mass")
    mass = float(mass_el.get("value")) if mass_el is not None else 1.0
    mass = max(mass, 1e-3)

    if (box := geometry.find("box")) is not None:
        size = _floats(box.get("size"), 3, 0.1)
        return {"id": name, "shape": "box", "size": size, "mass": mass}
    if (sphere := geometry.find("sphere")) is not None:
        return {
            "id": name,
            "shape": "sphere",
            "radius": float(sphere.get("radius", "0.1")),
            "mass": mass,
        }
    if (cylinder := geometry.find("cylinder")) is not None:
        return {
            "id": name,
            "shape": "cylinder",
            "radius": float(cylinder.get("radius", "0.05")),
            "length": float(cylinder.get("length", "0.2")),
            "mass": mass,
        }
    warnings.append(f"link {name!r}: unsupported geometry (mesh?), skipped")
    return None


def _parse_joint(joint: ET.Element, link_ids: set[str], warnings: list[str]) -> dict | None:
    name = joint.get("name", "")
    urdf_type = joint.get("type", "fixed")
    parent_el, child_el = joint.find("parent"), joint.find("child")
    if parent_el is None or child_el is None:
        warnings.append(f"joint {name!r}: missing parent/child, skipped")
        return None
    parent, child = parent_el.get("link", ""), child_el.get("link", "")
    if parent not in link_ids or child not in link_ids:
        warnings.append(f"joint {name!r}: references a skipped link, skipped")
        return None

    origin = joint.find("origin")
    xyz = _floats(origin.get("xyz") if origin is not None else None, 3)
    rpy = _floats(origin.get("rpy") if origin is not None else None, 3)
    spec = {
        "id": name,
        "parent": parent,
        "child": child,
        "anchor": xyz,
        "rest_orientation": list(_rpy_to_quat(*rpy)),
    }
    if urdf_type in ("revolute", "continuous"):
        axis_el = joint.find("axis")
        spec["type"] = "hinge"
        spec["axis"] = _floats(axis_el.get("xyz") if axis_el is not None else "1 0 0", 3)
        limit_el = joint.find("limit")
        if limit_el is not None and limit_el.get("lower") and limit_el.get("upper"):
            spec["limit"] = [float(limit_el.get("lower")), float(limit_el.get("upper"))]
    else:
        if urdf_type != "fixed":
            warnings.append(f"joint {name!r}: type {urdf_type!r} imported as fixed")
        spec["type"] = "fixed"
    return spec


def import_urdf(urdf_text: str) -> ImportResult:
    """Parse URDF text into a (best-effort) CreatureSpec plus skip warnings."""
    warnings: list[str] = []
    robot = ET.fromstring(urdf_text)

    parts = [p for link in robot.findall("link") if (p := _parse_link(link, warnings))]
    link_ids = {part["id"] for part in parts}
    joints = [
        j for joint in robot.findall("joint") if (j := _parse_joint(joint, link_ids, warnings))
    ]

    creature = CreatureSpec.model_validate(
        {"name": robot.get("name", "imported"), "parts": parts, "joints": joints}
    )
    return ImportResult(creature=creature, warnings=warnings)
