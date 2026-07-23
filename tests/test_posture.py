"""Tests for the closed-loop pitch-stabilizing posture/balance controller."""

from __future__ import annotations

import pytest

from creature_lab.controllers.posture import (
    PostureController,
    _pitch_lean,
    default_stabilized_joints,
)
from creature_lab.editor import presets
from creature_lab.schema import TaskSpec


def _push_task(force: tuple[float, float, float] | None, *, duration: float = 3.0) -> TaskSpec:
    data: dict = {
        "name": "push_test",
        "duration": duration,
        "timestep": 1 / 60,
        "terrain": {"type": "plane", "friction": 1.0},
        "reward": {"forward_distance": 0.0, "survival": 1.0, "fall_penalty": 1.0},
    }
    if force is not None:
        data["impulse_event"] = {"time": 0.5, "part_id": "torso", "force": list(force)}
    return TaskSpec.model_validate(data)


def test_pitch_lean_is_zero_when_upright():
    assert _pitch_lean((1.0, 0.0, 0.0, 0.0)) == pytest.approx(0.0)


def test_default_stabilized_joints_prefers_hips():
    creature = presets.generate_creature("humanoid")
    joints = default_stabilized_joints(creature)
    assert joints  # non-empty
    assert set(joints) == {"hip_l", "hip_r"}


def test_default_stabilized_joints_falls_back_to_all_motors_when_no_match():
    from creature_lab.scaffold import generate_worm

    creature = generate_worm(4)  # 'seg'-chain joints, no hip/knee/ankle naming
    joints = default_stabilized_joints(creature)
    assert joints == [m.joint for m in creature.motors]


def test_posture_controller_covers_every_stabilized_joint_from_the_first_call():
    creature = presets.generate_creature("humanoid")
    controller = PostureController(creature)
    targets = controller(0.0, None)
    assert set(default_stabilized_joints(creature)) <= set(targets)


def test_posture_controller_reset_clears_derivative_state():
    creature = presets.generate_creature("humanoid")
    controller = PostureController(creature)
    controller(0.0, None)
    controller(0.02, None)
    controller.reset()
    assert controller._prev_lean is None
    assert controller._prev_t is None


def test_posture_controller_is_deterministic():
    creature = presets.generate_creature("humanoid")
    a, b = PostureController(creature), PostureController(creature)
    for t in (0.0, 0.02, 0.04):
        assert a(t, None) == b(t, None)


# -- real physics: does it actually keep the humanoid upright? --------------------


def _run(controller, push_force, *, duration=4.0):
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend
    from creature_lab.diagnosis import first_fall_time
    from creature_lab.schema import EpisodeTrace

    creature = presets.generate_creature("humanoid")
    task = _push_task(push_force, duration=duration)
    backend = PyBulletBackend()
    backend.build(creature, task)
    frames = []
    prev = None
    try:
        for i in range(task.step_count()):
            backend.apply_motor_targets(controller(i * task.timestep, prev))
            prev = backend.step(task.timestep)
            frames.append(prev)
    finally:
        backend.close()
    trace = EpisodeTrace(
        run_id="x",
        creature_name=creature.name,
        task_name=task.name,
        backend="pybullet",
        score=frames[-1].score,
        frames=frames,
    )
    return first_fall_time(trace, creature)


def test_posture_controller_survives_a_forward_push_that_topples_a_static_stance():
    """The core claim: PD pitch correction measurably improves on doing nothing.
    Measured (not assumed): a static stance (kp=kd=0) falls under a 3000N
    forward push at t=0.5s; PostureController's default gains never fall."""
    pytest.importorskip("pybullet")
    creature = presets.generate_creature("humanoid")

    baseline = PostureController(creature, kp=0.0, kd=0.0)
    baseline_fell = _run(baseline, (3000.0, 0.0, 0.0))
    assert baseline_fell is not None  # confirms the scenario is a real test of something

    stabilized = PostureController(creature)  # default (measured) gains
    stabilized_fell = _run(stabilized, (3000.0, 0.0, 0.0))
    assert stabilized_fell is None


@pytest.mark.parametrize("force", [(2000.0, 0.0, 0.0), (3000.0, 0.0, 0.0), (-3000.0, 0.0, 0.0)])
def test_posture_controller_survives_a_range_of_fore_aft_pushes(force):
    creature = presets.generate_creature("humanoid")
    controller = PostureController(creature)
    assert _run(controller, force) is None


def test_posture_controller_does_not_destabilize_an_unpushed_stance():
    """A controller that only looks good against the one push it was tuned on, but
    falls over on its own with no disturbance at all, is worse than useless. Checked
    over a longer 8s window since a slow-building oscillation needs time to show up."""
    creature = presets.generate_creature("humanoid")
    controller = PostureController(creature)
    assert _run(controller, None, duration=8.0) is None


def test_posture_controller_survives_the_packaged_push_recovery_force_passively():
    """The humanoid's passive stance (feet + tuning from the Phase 4.5 stability
    sweep) already survives the packaged push_recovery task's exact lateral force
    (1500N) with or without active correction - not because posture control fixed
    lateral balance, but because it never needed to for this specific force."""
    creature = presets.generate_creature("humanoid")
    no_correction = PostureController(creature, kp=0.0, kd=0.0)
    with_correction = PostureController(creature)
    assert _run(no_correction, (0.0, 1500.0, 0.0)) is None
    assert _run(with_correction, (0.0, 1500.0, 0.0)) is None


def test_posture_controller_cannot_recover_a_lateral_push_beyond_passive_capacity():
    """Honest limitation, not a bug: every creature in this codebase actuates hips/
    knees/ankles with a single sagittal (Y-axis) hinge, so there is no roll-
    correcting degree of freedom anywhere. Measured: passive stance alone survives
    lateral pushes up to ~3500N; a stronger lateral push (4000N) still topples the
    creature even with active pitch correction, since pitch correction cannot act on
    roll. If this ever starts passing, the skeleton gained a roll DOF and this note
    (and docs/KNOWN_ISSUES.md) should be revisited."""
    creature = presets.generate_creature("humanoid")
    controller = PostureController(creature)
    assert _run(controller, (0.0, 4000.0, 0.0)) is not None
