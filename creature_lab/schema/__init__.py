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
from creature_lab.schema.control import ActionSpec, ObservationSpec
from creature_lab.schema.controller import ControllerSpec, ControllerType, MotorGaitSpec
from creature_lab.schema.creature import (
    CreatureSpec,
    JointSpec,
    JointType,
    MotorSpec,
    MotorType,
    PartSpec,
    ShapeType,
)
from creature_lab.schema.summary import EpisodeSummary
from creature_lab.schema.task import (
    DamageEventSpec,
    ImpulseEventSpec,
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
    TraceMeta,
)

__all__ = [
    "ActionSpec",
    "AgentStep",
    "AgentTrace",
    "ColorRGB",
    "ContactSpec",
    "ControllerSpec",
    "ControllerType",
    "CreatureSpec",
    "DamageEventSpec",
    "EpisodeSummary",
    "EpisodeTrace",
    "FrameState",
    "ImpulseEventSpec",
    "JointLimit",
    "JointSpec",
    "JointType",
    "MotorGaitSpec",
    "MotorSpec",
    "MotorType",
    "ObservationSpec",
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
    "TraceMeta",
    "Vector3",
]
