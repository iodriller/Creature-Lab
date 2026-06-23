"""Central Pattern Generator: coupled phase oscillators that produce a gait.

One oscillator per motored joint, ordered along the kinematic chain. Neighbours are
phase-coupled (Kuramoto style) toward a fixed phase lag, so the network settles into a
coordinated traveling wave even when the creature's own motor phases are uniform. This
is the difference from a plain open-loop sinusoid: the joints cooperate.

Stateful: call it once per timestep with the current time; it integrates the phases by
the elapsed dt and returns a target angle per joint.
"""

from __future__ import annotations

import math

from creature_lab.schema import CreatureSpec, FrameState, JointType


def _chain_order(creature: CreatureSpec) -> list[str]:
    """Motored hinge-joint ids ordered by a breadth-first walk from the root."""
    child_ids = {j.child for j in creature.joints}
    root = next(p.id for p in creature.parts if p.id not in child_ids)
    by_parent: dict[str, list] = {}
    for joint in creature.joints:
        by_parent.setdefault(joint.parent, []).append(joint)
    motored = {m.joint for m in creature.motors}

    order: list[str] = []
    queue = [root]
    while queue:
        part = queue.pop(0)
        for joint in by_parent.get(part, []):
            if joint.type == JointType.HINGE and joint.id in motored:
                order.append(joint.id)
            queue.append(joint.child)
    return order


class CPGController:
    """A coupled-oscillator gait generator over a creature's motored joints."""

    def __init__(
        self,
        creature: CreatureSpec,
        *,
        amplitude: float = 0.8,
        frequency: float = 1.5,
        phase_lag: float = 2.0,
        coupling: float = 6.0,
    ) -> None:
        self.amplitude = amplitude
        self.frequency = frequency
        self.phase_lag = phase_lag
        self.coupling = coupling
        self._joints = _chain_order(creature)
        # Seed phases as a traveling wave so it starts near the coordinated solution.
        self._phases = [(-phase_lag * i) for i in range(len(self._joints))]
        self._last_t = 0.0

    def reset(self) -> None:
        self._phases = [(-self.phase_lag * i) for i in range(len(self._joints))]
        self._last_t = 0.0

    def __call__(self, t: float, prev_frame: FrameState | None = None) -> dict[str, float]:
        dt = max(0.0, t - self._last_t)
        self._last_t = t
        omega = 2 * math.pi * self.frequency
        n = len(self._phases)
        new = list(self._phases)
        for i in range(n):
            coupling_term = 0.0
            for j in (i - 1, i + 1):
                if 0 <= j < n:
                    desired = self.phase_lag if j < i else -self.phase_lag
                    coupling_term += self.coupling * math.sin(
                        self._phases[j] - self._phases[i] - desired
                    )
            new[i] = self._phases[i] + dt * (omega + coupling_term)
        self._phases = new
        return {
            joint: self.amplitude * math.sin(phase)
            for joint, phase in zip(self._joints, self._phases, strict=True)
        }
