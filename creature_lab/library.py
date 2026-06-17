"""Built-in creatures and tasks.

These let ``creature-lab demo`` work from an installed package without needing the
repository's ``examples/`` directory on disk. The default creature mirrors
``examples/tripod.json``.
"""

from __future__ import annotations

from creature_lab.schema import CreatureSpec, TaskSpec

_TRIPOD = {
    "name": "tripod",
    "parts": [
        {
            "id": "torso",
            "shape": "box",
            "size": [0.45, 0.22, 0.12],
            "mass": 1.0,
            "color": [0.2, 0.5, 0.9],
        },
        {"id": "leg_a", "shape": "capsule", "length": 0.35, "radius": 0.04, "mass": 0.2},
        {"id": "leg_b", "shape": "capsule", "length": 0.35, "radius": 0.04, "mass": 0.2},
        {"id": "leg_c", "shape": "capsule", "length": 0.35, "radius": 0.04, "mass": 0.2},
    ],
    "joints": [
        {
            "id": "hip_a",
            "parent": "torso",
            "child": "leg_a",
            "type": "hinge",
            "anchor": [-0.18, 0.0, -0.2],
            "axis": [0, 1, 0],
            "limit": [-0.8, 0.8],
        },
        {
            "id": "hip_b",
            "parent": "torso",
            "child": "leg_b",
            "type": "hinge",
            "anchor": [0.18, 0.09, -0.2],
            "axis": [0, 1, 0],
            "limit": [-0.8, 0.8],
        },
        {
            "id": "hip_c",
            "parent": "torso",
            "child": "leg_c",
            "type": "hinge",
            "anchor": [0.18, -0.09, -0.2],
            "axis": [0, 1, 0],
            "limit": [-0.8, 0.8],
        },
    ],
    "motors": [
        {"joint": "hip_a", "type": "sinusoid", "amplitude": 0.6, "frequency": 2.0, "phase": 0.0},
        {"joint": "hip_b", "type": "sinusoid", "amplitude": 0.6, "frequency": 2.0, "phase": 2.09},
        {"joint": "hip_c", "type": "sinusoid", "amplitude": 0.6, "frequency": 2.0, "phase": 4.18},
    ],
}

_CRAWL_FORWARD = {
    "name": "crawl_forward",
    "duration": 3.0,
    "timestep": 1.0 / 60.0,
    "terrain": {"type": "plane", "friction": 0.8},
    "reward": {"forward_distance": 1.0},
}


def default_creature() -> CreatureSpec:
    """The built-in tripod creature used by ``creature-lab demo``."""
    return CreatureSpec.model_validate(_TRIPOD)


def default_task() -> TaskSpec:
    """The built-in crawl-forward task used by ``creature-lab demo``."""
    return TaskSpec.model_validate(_CRAWL_FORWARD)
