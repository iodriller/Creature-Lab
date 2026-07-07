"""Run report generation for saved Creature Lab artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from creature_lab.diagnostics import summarize_episode
from creature_lab.hashing import spec_hash
from creature_lab.runs import DEFAULT_RUNS_DIR, resolve_run_path
from creature_lab.schema import AgentTrace, CreatureSpec, EpisodeTrace, TaskSpec


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _load_artifacts(
    path: Path, runs_dir: Path
) -> tuple[Path, CreatureSpec | None, TaskSpec | None, EpisodeTrace]:
    resolved = resolve_run_path(path, runs_dir=runs_dir)
    run_dir = resolved if resolved.is_dir() else resolved.parent
    trace_path = run_dir / "trace.json" if resolved.is_dir() else resolved
    trace = EpisodeTrace.model_validate_json(trace_path.read_text())

    creature_path = run_dir / "creature.json"
    task_path = run_dir / "task.json"
    creature = (
        CreatureSpec.model_validate_json(creature_path.read_text())
        if creature_path.exists()
        else None
    )
    task = TaskSpec.model_validate_json(task_path.read_text()) if task_path.exists() else None
    return run_dir, creature, task, trace


def _lineage_summary(run_dir: Path) -> dict[str, Any] | None:
    data = _load_json(run_dir / "lineage.json")
    if data is None:
        return None
    nodes = data.get("nodes", [])
    scores = [node["score"] for node in nodes if "score" in node]
    accepted = [node for node in nodes if node.get("accepted")]
    return {
        "kind": "evolve",
        "strategy": data.get("strategy"),
        "attempts": max(0, len(nodes) - 1),
        "seed_score": scores[0] if scores else None,
        "best_score": max(scores) if scores else None,
        "accepted": max(0, len(accepted) - 1),
    }


def _agent_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "agent.json"
    if not path.exists():
        return None
    trace = AgentTrace.model_validate_json(path.read_text())
    accepted = [step for step in trace.steps if step.accepted and step.attempt > 0]
    invalid = [step for step in trace.steps if not step.valid]
    return {
        "kind": "ask",
        "goal": trace.goal,
        "attempts": max(0, len(trace.steps) - 1),
        "best_score": trace.best_score,
        "accepted": len(accepted),
        "invalid": len(invalid),
    }


def _artifact_paths(run_dir: Path) -> dict[str, str]:
    names = {
        "run_dir": run_dir,
        "trace": run_dir / "trace.json",
        "creature": run_dir / "creature.json",
        "task": run_dir / "task.json",
        "lineage": run_dir / "lineage.json",
        "archive": run_dir / "archive.json",
        "design_trace": run_dir / "agent.json",
    }
    return {name: str(path) for name, path in names.items() if path.exists() or name == "run_dir"}


def _reproduce_command(run_dir: Path, backend: str, seed: int | None) -> str | None:
    creature_path, task_path = run_dir / "creature.json", run_dir / "task.json"
    if not creature_path.exists() or not task_path.exists():
        return None
    parts = ["creature-lab", "run", str(creature_path), "--task", str(task_path)]
    parts += ["--backend", backend]
    if seed is not None:
        parts += ["--seed", str(seed)]
    return " ".join(parts)


def build_report(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> dict[str, Any]:
    """Build a serializable report for a saved run directory or trace."""
    run_dir, creature, task, trace = _load_artifacts(path, runs_dir)
    summary = summarize_episode(trace, task)
    meta = trace.meta

    diagnosis: dict[str, Any]
    if creature is not None:
        from creature_lab.diagnosis import diagnose

        result = diagnose(trace, creature, task)
        diagnosis = {
            "patterns": result.patterns,
            "suggestions": result.suggestions,
            "metrics": result.metrics,
        }
    else:
        diagnosis = {"patterns": [], "suggestions": [], "metrics": {}}

    improvement = _lineage_summary(run_dir) or _agent_summary(run_dir)
    creature_hash = spec_hash(creature) if creature is not None else None
    task_hash = spec_hash(task) if task is not None else None
    creature_hash = creature_hash or (meta.creature_hash if meta else None)
    task_hash = task_hash or (meta.task_hash if meta else None)
    seed = meta.seed if meta else None

    return {
        "run_id": trace.run_id,
        "run_dir": str(run_dir),
        "creature": {
            "name": trace.creature_name,
            "hash": creature_hash,
            "parts": len(creature.parts) if creature is not None else None,
            "joints": len(creature.joints) if creature is not None else None,
            "motors": len(creature.motors) if creature is not None else None,
        },
        "task": {
            "name": trace.task_name,
            "hash": task_hash,
        },
        "backend": {
            "name": trace.backend,
            "version": meta.backend_version if meta else None,
        },
        "score": trace.score,
        "summary": summary.model_dump(),
        "warnings": summary.warnings,
        "diagnosis": diagnosis,
        "improvement": improvement,
        "reproducibility": {
            "schema_version": meta.schema_version if meta else None,
            "lab_version": meta.lab_version if meta else None,
            "timestep": meta.timestep if meta else None,
            "seed": seed,
            "creature_hash": creature_hash,
            "task_hash": task_hash,
            "backend": trace.backend,
            "backend_version": meta.backend_version if meta else None,
            "command": _reproduce_command(run_dir, trace.backend, seed),
        },
        "artifacts": _artifact_paths(run_dir),
    }


def build_report_bundle(
    path: Path, runs_dir: Path = DEFAULT_RUNS_DIR
) -> tuple[dict[str, Any], EpisodeTrace, CreatureSpec | None]:
    """Report dict plus the raw trace/creature, for renderers that need series data (HTML)."""
    _, creature, _, trace = _load_artifacts(path, runs_dir)
    return build_report(path, runs_dir=runs_dir), trace, creature


def build_comparison(report_a: dict[str, Any], report_b: dict[str, Any]) -> dict[str, Any]:
    """Score and signal deltas (``b - a``) between two reports built by ``build_report``."""
    summary_a, summary_b = report_a["summary"], report_b["summary"]
    signals: dict[str, dict[str, float]] = {}
    for key in ("net_displacement", "forward_displacement", "total_joint_motion"):
        value_a, value_b = summary_a.get(key), summary_b.get(key)
        if value_a is not None and value_b is not None:
            signals[key] = {"a": value_a, "b": value_b, "delta": value_b - value_a}
    return {
        "run_a": report_a["run_id"],
        "run_b": report_b["run_id"],
        "score_a": report_a["score"],
        "score_b": report_b["score"],
        "score_delta": report_b["score"] - report_a["score"],
        "signals": signals,
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def report_to_markdown(report: dict[str, Any]) -> str:
    """Render a report dictionary as concise Markdown."""
    creature = report["creature"]
    task = report["task"]
    backend = report["backend"]
    summary = report["summary"]
    diagnosis = report["diagnosis"]
    lines = [
        f"# Creature Lab Run Report: {report['run_id']}",
        "",
        f"- Creature: {creature['name']} ({_format_value(creature['hash'])})",
        f"- Task: {task['name']} ({_format_value(task['hash'])})",
        f"- Backend: {backend['name']} ({_format_value(backend['version'])})",
        f"- Score: {_format_value(report['score'])}",
        f"- Frames: {summary['frame_count']} over {_format_value(summary['duration'])} s",
        "",
        "## Score Breakdown",
    ]

    component_scores = summary.get("component_scores") or {}
    if component_scores:
        for name, value in component_scores.items():
            lines.append(f"- {name}: {_format_value(value)}")
    else:
        lines.append("- No component score metadata recorded.")

    lines.extend(
        [
            "",
            "## Signals",
            f"- Net displacement: {_format_value(summary['net_displacement'])}",
            f"- Forward displacement: {_format_value(summary['forward_displacement'])}",
            f"- Target progress: {_format_value(summary.get('target_progress'))}",
            f"- Joint motion: {_format_value(summary['total_joint_motion'])}",
            f"- Fell: {_format_value(summary.get('fell'))}",
            "",
            "## Diagnostics",
        ]
    )
    patterns = diagnosis.get("patterns") or []
    suggestions = diagnosis.get("suggestions") or []
    if patterns:
        for index, pattern in enumerate(patterns):
            suggestion = suggestions[index] if index < len(suggestions) else ""
            suffix = f" - {suggestion}" if suggestion else ""
            lines.append(f"- {pattern}{suffix}")
    else:
        lines.append("- No failure patterns detected.")

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)

    improvement = report.get("improvement")
    if improvement:
        lines.extend(["", "## Improvement"])
        if improvement["kind"] == "evolve":
            lines.append(
                "- Evolve: "
                f"{improvement.get('strategy')} strategy, "
                f"{improvement.get('attempts')} attempt(s), "
                f"best score {_format_value(improvement.get('best_score'))}."
            )
        else:
            lines.append(
                "- Ask: "
                f"{improvement.get('attempts')} attempt(s), "
                f"{improvement.get('accepted')} accepted edit(s), "
                f"{improvement.get('invalid')} invalid proposal(s)."
            )
            if improvement.get("goal"):
                lines.append(f"- Goal: {improvement['goal']}")

    repro = report.get("reproducibility") or {}
    lines.extend(
        [
            "",
            "## Reproducibility",
            f"- Schema/lab version: {_format_value(repro.get('schema_version'))} / "
            f"{_format_value(repro.get('lab_version'))}",
            f"- Timestep: {_format_value(repro.get('timestep'))}",
            f"- Seed: {_format_value(repro.get('seed'))}",
            f"- Creature hash: {_format_value(repro.get('creature_hash'))}",
            f"- Task hash: {_format_value(repro.get('task_hash'))}",
        ]
    )
    if repro.get("command"):
        lines.extend(["- Reproduce:", f"  ```\n  {repro['command']}\n  ```"])

    lines.extend(["", "## Artifacts"])
    for name, value in report["artifacts"].items():
        lines.append(f"- {name}: `{value}`")
    lines.append("")
    return "\n".join(lines)
