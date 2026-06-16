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
    steps = int(task.duration / task.timestep)
    frames = []
    for step_index in range(steps):
        t = step_index * task.timestep
        backend.apply_motor_targets(sinusoid_targets(creature, t))
        frames.append(backend.step(task.timestep))
    return frames


def test_short_episode_emits_finite_frames(backend):
    creature = CreatureSpec.model_validate(TRIPOD)
    task = TaskSpec.model_validate({"name": "t", "duration": 0.5, "timestep": 1 / 60})

    frames = _run_episode(backend, creature, task)

    assert len(frames) == int(task.duration / task.timestep)
    assert all(math.isfinite(frame.score) for frame in frames)
    assert set(frames[0].parts) == {part.id for part in creature.parts}
    assert "hip_a" in frames[0].joint_angles
    assert "hip_b" not in frames[0].joint_angles  # fixed joints have no angle


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
