"""Backend-neutral simulator protocol.

Every physics engine adapter (PyBullet first, others later) implements this
protocol. Code outside `backends/` must only depend on this interface, never
on a specific engine.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from creature_lab.schema import CreatureSpec, FrameState, TaskSpec


@runtime_checkable
class SimBackend(Protocol):
    def build(self, creature: CreatureSpec, task: TaskSpec) -> None: ...
    def reset(self) -> None: ...
    def step(self, dt: float) -> FrameState: ...
    def apply_motor_targets(self, targets: dict[str, float]) -> None: ...
    def damage_part(self, part_id: str) -> None: ...
    def close(self) -> None: ...
