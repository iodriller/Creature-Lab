"""Tests for the portable ControllerSpec schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from creature_lab.schema import ControllerSpec, ControllerType, MotorGaitSpec


def test_sinusoid_requires_nonempty_motors():
    with pytest.raises(ValidationError, match="non-empty"):
        ControllerSpec.model_validate({"type": "sinusoid"})


def test_sinusoid_with_motors_is_valid():
    spec = ControllerSpec.model_validate(
        {
            "type": "sinusoid",
            "motors": [{"joint": "hip", "amplitude": 0.6, "frequency": 2.0, "phase": 0.0}],
        }
    )
    assert spec.type == ControllerType.SINUSOID
    assert spec.motors == [MotorGaitSpec(joint="hip", amplitude=0.6, frequency=2.0, phase=0.0)]


def test_sinusoid_motor_accepts_a_nonzero_center_offset():
    spec = ControllerSpec.model_validate(
        {
            "type": "sinusoid",
            "motors": [
                {
                    "joint": "hip",
                    "amplitude": 0.2,
                    "frequency": 1.0,
                    "offset": -0.3,
                }
            ],
        }
    )
    assert spec.motors[0].offset == pytest.approx(-0.3)


def test_cpg_rejects_motors_field():
    with pytest.raises(ValidationError, match="only used by a sinusoid"):
        ControllerSpec.model_validate(
            {"type": "cpg", "motors": [{"joint": "hip", "amplitude": 0.5, "frequency": 1.0}]}
        )


def test_target_seek_rejects_motors_field():
    with pytest.raises(ValidationError, match="only used by a sinusoid"):
        ControllerSpec.model_validate(
            {
                "type": "target_seek",
                "motors": [{"joint": "hip", "amplitude": 0.5, "frequency": 1.0}],
            }
        )


def test_cpg_with_no_overrides_is_valid():
    spec = ControllerSpec.model_validate({"type": "cpg"})
    assert spec.amplitude is None  # falls back to CPGController's own defaults


def test_cpg_with_overrides_is_valid():
    spec = ControllerSpec.model_validate(
        {"type": "cpg", "amplitude": 0.9, "frequency": 2.0, "phase_lag": 1.5, "coupling": 4.0}
    )
    assert spec.amplitude == 0.9
    assert spec.coupling == 4.0


def test_target_seek_with_steering_overrides_is_valid():
    spec = ControllerSpec.model_validate(
        {
            "type": "target_seek",
            "turn_gain": 1.5,
            "max_turn_scale": 0.9,
            "slow_radius": 1.2,
            "stop_radius": 0.1,
        }
    )
    assert spec.turn_gain == 1.5
    assert spec.stop_radius == 0.1


def test_posture_with_no_overrides_is_valid():
    spec = ControllerSpec.model_validate({"type": "posture"})
    assert spec.kp is None  # falls back to PostureController's own defaults


def test_posture_with_overrides_is_valid():
    spec = ControllerSpec.model_validate({"type": "posture", "kp": 20.0, "kd": 1.5})
    assert spec.kp == 20.0
    assert spec.kd == 1.5


def test_posture_rejects_motors_field():
    with pytest.raises(ValidationError, match="only used by a sinusoid"):
        ControllerSpec.model_validate(
            {"type": "posture", "motors": [{"joint": "hip", "amplitude": 0.5, "frequency": 1.0}]}
        )


def test_policy_requires_policy_file():
    with pytest.raises(ValidationError, match="requires 'policy_file'"):
        ControllerSpec.model_validate({"type": "policy"})


def test_policy_with_policy_file_is_valid():
    spec = ControllerSpec.model_validate({"type": "policy", "policy_file": "policy.zip"})
    assert spec.policy_file == "policy.zip"


def test_policy_file_rejected_for_other_types():
    with pytest.raises(ValidationError, match="only used by a policy controller"):
        ControllerSpec.model_validate({"type": "cpg", "policy_file": "policy.zip"})


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        ControllerSpec.model_validate({"type": "cpg", "not_a_real_field": 1.0})


def test_default_name_is_set():
    spec = ControllerSpec.model_validate({"type": "cpg"})
    assert spec.name == "controller"


def test_motor_gait_spec_rejects_blank_joint():
    with pytest.raises(ValidationError, match="blank"):
        MotorGaitSpec.model_validate({"joint": "   ", "amplitude": 0.5, "frequency": 1.0})


def test_controller_spec_round_trips_through_json():
    spec = ControllerSpec.model_validate(
        {"name": "my_controller", "type": "target_seek", "turn_gain": 1.1}
    )
    restored = ControllerSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec


@pytest.mark.parametrize("policy_file", ["C:/models/policy.zip", "../policy.zip", "dir/policy.zip"])
def test_policy_file_must_stay_inside_its_bundle(policy_file):
    with pytest.raises(ValidationError, match="filename"):
        ControllerSpec.model_validate({"type": "policy", "policy_file": policy_file})


def test_sinusoid_rejects_duplicate_joint_entries():
    motor = {"joint": "hip", "amplitude": 0.5, "frequency": 1.0}
    with pytest.raises(ValidationError, match="unique"):
        ControllerSpec.model_validate({"type": "sinusoid", "motors": [motor, motor]})


def test_target_seek_stop_radius_cannot_exceed_slow_radius():
    with pytest.raises(ValidationError, match="stop_radius"):
        ControllerSpec.model_validate(
            {"type": "target_seek", "slow_radius": 0.5, "stop_radius": 1.0}
        )


def test_controller_rejects_nonfinite_tuning_values():
    with pytest.raises(ValidationError):
        ControllerSpec.model_validate({"type": "cpg", "frequency": float("inf")})


def test_controller_rejects_irrelevant_type_specific_fields():
    with pytest.raises(ValidationError, match="not used"):
        ControllerSpec.model_validate({"type": "posture", "turn_gain": 2.0})


def test_hold_controller_has_no_tuning_fields():
    assert ControllerSpec.model_validate({"type": "hold"}).type == ControllerType.HOLD
