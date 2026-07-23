"""Tests for the CPG, PID, pose-sequence, and target-seeking controllers."""

import math

import pytest

from creature_lab.controllers.cpg import CPGController
from creature_lab.controllers.pid import PIDController
from creature_lab.controllers.pose_seq import PoseSequenceController
from creature_lab.controllers.target_seek import TargetSeekController
from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import TaskSpec


def test_cpg_targets_cover_all_motored_joints():
    creature = generate_quadruped()
    cpg = CPGController(creature)
    targets = cpg(0.1)
    assert set(targets) == {m.joint for m in creature.motors}


def test_cpg_produces_distinct_per_joint_phases():
    creature = generate_quadruped()
    cpg = CPGController(creature)
    # Advance a few steps; the coupled oscillators should not all be identical.
    for t in range(1, 6):
        targets = cpg(t * 0.05)
    assert len(set(round(v, 4) for v in targets.values())) > 1


def test_cpg_resets_phases():
    cpg = CPGController(generate_quadruped())
    cpg(0.1)
    cpg(0.2)
    cpg.reset()
    assert cpg(0.0)  # callable again from t=0 without error


def test_pid_drives_error_to_zero():
    pid = PIDController(kp=0.5)
    measurement = 0.0
    setpoint = 1.0
    errors = []
    for _ in range(60):
        output = pid.step(setpoint, measurement, dt=0.1)
        measurement += output * 0.1  # simple integrator plant
        errors.append(abs(setpoint - measurement))
    assert errors[-1] < errors[0]
    assert errors[-1] < 0.05


def test_pid_rejects_nonpositive_dt():
    with pytest.raises(ValueError, match="dt must be positive"):
        PIDController(kp=1.0).step(1.0, 0.0, dt=0.0)


def test_pose_sequence_interpolates_and_clamps():
    ctrl = PoseSequenceController([(0.0, {"j": 0.0}), (1.0, {"j": 1.0})])
    assert ctrl(-1.0)["j"] == pytest.approx(0.0)  # clamp before
    assert ctrl(0.5)["j"] == pytest.approx(0.5)  # interpolate
    assert ctrl(2.0)["j"] == pytest.approx(1.0)  # clamp after


def test_pose_sequence_requires_keyframes():
    with pytest.raises(ValueError, match="at least one keyframe"):
        PoseSequenceController([])


def test_cpg_beats_single_phase_sinusoid():
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend
    from creature_lab.controllers.sinusoid import sinusoid_targets
    from creature_lab.schema import CreatureSpec, TaskSpec

    # A quadruped whose motors all share phase 0 => uncoordinated "single sinusoid".
    data = generate_quadruped().model_dump()
    for motor in data["motors"]:
        motor["phase"] = 0.0
    naive = CreatureSpec.model_validate(data)
    task = TaskSpec.model_validate(
        {
            "name": "f",
            "duration": 4.0,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "reward": {"forward_distance": 1.0},
        }
    )

    def run(controller) -> float:
        backend = PyBulletBackend()
        backend.build(naive, task)
        prev = None
        try:
            for i in range(task.step_count()):
                backend.apply_motor_targets(controller(i * task.timestep, prev))
                prev = backend.step(task.timestep)
        finally:
            backend.close()
        return prev.score

    sinusoid_score = run(lambda t, prev=None: sinusoid_targets(naive, t))
    cpg_score = run(CPGController(naive))
    assert cpg_score > sinusoid_score


# -- target-seeking controller --------------------------------------------------


def _task_with_target(target_xy: tuple[float, float], *, duration: float = 3.0) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "name": "reach",
            "duration": duration,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "target": {"position": [target_xy[0], target_xy[1], 0.15], "radius": 0.15},
            "reward": {"target_distance": 1.0},
        }
    )


def test_target_seek_requires_a_target():
    task = TaskSpec.model_validate({"name": "no_target", "duration": 1.0})
    with pytest.raises(ValueError, match="requires a task with a target"):
        TargetSeekController(generate_quadruped(), task)


def _run_target_seek(creature, task, **kwargs) -> list:
    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend

    controller = TargetSeekController(creature, task, **kwargs)
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
    return frames


def _bearing_error(frame, target_xy: tuple[float, float], root_id: str = "torso") -> float:
    from creature_lab.controllers.target_seek import _forward_xy, _wrap_to_pi

    pose = frame.parts[root_id]
    dx = target_xy[0] - pose.position[0]
    dy = target_xy[1] - pose.position[1]
    fx, fy = _forward_xy(pose.orientation)
    return abs(_wrap_to_pi(math.atan2(dy, dx) - math.atan2(fy, fx)))


@pytest.mark.parametrize("target_xy", [(0.0, 1.5), (0.0, -1.5)])
def test_target_seek_turns_toward_an_off_axis_target(target_xy):
    """Target directly left (+y) or right (-y): steering should shrink the bearing
    error over the episode, regardless of which side it has to turn toward."""
    creature = generate_quadruped()
    task = _task_with_target(target_xy)

    initial_error = math.atan2(target_xy[1], target_xy[0])  # robot starts facing +x at origin
    frames = _run_target_seek(creature, task)
    final_error = _bearing_error(frames[-1], target_xy)

    assert final_error < abs(initial_error) - 0.3  # meaningfully closed the bearing gap


def test_target_seek_approaches_a_target_directly_ahead():
    creature = generate_quadruped()
    task = _task_with_target((1.5, 0.0))

    frames = _run_target_seek(creature, task)

    initial_distance = 1.5
    final_pos = frames[-1].parts["torso"].position
    final_distance = math.hypot(1.5 - final_pos[0], 0.0 - final_pos[1])
    assert final_distance < initial_distance - 0.3


def test_target_seek_slows_and_stops_near_a_close_target():
    """A target already inside the stop radius should damp the gait toward zero
    almost immediately, so the body travels far less than an un-throttled CPG gait
    would over the same duration."""
    creature = generate_quadruped()
    close_task = _task_with_target((0.05, 0.0), duration=2.0)

    frames = _run_target_seek(creature, close_task)
    seek_travel = math.hypot(
        frames[-1].parts["torso"].position[0] - frames[0].parts["torso"].position[0],
        frames[-1].parts["torso"].position[1] - frames[0].parts["torso"].position[1],
    )

    pytest.importorskip("pybullet")
    from creature_lab.backends.pybullet_backend import PyBulletBackend

    plain_task = TaskSpec.model_validate(
        {
            "name": "plain",
            "duration": 2.0,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
            "reward": {"forward_distance": 1.0},
        }
    )
    backend = PyBulletBackend()
    backend.build(creature, plain_task)
    cpg = CPGController(creature)
    prev = None
    try:
        for i in range(plain_task.step_count()):
            backend.apply_motor_targets(cpg(i * plain_task.timestep, prev))
            prev = backend.step(plain_task.timestep)
    finally:
        backend.close()
    plain_travel = math.hypot(
        prev.parts["torso"].position[0] - 0.0, prev.parts["torso"].position[1] - 0.0
    )

    assert seek_travel < plain_travel * 0.5


def test_target_seek_is_deterministic():
    creature = generate_quadruped()
    task = _task_with_target((1.0, 0.5))

    frames_a = _run_target_seek(creature, task)
    frames_b = _run_target_seek(creature, task)

    assert [f.parts["torso"].position for f in frames_a] == [
        f.parts["torso"].position for f in frames_b
    ]
