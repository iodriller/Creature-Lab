"""Pure analysis series for the debug viewer and plots.

These derive overlay/plot data straight from a recorded trace (plus the creature for
masses). No viser, no matplotlib, no physics — so they are cheap and unit-testable.
The viewer turns these into 3-D trails; ``plot`` turns them into charts.
"""

from __future__ import annotations

from creature_lab.schema import CreatureSpec, EpisodeTrace

Vector3 = tuple[float, float, float]


def _root_id(creature: CreatureSpec) -> str:
    child_ids = {joint.child for joint in creature.joints}
    return next(part.id for part in creature.parts if part.id not in child_ids)


def center_of_mass_trail(creature: CreatureSpec, trace: EpisodeTrace) -> list[Vector3]:
    """Mass-weighted centre of mass at each frame."""
    masses = {part.id: part.mass for part in creature.parts}
    trail: list[Vector3] = []
    for frame in trace.frames:
        present = [(masses.get(pid, 0.0), pose.position) for pid, pose in frame.parts.items()]
        total = sum(mass for mass, _ in present) or 1.0
        trail.append(
            tuple(sum(mass * pos[axis] for mass, pos in present) / total for axis in range(3))
        )
    return trail


def root_path(creature: CreatureSpec, trace: EpisodeTrace) -> list[Vector3]:
    """The root part's position at each frame (its trajectory through space)."""
    root = _root_id(creature)
    return [tuple(frame.parts[root].position) for frame in trace.frames if root in frame.parts]


def joint_energy_series(trace: EpisodeTrace) -> list[float]:
    """Per-frame actuation-effort proxy: sum of squared joint-angle changes."""
    series: list[float] = []
    previous: dict[str, float] = {}
    for frame in trace.frames:
        energy = 0.0
        for joint_id, angle in frame.joint_angles.items():
            if joint_id in previous:
                delta = angle - previous[joint_id]
                energy += delta * delta
            previous[joint_id] = angle
        series.append(energy)
    return series


#: Metrics exposed by ``creature-lab plot``.
PLOT_METRICS = ("joint_energy", "score", "com_height", "forward_x")


def metric_series(
    trace: EpisodeTrace, creature: CreatureSpec, metric: str
) -> tuple[list[float], list[float]]:
    """Return ``(times, values)`` for a named metric over the episode."""
    times = [frame.t for frame in trace.frames]
    if metric == "joint_energy":
        return times, joint_energy_series(trace)
    if metric == "score":
        return times, [frame.score for frame in trace.frames]
    if metric == "com_height":
        return times, [point[2] for point in center_of_mass_trail(creature, trace)]
    if metric == "forward_x":
        return times, [point[0] for point in center_of_mass_trail(creature, trace)]
    raise ValueError(f"unknown metric {metric!r}; choose one of: {', '.join(PLOT_METRICS)}")
