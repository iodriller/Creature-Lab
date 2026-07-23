"""Tests for bundling a run into a portable design pack."""

from __future__ import annotations

from pathlib import Path

from creature_lab.controllers.factory import extract_sinusoid_spec
from creature_lab.exporting import export_design_pack, verify_design_pack
from creature_lab.hashing import spec_hash
from creature_lab.scaffold import generate_quadruped
from creature_lab.schema import ControllerSpec, ControllerType, EpisodeTrace, TaskSpec


def _task() -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "name": "crawl",
            "duration": 1.0,
            "timestep": 1 / 60,
            "terrain": {"type": "plane", "friction": 1.0},
        }
    )


def _trace(*, controller: str | None, meta: bool = True) -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": "abc123",
            "creature_name": "quad",
            "task_name": "crawl",
            "backend": "pybullet",
            "score": 1.5,
            "frames": [{"t": 0.0, "parts": {"torso": {"position": [0, 0, 0.2]}}}],
            "meta": (
                {"schema_version": "1", "lab_version": "0.1.0", "controller": controller}
                if meta
                else None
            ),
        }
    )


def test_export_writes_all_files_for_a_builtin_controller(tmp_path: Path):
    creature = generate_quadruped()
    task = _task()
    trace = _trace(controller="cpg")

    manifest = export_design_pack(creature, task, trace, out_dir=tmp_path / "pack")

    pack = tmp_path / "pack"
    for name in ("creature.json", "task.json", "controller.json", "trace.json", "manifest.json"):
        assert (pack / name).exists()

    controller_spec = ControllerSpec.model_validate_json((pack / "controller.json").read_text())
    assert controller_spec.type == ControllerType.CPG
    assert controller_spec.amplitude is None  # default tuning, exact reconstruction
    assert manifest.warnings == []
    assert "built-in" in manifest.controller_note


def test_export_extracts_sinusoid_controller_exactly(tmp_path: Path):
    creature = generate_quadruped()
    trace = _trace(controller="sinusoid")

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    controller_spec = ControllerSpec.model_validate_json(
        (tmp_path / "pack" / "controller.json").read_text()
    )
    assert controller_spec == extract_sinusoid_spec(creature)
    assert manifest.warnings == []


def test_export_reconstructs_target_seek_with_default_tuning(tmp_path: Path):
    creature = generate_quadruped()
    trace = _trace(controller="target_seek")

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    controller_spec = ControllerSpec.model_validate_json(
        (tmp_path / "pack" / "controller.json").read_text()
    )
    assert controller_spec.type == ControllerType.TARGET_SEEK
    assert controller_spec.turn_gain is None
    assert manifest.warnings == []


def test_export_copies_an_existing_controller_json_verbatim(tmp_path: Path):
    creature = generate_quadruped()
    original = tmp_path / "my_controller.json"
    spec = ControllerSpec.model_validate({"type": "cpg", "amplitude": 0.42})
    original.write_text(spec.model_dump_json())
    trace = _trace(controller=str(original))

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    controller_spec = ControllerSpec.model_validate_json(
        (tmp_path / "pack" / "controller.json").read_text()
    )
    assert controller_spec == spec
    assert manifest.warnings == []
    assert "copied" in manifest.controller_note


def test_export_falls_back_when_the_controller_json_path_no_longer_exists(tmp_path: Path):
    creature = generate_quadruped()
    trace = _trace(controller=str(tmp_path / "gone.json"))

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    controller_spec = ControllerSpec.model_validate_json(
        (tmp_path / "pack" / "controller.json").read_text()
    )
    assert controller_spec.type == ControllerType.SINUSOID
    assert len(manifest.warnings) == 1
    assert "no longer exists" in manifest.warnings[0]


def test_export_falls_back_with_a_warning_for_a_trace_with_no_controller_recorded(
    tmp_path: Path,
):
    creature = generate_quadruped()
    trace = _trace(controller=None)

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    assert len(manifest.warnings) == 1
    assert "predates controller tracking" in manifest.warnings[0]


def test_export_falls_back_with_a_warning_for_a_trace_with_no_meta_at_all(tmp_path: Path):
    creature = generate_quadruped()
    trace = _trace(controller=None, meta=False)
    assert trace.meta is None

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    assert len(manifest.warnings) == 1


def test_export_falls_back_with_a_warning_for_an_unrecognized_controller_name(tmp_path: Path):
    creature = generate_quadruped()
    trace = _trace(controller="some_future_controller")

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    assert len(manifest.warnings) == 1
    assert "unrecognized" in manifest.warnings[0]


def test_export_without_a_task_skips_task_json_and_falls_back_to_trace_task_name(tmp_path: Path):
    creature = generate_quadruped()
    trace = _trace(controller="cpg")

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")

    assert not (tmp_path / "pack" / "task.json").exists()
    assert manifest.task_name == trace.task_name
    assert manifest.task_hash is None


def test_export_manifest_hashes_match_spec_hash(tmp_path: Path):
    creature = generate_quadruped()
    task = _task()
    trace = _trace(controller="cpg")

    manifest = export_design_pack(creature, task, trace, out_dir=tmp_path / "pack")

    assert manifest.creature_hash == spec_hash(creature)
    assert manifest.task_hash == spec_hash(task)
    assert manifest.pack_version == "2"
    assert manifest.score == trace.score
    assert manifest.backend == trace.backend


def test_manifest_json_on_disk_matches_the_returned_manifest(tmp_path: Path):
    import json

    creature = generate_quadruped()
    trace = _trace(controller="cpg")

    manifest = export_design_pack(creature, None, trace, out_dir=tmp_path / "pack")
    on_disk = json.loads((tmp_path / "pack" / "manifest.json").read_text())

    assert on_disk == manifest.to_json_dict()


def test_verify_pack_detects_tampering(tmp_path: Path):
    creature = generate_quadruped()
    pack = tmp_path / "pack"
    export_design_pack(creature, _task(), _trace(controller="cpg"), out_dir=pack)

    assert verify_design_pack(pack).valid is True
    (pack / "creature.json").write_text("{}")
    result = verify_design_pack(pack)

    assert result.valid is False
    assert any("creature" in error for error in result.errors)


def test_policy_pack_copies_the_model_payload(tmp_path: Path):
    creature = generate_quadruped()
    source = tmp_path / "source"
    source.mkdir()
    (source / "policy.zip").write_bytes(b"fake-policy-payload")
    policy = ControllerSpec(
        type=ControllerType.POLICY,
        policy_file="policy.zip",
    )
    controller_path = source / "controller.json"
    controller_path.write_text(policy.model_dump_json())

    pack = tmp_path / "pack"
    export_design_pack(
        creature,
        _task(),
        _trace(controller=str(controller_path)),
        out_dir=pack,
    )

    assert (pack / "policy.zip").read_bytes() == b"fake-policy-payload"
    assert verify_design_pack(pack).valid is True


def test_posture_builtin_is_exported_exactly(tmp_path: Path):
    pack = tmp_path / "pack"
    manifest = export_design_pack(
        generate_quadruped(), _task(), _trace(controller="posture"), out_dir=pack
    )

    controller = ControllerSpec.model_validate_json((pack / "controller.json").read_text())
    assert controller.type == ControllerType.POSTURE
    assert manifest.warnings == []
