"""Backend-neutral data contracts for Creature Lab.

This package is the source of truth for creatures, tasks, and traces. It must not
import any physics engine.
"""

from creature_lab.schema.agent import AgentStep, AgentTrace
from creature_lab.schema.base import (
    ColorRGB,
    JointLimit,
    Quaternion,
    StrictModel,
    Vector3,
)
from creature_lab.schema.creature import (
    CreatureSpec,
    JointSpec,
    JointType,
    MotorSpec,
    MotorType,
    PartSpec,
    ShapeType,
)
from creature_lab.schema.task import (
    DamageEventSpec,
    RewardSpec,
    TargetSpec,
    TargetType,
    TaskSpec,
    TerrainSpec,
    TerrainType,
)
from creature_lab.schema.trace import (
    ContactSpec,
    EpisodeTrace,
    FrameState,
    PartPose,
)

__all__ = [
    "AgentStep",
    "AgentTrace",
    "ColorRGB",
    "ContactSpec",
    "CreatureSpec",
    "DamageEventSpec",
    "EpisodeTrace",
    "FrameState",
    "JointLimit",
    "JointSpec",
    "JointType",
    "MotorSpec",
    "MotorType",
    "PartPose",
    "PartSpec",
    "Quaternion",
    "RewardSpec",
    "ShapeType",
    "StrictModel",
    "TargetSpec",
    "TargetType",
    "TaskSpec",
    "TerrainSpec",
    "TerrainType",
    "Vector3",
]
