"""Keyframe pose-sequence controller.

Plays back a list of ``(time, {joint: angle})`` keyframes, linearly interpolating
joint targets between them and holding the endpoints outside the range. Useful for
scripted/hand-authored motion (a "pose animation") rather than a generated gait.
"""

from __future__ import annotations

from creature_lab.schema import FrameState

Keyframe = tuple[float, dict[str, float]]


class PoseSequenceController:
    """Interpolate joint targets across time-stamped keyframes."""

    def __init__(self, keyframes: list[Keyframe]) -> None:
        if not keyframes:
            raise ValueError("pose sequence needs at least one keyframe")
        self._keys = sorted(keyframes, key=lambda kf: kf[0])

    def __call__(self, t: float, prev_frame: FrameState | None = None) -> dict[str, float]:
        keys = self._keys
        if t <= keys[0][0]:
            return dict(keys[0][1])
        if t >= keys[-1][0]:
            return dict(keys[-1][1])
        for (t0, pose0), (t1, pose1) in zip(keys, keys[1:], strict=False):
            if t0 <= t <= t1:
                span = t1 - t0
                frac = 0.0 if span == 0 else (t - t0) / span
                joints = set(pose0) | set(pose1)
                return {
                    j: pose0.get(j, 0.0) + frac * (pose1.get(j, 0.0) - pose0.get(j, 0.0))
                    for j in joints
                }
        return dict(keys[-1][1])  # unreachable, but keeps the type checker happy
