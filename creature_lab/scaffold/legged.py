"""Procedural legged-creature generators (quadruped, hexapod).

Both share one body plan: a box torso with capsule legs anchored along its sides.
Each leg hinges fore/aft about Y and is tilted backward at rest (``rest_orientation``)
so the swing acts like an oar and yields net forward thrust along +X. Legs alternate
phase in a diagonal/tripod gait so the body stays upright and tracks straight.
"""

from __future__ import annotations

import math

from creature_lab.schema import CreatureSpec

#: Backward leg tilt (about Y) that turns a fore/aft swing into forward thrust.
_TILT_DEG = 35.0


def _tilt_quat(degrees: float) -> list[float]:
    """Quaternion (w, x, y, z) for a rotation of ``-degrees`` about the Y axis."""
    half = math.radians(-degrees) / 2.0
    return [math.cos(half), 0.0, math.sin(half), 0.0]


def _build_legged(
    name: str,
    leg_rows: list[float],
    *,
    body_length: float,
    body_width: float,
    leg_length: float,
    leg_radius: float,
    amplitude: float,
    frequency: float,
    gait: str = "diagonal",
) -> CreatureSpec:
    """Build a legged creature with one leg pair per entry in ``leg_rows`` (x offsets).

    ``gait`` sets the per-leg phase: ``"diagonal"`` (opposite corners in phase — a
    trot, best for four legs) or ``"lateral"`` (all left legs vs all right legs — a
    pace, which tracks straighter with three or more leg pairs).
    """
    tilt = _tilt_quat(_TILT_DEG)
    parts = [
        {
            "id": "torso",
            "shape": "box",
            "size": [body_length, body_width, 0.08],
            "mass": 1.0,
            "color": [0.2, 0.55, 0.9],
        }
    ]
    joints = []
    motors = []
    half_w = body_width / 2.0 + 0.0
    # Alternating-tripod / diagonal gait: opposite corners share a phase.
    for row_index, x in enumerate(leg_rows):
        for side, y in (("l", half_w), ("r", -half_w)):
            leg_id = f"leg_{row_index}{side}"
            hip_id = f"hip_{row_index}{side}"
            if gait == "lateral":
                phase = math.pi if side == "r" else 0.0
            else:  # diagonal trot: opposite corners share a phase
                phase = math.pi if ((row_index + (side == "r")) % 2) else 0.0
            parts.append(
                {
                    "id": leg_id,
                    "shape": "capsule",
                    "length": leg_length,
                    "radius": leg_radius,
                    "mass": 0.15,
                    "color": [0.3, 0.7, 0.95] if side == "l" else [0.25, 0.6, 0.9],
                }
            )
            joints.append(
                {
                    "id": hip_id,
                    "parent": "torso",
                    "child": leg_id,
                    "type": "hinge",
                    "anchor": [x, y, -0.04],
                    "axis": [0, 1, 0],
                    "limit": [-1.2, 1.2],
                    "rest_orientation": tilt,
                }
            )
            motors.append(
                {
                    "joint": hip_id,
                    "type": "sinusoid",
                    "amplitude": amplitude,
                    "frequency": frequency,
                    "phase": phase,
                }
            )

    return CreatureSpec.model_validate(
        {"name": name, "parts": parts, "joints": joints, "motors": motors}
    )


def generate_quadruped(
    *,
    leg_length: float = 0.22,
    body_length: float = 0.4,
    body_width: float = 0.32,
    amplitude: float = 0.7,
    frequency: float = 2.0,
) -> CreatureSpec:
    """Generate a four-legged walker that paddles forward along +X."""
    rows = [body_length * 0.375, -body_length * 0.375]  # front, rear
    return _build_legged(
        "quadruped",
        rows,
        body_length=body_length,
        body_width=body_width,
        leg_length=leg_length,
        leg_radius=0.03,
        amplitude=amplitude,
        frequency=frequency,
    )


def generate_hexapod(
    *,
    leg_length: float = 0.2,
    body_length: float = 0.6,
    body_width: float = 0.3,
    amplitude: float = 0.7,
    frequency: float = 2.0,
) -> CreatureSpec:
    """Generate a six-legged walker (three leg pairs) with an alternating-tripod gait."""
    rows = [body_length * 0.4, 0.0, -body_length * 0.4]  # front, middle, rear
    return _build_legged(
        "hexapod",
        rows,
        body_length=body_length,
        body_width=body_width,
        leg_length=leg_length,
        leg_radius=0.028,
        amplitude=amplitude,
        frequency=frequency,
        gait="lateral",
    )
