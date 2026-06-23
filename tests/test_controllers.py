"""Tests for the CPG, PID, and pose-sequence controllers."""

import pytest

from creature_lab.controllers.cpg import CPGController
from creature_lab.controllers.pid import PIDController
from creature_lab.controllers.pose_seq import PoseSequenceController
from creature_lab.scaffold import generate_quadruped


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
