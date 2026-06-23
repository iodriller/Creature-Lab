"""Procedural worm generator.

A chain of capsule segments laid flat on the ground. Each joint hinges about the
world Y axis and a traveling sine wave down the chain (phase ``-2 rad`` per joint)
drives the worm forward along +X.
"""

from __future__ import annotations

from creature_lab.schema import CreatureSpec

#: Rotates a capsule (default axis +Z) 90 deg about Y so it lies along X.
_LIE_FLAT = (0.7071067811865476, 0.0, 0.7071067811865476, 0.0)


def generate_worm(
    segments: int = 5,
    *,
    seg_length: float = 0.18,
    radius: float = 0.05,
    mass: float = 0.4,
    amplitude: float = 1.0,
    frequency: float = 1.5,
) -> CreatureSpec:
    """Generate a multi-segment worm that crawls forward.

    Args:
        segments: Number of body segments (>= 2).
        seg_length: Length of each capsule segment.
        radius: Capsule radius.
        mass: Mass of each segment.
        amplitude: Joint sine amplitude (rad).
        frequency: Joint sine frequency (Hz).
    """
    if segments < 2:
        raise ValueError("a worm needs at least 2 segments")

    anchor_x = -(seg_length + 0.02)
    parts = []
    joints = []
    motors = []
    for i in range(segments):
        shade = 0.45 + 0.09 * i / max(1, segments - 1)
        parts.append(
            {
                "id": f"seg{i}",
                "shape": "capsule",
                "length": seg_length,
                "radius": radius,
                "mass": mass,
                "color": [0.9, shade, 0.2 + 0.15 * i / max(1, segments - 1)],
            }
        )
        if i == 0:
            continue
        joints.append(
            {
                "id": f"j{i}",
                "parent": f"seg{i - 1}",
                "child": f"seg{i}",
                "type": "hinge",
                "anchor": [anchor_x, 0.0, 0.0],
                "axis": [0, 1, 0],
                "limit": [-1.0, 1.0],
                "rest_orientation": list(_LIE_FLAT),
            }
        )
        motors.append(
            {
                "joint": f"j{i}",
                "type": "sinusoid",
                "amplitude": amplitude,
                "frequency": frequency,
                "phase": -2.0 * i,
            }
        )

    return CreatureSpec.model_validate(
        {"name": "worm", "parts": parts, "joints": joints, "motors": motors}
    )
