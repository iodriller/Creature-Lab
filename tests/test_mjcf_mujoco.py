"""Tests for MJCF export, the MuJoCo backend, and URDF import round-trips."""

import pytest

from creature_lab.export import export_mjcf, export_urdf, import_urdf
from creature_lab.scaffold import generate_humanoid, generate_quadruped, generate_worm
from creature_lab.schema import TaskSpec

# --- MJCF export --------------------------------------------------------------


@pytest.mark.parametrize(
    "creature",
    [generate_worm(), generate_quadruped(), generate_humanoid(dof=12)],
    ids=["worm", "quadruped", "humanoid"],
)
def test_mjcf_is_well_formed_xml(creature):
    import xml.etree.ElementTree as ET

    root = ET.fromstring(export_mjcf(creature))
    assert root.tag == "mujoco"
    assert root.find("worldbody") is not None
    # One actuator per motored joint.
    actuators = root.findall("actuator/position")
    assert len(actuators) == len(creature.motors)


def test_mjcf_loads_in_mujoco():
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string(export_mjcf(generate_quadruped()))
    # 5 parts + the world body; 4 motored hinges -> 4 actuators.
    assert model.nu == 4
    assert model.nbody == 6


def test_mjcf_excludes_parent_child_contacts():
    import xml.etree.ElementTree as ET

    root = ET.fromstring(export_mjcf(generate_quadruped()))
    excludes = root.findall("contact/exclude")
    assert len(excludes) == len(generate_quadruped().joints)


# --- MuJoCo backend -----------------------------------------------------------


def test_mujoco_backend_conforms_to_protocol():
    pytest.importorskip("mujoco")
    from creature_lab.backends.base import SimBackend
    from creature_lab.backends.mujoco_backend import MuJoCoBackend

    assert isinstance(MuJoCoBackend(), SimBackend)


def test_mujoco_backend_runs_an_episode():
    pytest.importorskip("mujoco")
    from creature_lab.backends.mujoco_backend import MuJoCoBackend
    from creature_lab.controllers.sinusoid import sinusoid_targets

    creature = generate_quadruped()
    task = TaskSpec.model_validate(
        {"name": "f", "duration": 1.0, "timestep": 1 / 60, "reward": {"forward_distance": 1.0}}
    )
    backend = MuJoCoBackend()
    backend.build(creature, task)
    try:
        frames = []
        for i in range(task.step_count()):
            backend.apply_motor_targets(sinusoid_targets(creature, i * task.timestep))
            frames.append(backend.step(task.timestep))
    finally:
        backend.close()

    assert len(frames) == task.step_count()
    assert set(frames[-1].parts) == {p.id for p in creature.parts}
    assert frames[-1].joint_angles  # hinge angles reported
    import math

    assert math.isfinite(frames[-1].score)


def test_mujoco_backend_reset_reruns():
    pytest.importorskip("mujoco")
    from creature_lab.backends.mujoco_backend import MuJoCoBackend

    task = TaskSpec.model_validate({"name": "t", "duration": 0.2, "timestep": 1 / 60})
    backend = MuJoCoBackend()
    backend.build(generate_quadruped(), task)
    try:
        backend.step(task.timestep)
        backend.reset()
        frame = backend.observe()
        assert frame.t == 0.0
    finally:
        backend.close()


# --- URDF import / round-trip -------------------------------------------------


@pytest.mark.parametrize(
    "creature",
    [generate_worm(), generate_quadruped(), generate_humanoid(dof=8)],
    ids=["worm", "quadruped", "humanoid"],
)
def test_urdf_round_trip_preserves_structure(creature):
    result = import_urdf(export_urdf(creature))
    assert len(result.creature.parts) == len(creature.parts)
    assert len(result.creature.joints) == len(creature.joints)
    assert {p.id for p in result.creature.parts} == {p.id for p in creature.parts}


def test_urdf_import_warns_on_mesh_geometry():
    urdf = """
    <robot name="meshbot">
      <link name="base">
        <visual><geometry><box size="0.2 0.2 0.2"/></geometry></visual>
      </link>
      <link name="arm">
        <visual><geometry><mesh filename="arm.stl"/></geometry></visual>
      </link>
      <joint name="j" type="revolute">
        <parent link="base"/><child link="arm"/>
        <axis xyz="0 1 0"/><limit lower="-1" upper="1" effort="1" velocity="1"/>
      </joint>
    </robot>
    """
    result = import_urdf(urdf)
    # The mesh link is skipped, and the joint referencing it is dropped too.
    assert {p.id for p in result.creature.parts} == {"base"}
    assert result.creature.joints == []
    assert any("mesh" in w or "skipped" in w for w in result.warnings)


def test_urdf_import_maps_revolute_to_hinge_with_limits():
    urdf = """
    <robot name="r">
      <link name="a"><visual><geometry><sphere radius="0.1"/></geometry></visual></link>
      <link name="b">
        <visual><geometry><cylinder radius="0.05" length="0.3"/></geometry></visual>
      </link>
      <joint name="hinge" type="revolute">
        <parent link="a"/><child link="b"/>
        <origin xyz="0.1 0 0" rpy="0 0 0"/>
        <axis xyz="0 0 1"/>
        <limit lower="-0.5" upper="0.5" effort="1" velocity="1"/>
      </joint>
    </robot>
    """
    creature = import_urdf(urdf).creature
    joint = creature.joints[0]
    assert joint.type.value == "hinge"
    assert joint.limit == (-0.5, 0.5)
    assert joint.anchor == (0.1, 0.0, 0.0)


def test_run_mujoco_backend_cli_saves_trace(tmp_path):
    pytest.importorskip("mujoco")
    from typer.testing import CliRunner

    from creature_lab.cli import app
    from creature_lab.schema import EpisodeTrace

    runs_dir = tmp_path / "runs"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "examples/quadruped.json",
            "--task",
            "examples/crawl_forward.json",
            "--backend",
            "mujoco",
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    run_dir = next(p for p in runs_dir.iterdir() if p.is_dir())
    trace = EpisodeTrace.model_validate_json((run_dir / "trace.json").read_text())
    assert trace.backend == "mujoco"
