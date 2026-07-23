"""Procedural humanoid generator.

A bipedal body plan: a box torso (root) with a head, two legs, and two arms.
``dof`` selects how many actuated hinges:

* ``8``  — legs (hip, knee) and arms (shoulder, elbow), 4 hinges per side.
* ``12`` — adds an ankle with a horizontal foot and a wrist/hand per side,
  6 hinges per side.

All joints hinge in the sagittal plane (about Y). The 12-DOF proportions, feet,
and actuator scaling are the body used by the packaged humanoid walking example;
its measured gait remains a separate controller artifact.
"""

from __future__ import annotations

import math
from typing import Literal

from creature_lab.schema import CreatureSpec

_LIMB_COLOR = [0.85, 0.5, 0.55]
_TORSO_COLOR = [0.4, 0.45, 0.7]


def generate_humanoid(
    *,
    height: float = 1.6,
    mass: float = 60.0,
    dof: Literal[8, 12] = 12,
    torso_height_ratio: float = 0.25,
    torso_width_ratio: float = 0.18,
    upper_leg_ratio: float = 0.20,
    lower_leg_ratio: float = 0.20,
    upper_arm_ratio: float = 0.18,
    lower_arm_ratio: float = 0.16,
    shoulder_extra_ratio: float = 0.04,
    limb_radius_ratio: float = 0.035,
    hip_spread_ratio: float = 0.5,
    amplitude: float = 0.4,
    frequency: float = 1.0,
) -> CreatureSpec:
    """Generate a bipedal humanoid skeleton.

    Args:
        height: Approximate standing height (m); all segments scale from it.
        mass: Total mass (kg), distributed across the segments.
        dof: 12 (default; adds ankle/foot + wrist/hand) or 8 (the explicit
            footless balance challenge).
        *_ratio: Body proportions as fractions of height, surfaced by the build editor.
        hip_spread_ratio: Hip lateral offset as a fraction of torso width (wider =
            a bigger support polygon underneath = more passively stable).
        amplitude, frequency: Uniform sinusoid gait applied to every hinge motor.
            Defaults match the original hardcoded values, so every existing caller
            that doesn't pass these gets an identical creature.
    """
    if dof not in (8, 12):
        raise ValueError("dof must be 8 or 12")
    ratios = {
        "torso_height_ratio": torso_height_ratio,
        "torso_width_ratio": torso_width_ratio,
        "upper_leg_ratio": upper_leg_ratio,
        "lower_leg_ratio": lower_leg_ratio,
        "upper_arm_ratio": upper_arm_ratio,
        "lower_arm_ratio": lower_arm_ratio,
        "shoulder_extra_ratio": shoulder_extra_ratio,
        "limb_radius_ratio": limb_radius_ratio,
    }
    for name, value in ratios.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    has_feet_hands = dof == 12
    # Segment lengths as fractions of height.
    torso_h = torso_height_ratio * height
    torso_w = torso_width_ratio * height
    upper_leg = upper_leg_ratio * height
    lower_leg = lower_leg_ratio * height
    foot_len = 0.22 * height
    foot_width = 0.1125 * height
    foot_height = 0.05 * height
    upper_arm = upper_arm_ratio * height
    lower_arm = lower_arm_ratio * height
    hand_len = 0.08 * height

    parts: list[dict] = [
        {
            "id": "torso",
            "shape": "box",
            "size": [0.12 * height, torso_w, torso_h],
            "mass": 0.45 * mass,
            "color": _TORSO_COLOR,
        },
        {
            "id": "head",
            "shape": "sphere",
            "radius": 0.08 * height,
            "mass": 0.08 * mass,
            "color": [0.9, 0.75, 0.6],
        },
    ]
    joints: list[dict] = [
        {
            "id": "neck",
            "parent": "torso",
            "child": "head",
            "type": "fixed",
            "anchor": [0.0, 0.0, torso_h / 2 + 0.08 * height],
        }
    ]
    motors: list[dict] = []

    def add_capsule(part_id: str, length: float, seg_mass: float) -> None:
        parts.append(
            {
                "id": part_id,
                "shape": "capsule",
                "length": length,
                "radius": limb_radius_ratio * height,
                "mass": seg_mass,
                "color": _LIMB_COLOR,
            }
        )

    def add_hinge(
        joint_id: str, parent: str, child: str, anchor: list[float], phase: float
    ) -> None:
        joints.append(
            {
                "id": joint_id,
                "parent": parent,
                "child": child,
                "type": "hinge",
                "anchor": anchor,
                "axis": [0, 1, 0],
                "limit": [-1.2, 1.2],
            }
        )
        motors.append(
            {
                "joint": joint_id,
                "type": "sinusoid",
                "amplitude": amplitude,
                "frequency": frequency,
                "phase": phase,
                # A human-scale joint needs more than the small-creature backend
                # default. Scale torque with mass so dynamic similarity is retained.
                "max_force": 160.0 * mass / 60.0,
            }
        )

    leg_mass = 0.12 * mass
    arm_mass = 0.06 * mass
    for side, sign, base_phase in (("l", 1.0, 0.0), ("r", -1.0, math.pi)):
        hip_y = sign * torso_w * hip_spread_ratio
        shoulder_y = sign * (torso_w * 0.5 + shoulder_extra_ratio * height)
        # Leg chain: hip -> upper leg -> knee -> lower leg (-> ankle -> foot).
        add_capsule(f"upper_leg_{side}", upper_leg, leg_mass)
        add_hinge(
            f"hip_{side}", "torso", f"upper_leg_{side}", [0.0, hip_y, -torso_h / 2], base_phase
        )
        add_capsule(f"lower_leg_{side}", lower_leg, leg_mass * 0.7)
        add_hinge(
            f"knee_{side}",
            f"upper_leg_{side}",
            f"lower_leg_{side}",
            [0.0, 0.0, -upper_leg],
            base_phase,
        )
        if has_feet_hands:
            parts.append(
                {
                    "id": f"foot_{side}",
                    "shape": "box",
                    "size": [foot_len, foot_width, foot_height],
                    "mass": leg_mass * 0.3,
                    "color": _LIMB_COLOR,
                }
            )
            add_hinge(
                f"ankle_{side}",
                f"lower_leg_{side}",
                f"foot_{side}",
                [0.0, 0.0, -lower_leg],
                base_phase,
            )
        # Arm chain: shoulder -> upper arm -> elbow -> lower arm (-> wrist -> hand).
        add_capsule(f"upper_arm_{side}", upper_arm, arm_mass)
        add_hinge(
            f"shoulder_{side}",
            "torso",
            f"upper_arm_{side}",
            [0.0, shoulder_y, torso_h / 2 - 0.04 * height],
            base_phase + math.pi,
        )
        add_capsule(f"lower_arm_{side}", lower_arm, arm_mass * 0.7)
        add_hinge(
            f"elbow_{side}",
            f"upper_arm_{side}",
            f"lower_arm_{side}",
            [0.0, 0.0, -upper_arm],
            base_phase,
        )
        if has_feet_hands:
            add_capsule(f"hand_{side}", hand_len, arm_mass * 0.3)
            add_hinge(
                f"wrist_{side}",
                f"lower_arm_{side}",
                f"hand_{side}",
                [0.0, 0.0, -lower_arm],
                base_phase,
            )

    # The allocation weights above historically summed to 1.25 for a 12-DOF
    # humanoid. Normalize at the public boundary so ``mass`` really is total mass.
    mass_scale = mass / sum(part["mass"] for part in parts)
    for part in parts:
        part["mass"] *= mass_scale

    return CreatureSpec.model_validate(
        {
            "name": "humanoid_12dof" if dof == 12 else "humanoid_minimal",
            "parts": parts,
            "joints": joints,
            "motors": motors,
        }
    )
