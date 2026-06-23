"""Built-in creatures and tasks.

These let ``creature-lab demo`` work from an installed package without needing the
repository's ``examples/`` directory on disk. ``creature-lab demo --creature NAME``
picks any of the built-ins below; with no name it uses the quadruped, which walks
visibly forward and stays upright.
"""

from __future__ import annotations

from creature_lab.schema import CreatureSpec, TaskSpec

# A four-legged walker. Legs are angled backward (``rest_orientation``) so the
# fore/aft swing acts like oars and produces net forward thrust; the diagonal
# gait (FL+RR vs FR+RL out of phase) keeps it upright and tracking straight.
_QUADRUPED = {
    "name": "quadruped",
    "parts": [
        {
            "id": "torso",
            "shape": "box",
            "size": [0.4, 0.25, 0.08],
            "mass": 1.0,
            "color": [0.2, 0.55, 0.9],
        },
        {
            "id": "leg_fl",
            "shape": "capsule",
            "length": 0.22,
            "radius": 0.03,
            "mass": 0.15,
            "color": [0.3, 0.7, 0.95],
        },
        {
            "id": "leg_fr",
            "shape": "capsule",
            "length": 0.22,
            "radius": 0.03,
            "mass": 0.15,
            "color": [0.3, 0.7, 0.95],
        },
        {
            "id": "leg_rl",
            "shape": "capsule",
            "length": 0.22,
            "radius": 0.03,
            "mass": 0.15,
            "color": [0.25, 0.6, 0.9],
        },
        {
            "id": "leg_rr",
            "shape": "capsule",
            "length": 0.22,
            "radius": 0.03,
            "mass": 0.15,
            "color": [0.25, 0.6, 0.9],
        },
    ],
    "joints": [
        {
            "id": "hip_fl",
            "parent": "torso",
            "child": "leg_fl",
            "type": "hinge",
            "anchor": [0.15, 0.16, -0.04],
            "axis": [0, 1, 0],
            "limit": [-1.2, 1.2],
            "rest_orientation": [0.9537, 0, -0.3007, 0],
        },
        {
            "id": "hip_fr",
            "parent": "torso",
            "child": "leg_fr",
            "type": "hinge",
            "anchor": [0.15, -0.16, -0.04],
            "axis": [0, 1, 0],
            "limit": [-1.2, 1.2],
            "rest_orientation": [0.9537, 0, -0.3007, 0],
        },
        {
            "id": "hip_rl",
            "parent": "torso",
            "child": "leg_rl",
            "type": "hinge",
            "anchor": [-0.15, 0.16, -0.04],
            "axis": [0, 1, 0],
            "limit": [-1.2, 1.2],
            "rest_orientation": [0.9537, 0, -0.3007, 0],
        },
        {
            "id": "hip_rr",
            "parent": "torso",
            "child": "leg_rr",
            "type": "hinge",
            "anchor": [-0.15, -0.16, -0.04],
            "axis": [0, 1, 0],
            "limit": [-1.2, 1.2],
            "rest_orientation": [0.9537, 0, -0.3007, 0],
        },
    ],
    "motors": [
        {"joint": "hip_fl", "type": "sinusoid", "amplitude": 0.7, "frequency": 2.0, "phase": 0.0},
        {
            "joint": "hip_fr",
            "type": "sinusoid",
            "amplitude": 0.7,
            "frequency": 2.0,
            "phase": 3.1416,
        },
        {
            "joint": "hip_rl",
            "type": "sinusoid",
            "amplitude": 0.7,
            "frequency": 2.0,
            "phase": 3.1416,
        },
        {"joint": "hip_rr", "type": "sinusoid", "amplitude": 0.7, "frequency": 2.0, "phase": 0.0},
    ],
}

# A five-segment worm. Each capsule is laid flat (``rest_orientation`` rotates it
# 90 deg about Y) and a traveling sine wave down the chain drives it forward.
_WORM = {
    "name": "worm",
    "parts": [
        {
            "id": "seg0",
            "shape": "capsule",
            "length": 0.18,
            "radius": 0.05,
            "mass": 0.4,
            "color": [0.9, 0.45, 0.2],
        },
        {
            "id": "seg1",
            "shape": "capsule",
            "length": 0.18,
            "radius": 0.05,
            "mass": 0.4,
            "color": [0.93, 0.55, 0.22],
        },
        {
            "id": "seg2",
            "shape": "capsule",
            "length": 0.18,
            "radius": 0.05,
            "mass": 0.4,
            "color": [0.95, 0.65, 0.25],
        },
        {
            "id": "seg3",
            "shape": "capsule",
            "length": 0.18,
            "radius": 0.05,
            "mass": 0.4,
            "color": [0.97, 0.72, 0.3],
        },
        {
            "id": "seg4",
            "shape": "capsule",
            "length": 0.18,
            "radius": 0.05,
            "mass": 0.4,
            "color": [0.98, 0.8, 0.35],
        },
    ],
    "joints": [
        {
            "id": "j1",
            "parent": "seg0",
            "child": "seg1",
            "type": "hinge",
            "anchor": [-0.2, 0, 0],
            "axis": [0, 1, 0],
            "limit": [-1.0, 1.0],
            "rest_orientation": [0.7071, 0, 0.7071, 0],
        },
        {
            "id": "j2",
            "parent": "seg1",
            "child": "seg2",
            "type": "hinge",
            "anchor": [-0.2, 0, 0],
            "axis": [0, 1, 0],
            "limit": [-1.0, 1.0],
            "rest_orientation": [0.7071, 0, 0.7071, 0],
        },
        {
            "id": "j3",
            "parent": "seg2",
            "child": "seg3",
            "type": "hinge",
            "anchor": [-0.2, 0, 0],
            "axis": [0, 1, 0],
            "limit": [-1.0, 1.0],
            "rest_orientation": [0.7071, 0, 0.7071, 0],
        },
        {
            "id": "j4",
            "parent": "seg3",
            "child": "seg4",
            "type": "hinge",
            "anchor": [-0.2, 0, 0],
            "axis": [0, 1, 0],
            "limit": [-1.0, 1.0],
            "rest_orientation": [0.7071, 0, 0.7071, 0],
        },
    ],
    "motors": [
        {"joint": "j1", "type": "sinusoid", "amplitude": 1.0, "frequency": 1.5, "phase": -2.0},
        {"joint": "j2", "type": "sinusoid", "amplitude": 1.0, "frequency": 1.5, "phase": -4.0},
        {"joint": "j3", "type": "sinusoid", "amplitude": 1.0, "frequency": 1.5, "phase": -6.0},
        {"joint": "j4", "type": "sinusoid", "amplitude": 1.0, "frequency": 1.5, "phase": -8.0},
    ],
}

# The original example creature. A tripod swinging single-hinge legs has little
# net thrust, so it mostly wiggles in place — kept as a built-in for comparison
# (and as the worked example in ``examples/tripod.json``), not as the demo default.
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

#: Built-in creatures, addressable by name via ``creature-lab demo --creature NAME``.
_BUILTIN_CREATURES: dict[str, dict] = {
    "quadruped": _QUADRUPED,
    "worm": _WORM,
    "tripod": _TRIPOD,
}

_CRAWL_FORWARD = {
    "name": "crawl_forward",
    "duration": 5.0,
    "timestep": 1.0 / 60.0,
    "terrain": {"type": "plane", "friction": 1.0},
    "reward": {"forward_distance": 1.0},
}


def builtin_creature_names() -> list[str]:
    """Names of the built-in creatures available to ``demo --creature``."""
    return list(_BUILTIN_CREATURES)


def creature_by_name(name: str) -> CreatureSpec:
    """Return a built-in creature by name (e.g. ``"worm"``).

    Raises ``KeyError`` (with the available names) if the name is unknown.
    """
    try:
        spec = _BUILTIN_CREATURES[name]
    except KeyError as exc:
        available = ", ".join(builtin_creature_names())
        raise KeyError(f"unknown built-in creature {name!r}; choose one of: {available}") from exc
    return CreatureSpec.model_validate(spec)


def default_creature() -> CreatureSpec:
    """The built-in creature used by ``creature-lab demo`` (a forward-walking quadruped)."""
    return creature_by_name("quadruped")


def default_task() -> TaskSpec:
    """The built-in crawl-forward task used by ``creature-lab demo``."""
    return TaskSpec.model_validate(_CRAWL_FORWARD)
