"""Smoke tests for the PyBullet backend.

These exercise the backend only through the SimBackend protocol and avoid
asserting exact physics trajectories, per CLAUDE.md.
"""

import math

import pytest

pytest.importorskip("pybullet")

from creature_lab.controllers.sinusoid import sinusoid_targets  # noqa: E402
from creature_lab.schema import CreatureSpec, TaskSpec  # noqa: E402

TRIPOD = {
    "name": "tripod",
    "parts": [
        {"id": "torso", "shape": "box", "size": [0.45, 0.22, 0.12], "mass": 1.0},
        {"id": "leg_a", "shape": "capsule", "length": 0.35, "radius": 0.04, "mass": 0.2},
        {"id": "leg_b", "shape": "capsule", "length": 0.35, "radius": 0.04, "mass": 0.2},
    ],
    "joints": [
        {
            "id": "hip_a",
            "parent": "torso",
            "child": "leg_a",
            "type": "hinge",
            "axis": [0, 1, 0],
            "limit": [-0.8, 0.8],
        },
        {
            "id": "hip_b",
            "parent": "torso",
            "child": "leg_b",
            "type": "fixed",
        },
    ],
    "motors": [{"joint": "hip_a", "amplitude": 0.6, "frequency": 2.0}],
}


@pytest.fixture
def backend():
    from creature_lab.backends.pybullet_backend import PyBulletBackend

    instance = PyBulletBackend()
    yield instance
    instance.close()


def _run_episode(backend, creature, task) -> list:
    backend.build(creature, task)
    frames = []
    for step_index in range(task.step_count()):
        t = step_index * task.timestep
        backend.apply_motor_targets(sinusoid_targets(creature, t))
        frames.append(backend.step(task.timestep))
    return frames


def test_short_episode_emits_finite_frames(backend):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate({"name": "t", "duration": 0.5, "timestep": 1 / 60})

    frames = _run_episode(backend, creature, task)

    assert len(frames) == task.step_count()
    assert all(math.isfinite(frame.score) for frame in frames)
    assert set(frames[0].parts) == {part.id for part in creature.parts}
    assert "hip_a" in frames[0].joint_angles
    assert "hip_b" not in frames[0].joint_angles  # fixed joints have no angle


def test_ground_contacts_are_reported(backend):
    from creature_lab.library import default_creature

    creature = default_creature()  # quadruped standing on four legs
    task = TaskSpec.model_validate({"name": "t", "duration": 2.0, "timestep": 1 / 60})

    frames = _run_episode(backend, creature, task)

    part_ids = {part.id for part in creature.parts}
    # Once it settles, at least one frame reports foot/ground contacts.
    contact_frames = [frame for frame in frames if frame.contacts]
    assert contact_frames, "expected the creature to touch the ground"
    for contact in contact_frames[-1].contacts:
        assert contact.part_id in part_ids
        assert contact.force >= 0.0


def test_frames_are_time_ordered(backend):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate({"name": "t", "duration": 0.2, "timestep": 1 / 60})

    frames = _run_episode(backend, creature, task)

    times = [frame.t for frame in frames]
    assert times == sorted(times)


def test_damage_event_fires_once(backend):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate(
        {
            "name": "t",
            "duration": 0.5,
            "timestep": 1 / 60,
            "damage_event": {"time": 0.1, "part_id": "leg_a"},
        }
    )

    frames = _run_episode(backend, creature, task)

    damage_frames = [frame for frame in frames if frame.events]
    assert len(damage_frames) == 1
    assert damage_frames[0].events == ["damage:leg_a"]


def test_reset_reruns_from_the_start(backend):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate({"name": "t", "duration": 0.2, "timestep": 1 / 60})

    first = _run_episode(backend, creature, task)
    backend.reset()
    second_first_frame = backend.step(task.timestep)

    # After reset the clock restarts near zero rather than continuing from the
    # end of the previous episode.
    assert second_first_frame.t < first[-1].t


@pytest.mark.parametrize(
    "terrain",
    [
        {"type": "slope", "slope_angle": 0.15},
        {"type": "steps", "step_height": 0.05, "step_length": 0.4},
        {"type": "gaps", "gap_width": 0.2, "gap_period": 1.0},
        {"type": "rough", "roughness": 0.03, "seed": 1},
    ],
)
def test_non_flat_terrain_produces_finite_frames(backend, terrain):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate(
        {"name": "t", "duration": 0.5, "timestep": 1 / 60, "terrain": terrain}
    )

    frames = _run_episode(backend, creature, task)

    for frame in frames:
        for pose in frame.parts.values():
            assert all(math.isfinite(v) for v in pose.position)


def test_gaps_terrain_keeps_a_solid_start_platform(backend):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate(
        {
            "name": "t",
            "duration": 1.0,
            "timestep": 1 / 60,
            "terrain": {"type": "gaps", "gap_width": 0.2, "gap_period": 1.0},
        }
    )

    frames = _run_episode(backend, creature, task)

    # A creature spawning at the origin must land on the safe platform, not fall forever.
    final_z = min(pose.position[2] for pose in frames[-1].parts.values())
    assert final_z > -1.0


def test_backend_satisfies_protocol():
    from creature_lab.backends.base import SimBackend
    from creature_lab.backends.pybullet_backend import PyBulletBackend

    instance = PyBulletBackend()
    try:
        assert isinstance(instance, SimBackend)
    finally:
        instance.close()


def test_rest_orientation_orients_child_link(backend):
    # 90 degrees about X, scalar-first (w, x, y, z).
    half = math.sqrt(0.5)
    creature = CreatureSpec.model_validate(
        {
            "name": "bent",
            "parts": [
                {"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0},
                {"id": "arm", "shape": "capsule", "length": 0.3, "radius": 0.04, "mass": 0.2},
            ],
            "joints": [
                {
                    "id": "j",
                    "parent": "torso",
                    "child": "arm",
                    "type": "fixed",
                    "rest_orientation": [half, half, 0.0, 0.0],
                }
            ],
        }
    )
    task = TaskSpec.model_validate({"name": "t", "duration": 0.2, "timestep": 1 / 60})

    backend.build(creature, task)
    frame = backend._read_frame()  # initial pose, before stepping

    orientation = frame.parts["arm"].orientation
    # A quaternion and its negation represent the same rotation; canonicalize on w >= 0.
    if orientation[0] < 0:
        orientation = tuple(-component for component in orientation)
    assert orientation == pytest.approx((half, half, 0.0, 0.0), abs=1e-4)
