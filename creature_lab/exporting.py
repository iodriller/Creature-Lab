"""Create and verify portable, self-contained Creature Lab experiment packs."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from creature_lab import VERSION
from creature_lab.controllers.factory import extract_sinusoid_spec
from creature_lab.hashing import spec_hash
from creature_lab.io_utils import atomic_write_text, contained_child
from creature_lab.schema import ControllerSpec, ControllerType, CreatureSpec, EpisodeTrace, TaskSpec

# Version 2 guarantees controller snapshots, copies policy payloads, hashes every
# artifact, and records enough runtime information to verify a pack before use.
DESIGN_PACK_VERSION = "2"

_FALLBACK_NOTE = (
    "best-effort sinusoid extraction from the creature's own motors "
    "(may not reproduce the original controller)"
)


def _fallback_controller(creature: CreatureSpec) -> ControllerSpec:
    return (
        extract_sinusoid_spec(creature)
        if creature.motors
        else ControllerSpec(type=ControllerType.HOLD)
    )


def file_hash(path: Path) -> str:
    """Return a sha256 digest of the exact bytes stored at ``path``."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True)
class ControllerBundle:
    spec: ControllerSpec
    note: str
    exact: bool
    policy_source: Path | None = None


@dataclass(frozen=True)
class DesignPackManifest:
    """Provenance record written as ``manifest.json`` beside a design pack."""

    pack_version: str
    creature_name: str
    task_name: str
    backend: str
    score: float
    creature_hash: str
    task_hash: str | None
    controller_hash: str
    controller_note: str
    trace_hash: str
    artifact_hashes: dict[str, str]
    runtime: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "pack_version": self.pack_version,
            "creature_name": self.creature_name,
            "task_name": self.task_name,
            "backend": self.backend,
            "score": self.score,
            "creature_hash": self.creature_hash,
            "task_hash": self.task_hash,
            "controller_hash": self.controller_hash,
            "controller_note": self.controller_note,
            "trace_hash": self.trace_hash,
            "artifact_hashes": self.artifact_hashes,
            "runtime": self.runtime,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class PackVerification:
    valid: bool
    checks: list[str]
    errors: list[str]


def _controller_from_path(path: Path) -> ControllerBundle:
    spec = ControllerSpec.model_validate_json(path.read_text(encoding="utf-8"))
    policy_source = None
    if spec.type == ControllerType.POLICY:
        if spec.policy_file is None:
            raise ValueError("policy controller requires policy_file")
        policy_source = contained_child(path.parent, spec.policy_file, field="policy_file")
        if not policy_source.is_file():
            raise ValueError(f"policy file not found beside controller: {policy_source}")
    return ControllerBundle(
        spec=spec,
        note=f"copied and snapshotted from controller spec {path}",
        exact=True,
        policy_source=policy_source,
    )


def resolve_controller_bundle(
    creature: CreatureSpec,
    controller_name: str | None,
    *,
    source_dir: Path | None = None,
) -> ControllerBundle:
    """Resolve the exact controller and optional policy payload for a run.

    A saved ``source_dir/controller.json`` wins over the historical CLI string,
    because it is the immutable snapshot made when the run was written.
    """
    if source_dir is not None:
        snapshot = Path(source_dir) / "controller.json"
        if snapshot.is_file():
            bundle = _controller_from_path(snapshot)
            return ControllerBundle(
                spec=bundle.spec,
                note="copied from the controller snapshot stored with the run",
                exact=True,
                policy_source=bundle.policy_source,
            )
    if controller_name is None:
        return ControllerBundle(
            _fallback_controller(creature),
            f"run predates controller tracking; {_FALLBACK_NOTE}",
            False,
        )
    if controller_name.lower().endswith(".json"):
        original = Path(controller_name).expanduser()
        if original.is_file():
            return _controller_from_path(original.resolve())
        return ControllerBundle(
            _fallback_controller(creature),
            f"original controller spec {controller_name!r} no longer exists; {_FALLBACK_NOTE}",
            False,
        )
    if controller_name == ControllerType.SINUSOID.value:
        if not creature.motors:
            return ControllerBundle(
                ControllerSpec(type=ControllerType.HOLD),
                "exact no-actuation equivalent of sinusoid on a creature with no motors",
                True,
            )
        return ControllerBundle(
            extract_sinusoid_spec(creature),
            "extracted from the creature's own motor gait",
            True,
        )
    if controller_name in {
        ControllerType.CPG.value,
        ControllerType.TARGET_SEEK.value,
        ControllerType.POSTURE.value,
        ControllerType.HOLD.value,
    }:
        return ControllerBundle(
            ControllerSpec(type=ControllerType(controller_name)),
            f"the built-in {controller_name!r} controller with default tuning",
            True,
        )
    return ControllerBundle(
        _fallback_controller(creature),
        f"unrecognized controller name {controller_name!r}; {_FALLBACK_NOTE}",
        False,
    )


def write_controller_snapshot(
    destination: Path,
    bundle: ControllerBundle,
) -> tuple[ControllerSpec, str | None]:
    """Write ``controller.json`` and its optional policy payload to a directory."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    spec = bundle.spec
    policy_hash = None
    if bundle.policy_source is not None:
        policy_name = Path(bundle.policy_source).name
        policy_destination = contained_child(destination, policy_name, field="policy_file")
        shutil.copyfile(bundle.policy_source, policy_destination)
        spec = spec.model_copy(update={"policy_file": policy_name})
        policy_hash = file_hash(policy_destination)
    atomic_write_text(
        destination / "controller.json",
        spec.model_dump_json(indent=2, exclude_none=True),
    )
    return spec, policy_hash


def export_design_pack(
    creature: CreatureSpec,
    task: TaskSpec | None,
    trace: EpisodeTrace,
    *,
    out_dir: Path,
    source_dir: Path | None = None,
    overwrite: bool = False,
) -> DesignPackManifest:
    """Atomically create a self-contained, hash-verifiable design pack."""
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if out_dir.exists() and not overwrite:
        raise FileExistsError(f"output directory already exists: {out_dir}")

    controller_name = trace.meta.controller if trace.meta is not None else None
    bundle = resolve_controller_bundle(creature, controller_name, source_dir=source_dir)
    stage = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        atomic_write_text(stage / "creature.json", creature.model_dump_json(indent=2))
        if task is not None:
            atomic_write_text(stage / "task.json", task.model_dump_json(indent=2))
        controller_spec, policy_hash = write_controller_snapshot(stage, bundle)

        updated_meta = trace.meta
        if updated_meta is not None:
            updated_meta = updated_meta.model_copy(
                update={
                    "controller_hash": spec_hash(controller_spec),
                    "controller_artifact": "controller.json",
                    "policy_hash": policy_hash,
                }
            )
        packed_trace = trace.model_copy(update={"meta": updated_meta})
        atomic_write_text(stage / "trace.json", packed_trace.model_dump_json(indent=2))

        artifact_hashes = {
            path.name: file_hash(path) for path in sorted(stage.iterdir()) if path.is_file()
        }
        manifest = DesignPackManifest(
            pack_version=DESIGN_PACK_VERSION,
            creature_name=creature.name,
            task_name=task.name if task is not None else trace.task_name,
            backend=trace.backend,
            score=trace.score,
            creature_hash=spec_hash(creature),
            task_hash=spec_hash(task) if task is not None else None,
            controller_hash=spec_hash(controller_spec),
            controller_note=bundle.note,
            trace_hash=spec_hash(packed_trace),
            artifact_hashes=artifact_hashes,
            runtime={
                "creature_lab": VERSION,
                "python": platform.python_version(),
                "platform": platform.platform(),
            },
            warnings=[] if bundle.exact else [f"controller.json: {bundle.note}"],
        )
        atomic_write_text(
            stage / "manifest.json",
            json.dumps(manifest.to_json_dict(), indent=2, sort_keys=True),
        )

        if out_dir.exists():
            # ``overwrite`` is explicit and the target was resolved above; stage is
            # already complete, so replacement cannot expose a partial pack.
            shutil.rmtree(out_dir)
        os.replace(stage, out_dir)
        return manifest
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def verify_design_pack(pack_dir: Path) -> PackVerification:
    """Validate pack structure, hashes, schemas, and controller payload presence."""
    pack_dir = Path(pack_dir)
    errors: list[str] = []
    checks: list[str] = []
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        return PackVerification(False, [], ["manifest.json is missing"])
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return PackVerification(False, [], [f"manifest.json is unreadable: {exc}"])
    if manifest.get("pack_version") != DESIGN_PACK_VERSION:
        errors.append(
            f"unsupported pack version {manifest.get('pack_version')!r}; "
            f"expected {DESIGN_PACK_VERSION!r}"
        )

    hashes = manifest.get("artifact_hashes")
    if not isinstance(hashes, dict):
        errors.append("manifest artifact_hashes is missing or invalid")
        hashes = {}
    for name, expected in hashes.items():
        try:
            path = contained_child(pack_dir, name, field="manifest artifact")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"artifact is missing: {name}")
        elif file_hash(path) != expected:
            errors.append(f"artifact hash mismatch: {name}")
        else:
            checks.append(f"hash ok: {name}")

    try:
        creature = CreatureSpec.model_validate_json(
            (pack_dir / "creature.json").read_text(encoding="utf-8")
        )
        if spec_hash(creature) != manifest.get("creature_hash"):
            errors.append("creature semantic hash mismatch")
        else:
            checks.append("creature schema and semantic hash ok")
    except (OSError, ValueError) as exc:
        errors.append(f"creature.json is invalid: {exc}")

    task_path = pack_dir / "task.json"
    if task_path.exists():
        try:
            task = TaskSpec.model_validate_json(task_path.read_text(encoding="utf-8"))
            if spec_hash(task) != manifest.get("task_hash"):
                errors.append("task semantic hash mismatch")
            else:
                checks.append("task schema and semantic hash ok")
        except (OSError, ValueError) as exc:
            errors.append(f"task.json is invalid: {exc}")

    try:
        controller = ControllerSpec.model_validate_json(
            (pack_dir / "controller.json").read_text(encoding="utf-8")
        )
        if spec_hash(controller) != manifest.get("controller_hash"):
            errors.append("controller semantic hash mismatch")
        else:
            checks.append("controller schema and semantic hash ok")
        if controller.policy_file is not None:
            policy = contained_child(pack_dir, controller.policy_file, field="policy_file")
            if not policy.is_file():
                errors.append(f"policy payload is missing: {controller.policy_file}")
    except (OSError, ValueError) as exc:
        errors.append(f"controller.json is invalid: {exc}")

    try:
        trace = EpisodeTrace.model_validate_json(
            (pack_dir / "trace.json").read_text(encoding="utf-8")
        )
        if spec_hash(trace) != manifest.get("trace_hash"):
            errors.append("trace semantic hash mismatch")
        else:
            checks.append("trace schema and semantic hash ok")
    except (OSError, ValueError) as exc:
        errors.append(f"trace.json is invalid: {exc}")

    return PackVerification(not errors, checks, errors)
