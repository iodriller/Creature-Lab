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
    # One actuator per hinge: policies may intentionally control a hinge even when
    # the legacy open-loop gait has no MotorSpec for it.
    actuators = root.findall("actuator/position")
    assert len(actuators) == len([joint for joint in creature.joints if joint.type == "hinge"])


def test_mjcf_loads_in_mujoco():
    mujoco = pytest.importorskip("mujoco")
    model = mujoco.MjModel.from_xml_string(export_mjcf(generate_quadruped()))
    # 5 parts + the world body; 4 motored hinges -> 4 actuators.
    assert model.nu == 4
    assert model.nbody == 6


def test_mjcf_with_terrain_builds_a_loadable_hfield():
    mujoco = pytest.importorskip("mujoco")
    from creature_lab.schema.task import TerrainSpec

    terrain = TerrainSpec(type="steps", step_height=0.05, step_length=0.4)
    xml = export_mjcf(generate_quadruped(), terrain=terrain)

    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml)
    assert root.find("asset/hfield") is not None
    ground = next(g for g in root.findall("worldbody/geom") if g.get("name") == "ground")
    assert ground.get("type") == "hfield"

    model = mujoco.MjModel.from_xml_string(xml)
    assert model.nhfield == 1


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


def test_target_seek_runs_deterministically_on_mujoco():
    """MuJoCo's default MJCF actuator/friction export makes generate_quadruped() a
    much weaker walker than under PyBullet for the same open-loop gait - a
    pre-existing, documented backend characteristic (see KNOWN_ISSUES.md's
    "exact physics is backend-dependent"), not something specific to this
    controller. A full physical steering scenario like test_controllers.py's isn't a
    reliable signal here since the body barely translates at all in 3s regardless of
    controller. This instead confirms the controller runs cleanly and
    deterministically against MuJoCo-sourced frames (real cross-backend coverage for
    the steering *math* itself is in test_target_seek_steering_asymmetry_from_a_
    synthetic_frame below, which is backend-independent by construction)."""
    pytest.importorskip("mujoco")
    import math

    from creature_lab.backends.mujoco_backend import MuJoCoBackend
    from creature_lab.controllers.target_seek import TargetSeekController

    creature = generate_quadruped()
    task = TaskSpec.model_validate(
        {
            "name": "reach",
            "duration": 1.0,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "target": {"position": [0.0, 1.5, 0.15], "radius": 0.15},
            "reward": {"target_distance": 1.0},
        }
    )

    def run() -> list:
        controller = TargetSeekController(creature, task)
        backend = MuJoCoBackend()
        backend.build(creature, task)
        frames = []
        prev = None
        try:
            for i in range(task.step_count()):
                backend.apply_motor_targets(controller(i * task.timestep, prev))
                prev = backend.step(task.timestep)
                frames.append(prev)
        finally:
            backend.close()
        return frames

    frames_a = run()
    frames_b = run()

    assert [f.parts["torso"].position for f in frames_a] == [
        f.parts["torso"].position for f in frames_b
    ]
    assert all(math.isfinite(f.score) for f in frames_a)


def test_target_seek_steering_asymmetry_from_a_synthetic_frame():
    """The controller only ever reads a FrameState (root position + orientation) -
    it has no idea which backend produced it. Feed it a synthetic frame directly
    (identity orientation, facing +x) with the target off to one side, and confirm
    it computes the correct differential steering regardless of backend: this is
    the part of "works on both backends" that's actually backend-independent."""
    from creature_lab.controllers.cpg import CPGController
    from creature_lab.controllers.target_seek import TargetSeekController
    from creature_lab.schema import FrameState

    creature = generate_quadruped()
    task = TaskSpec.model_validate(
        {
            "name": "reach",
            "duration": 1.0,
            "target": {"position": [0.0, 1.5, 0.15], "radius": 0.15},  # target to the left
        }
    )
    frame = FrameState.model_validate(
        {
            "t": 0.0,
            "parts": {"torso": {"position": (0.0, 0.0, 0.1), "orientation": (1, 0, 0, 0)}},
            "score": 0.0,
        }
    )
    # Two fresh, independently-seeded instances so this doesn't depend on shared
    # mutable state or call ordering between them.
    targets = TargetSeekController(creature, task)(0.0, frame)
    base = CPGController(creature)(0.0, frame)  # the un-steered gait for the same instant

    left_joints = [j for j in targets if j.endswith("l")]
    right_joints = [j for j in targets if j.endswith("r")]
    assert left_joints and right_joints
    # Target is 90 degrees left: left-side output should be damped relative to the
    # base gait, right-side amplified - a hard turn toward the target.
    for j in left_joints:
        assert abs(targets[j]) < abs(base[j]) + 1e-9
    for j in right_joints:
        assert abs(targets[j]) > abs(base[j]) - 1e-9


@pytest.mark.parametrize(
    "terrain",
    [
        {"type": "slope", "slope_angle": 0.15},
        {"type": "steps", "step_height": 0.05, "step_length": 0.4},
        {"type": "gaps", "gap_width": 0.2, "gap_period": 1.0},
        {"type": "rough", "roughness": 0.03, "seed": 1},
    ],
)
def test_mujoco_backend_non_flat_terrain_produces_finite_frames(terrain):
    pytest.importorskip("mujoco")
    import math

    from creature_lab.backends.mujoco_backend import MuJoCoBackend
    from creature_lab.controllers.sinusoid import sinusoid_targets

    creature = generate_quadruped()
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 0.5, "timestep": 1 / 60, "terrain": terrain}
    )
    backend = MuJoCoBackend()
    backend.build(creature, task)
    try:
        for i in range(task.step_count()):
            backend.apply_motor_targets(sinusoid_targets(creature, i * task.timestep))
            frame = backend.step(task.timestep)
    finally:
        backend.close()

    for pose in frame.parts.values():
        assert all(math.isfinite(v) for v in pose.position)


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
