"""Tests for the URDF exporter."""

import xml.etree.ElementTree as ET

import pytest

from creature_lab.export import export_urdf
from creature_lab.scaffold import generate_humanoid, generate_quadruped, generate_worm


@pytest.mark.parametrize(
    "creature",
    [generate_worm(), generate_quadruped(), generate_humanoid(dof=12)],
    ids=["worm", "quadruped", "humanoid"],
)
def test_urdf_is_well_formed_and_complete(creature):
    root = ET.fromstring(export_urdf(creature))  # raises if not well-formed XML
    assert root.tag == "robot"
    assert root.get("name") == creature.name
    assert len(root.findall("link")) == len(creature.parts)
    assert len(root.findall("joint")) == len(creature.joints)


def test_urdf_joint_types_and_limits():
    root = ET.fromstring(export_urdf(generate_quadruped()))
    for joint in root.findall("joint"):
        assert joint.get("type") in ("revolute", "fixed")
        assert joint.find("parent") is not None
        assert joint.find("child") is not None
        if joint.get("type") == "revolute":
            limit = joint.find("limit")
            assert limit is not None
            assert float(limit.get("lower")) < float(limit.get("upper"))


def test_urdf_links_have_inertia_and_geometry():
    root = ET.fromstring(export_urdf(generate_worm()))
    for link in root.findall("link"):
        assert link.find("visual/geometry") is not None
        assert link.find("collision/geometry") is not None
        inertia = link.find("inertial/inertia")
        assert inertia is not None
        assert float(inertia.get("ixx")) > 0


def test_urdf_loads_in_pybullet():
    pybullet = pytest.importorskip("pybullet")
    import tempfile

    urdf = export_urdf(generate_quadruped())
    client = pybullet.connect(pybullet.DIRECT)
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".urdf", delete=False) as handle:
            handle.write(urdf)
            path = handle.name
        body = pybullet.loadURDF(path)
        assert pybullet.getNumJoints(body) == 4
    finally:
        pybullet.disconnect(client)


def test_urdf_has_transmission_for_motored_joints():
    creature = generate_quadruped()
    root = ET.fromstring(export_urdf(creature))
    transmissions = root.findall("transmission")
    assert len(transmissions) == len(creature.motors)
    # MJCF export now lives in test_mjcf_mujoco.py (Phase 8).
