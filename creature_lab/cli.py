"""Command-line interface for Creature Lab."""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any, TypeVar
from xml.etree.ElementTree import ParseError as ET_PARSE_ERROR

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.table import Table

from creature_lab import VERSION
from creature_lab.controllers.sinusoid import sinusoid_targets
from creature_lab.diagnostics import collect_doctor_checks, summarize_episode
from creature_lab.evolve import (
    Evaluation,
    cmaes,
    genetic,
    hill_climb,
    make_mutator,
    map_elites,
)
from creature_lab.hashing import spec_hash
from creature_lab.library import (
    builtin_creature_names,
    creature_by_name,
    default_creature,
    default_task,
)
from creature_lab.runs import (
    DEFAULT_RUNS_DIR,
    new_run_id,
    resolve_run_path,
    resolve_trace_path,
    save_run,
)
from creature_lab.schema import CreatureSpec, EpisodeTrace, FrameState, TaskSpec, TraceMeta
from creature_lab.schema.trace import TRACE_SCHEMA_VERSION
from creature_lab.validation import EpisodeInputError, validate_episode_inputs

app = typer.Typer(
    help=(
        "Tiny local lab for designing, running, diagnosing, and improving "
        "modular robot-creatures from JSON."
    )
)
console = Console()

ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_spec(path: Path, model: type[ModelT]) -> ModelT:
    if not path.exists():
        console.print(f"[red]error:[/red] file not found: {path}")
        raise typer.Exit(code=2)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]invalid JSON[/red] in {path}: {exc}")
        raise typer.Exit(code=1) from exc

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        console.print(f"[red]invalid {model.__name__}[/red] in {path}:")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "(root)"
            console.print(f"  [yellow]{location}[/yellow]: {error['msg']}")
        raise typer.Exit(code=1) from exc


def _write_stdout(text: str) -> None:
    console.file.write(text)
    if not text.endswith("\n"):
        console.file.write("\n")


def _print_json(data: Any) -> None:
    _write_stdout(json.dumps(data, indent=2, sort_keys=True))


def _resolve_run_path(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    try:
        return resolve_run_path(path, runs_dir=runs_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


def _resolve_trace_path(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    try:
        return resolve_trace_path(path, runs_dir=runs_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


def _run_dir_for(path: Path, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    resolved = _resolve_run_path(path, runs_dir=runs_dir)
    return resolved if resolved.is_dir() else resolved.parent


def _load_creature_for_trace(
    path: Path, creature_path: Path | None, runs_dir: Path = DEFAULT_RUNS_DIR
) -> CreatureSpec:
    """Load the creature for a trace, defaulting to creature.json in the run directory."""
    if creature_path is None:
        run_dir = _run_dir_for(path, runs_dir=runs_dir)
        creature_path = run_dir / "creature.json"
    return _load_spec(creature_path, CreatureSpec)


def _load_task_for_trace(
    path: Path, task_path: Path | None, runs_dir: Path = DEFAULT_RUNS_DIR
) -> TaskSpec | None:
    """Load the task for a trace: explicit --task, else task.json in the run dir if present."""
    if task_path is not None:
        return _load_spec(task_path, TaskSpec)
    run_dir = _run_dir_for(path, runs_dir=runs_dir)
    candidate = run_dir / "task.json"
    return _load_spec(candidate, TaskSpec) if candidate.exists() else None


def _saved_run_payload(
    creature: CreatureSpec, task: TaskSpec, trace: EpisodeTrace, run_dir: Path
) -> dict[str, Any]:
    return {
        "run_id": trace.run_id,
        "run_dir": str(run_dir),
        "creature": creature.name,
        "task": task.name,
        "backend": trace.backend,
        "score": trace.score,
        "frames": len(trace.frames),
    }


def _check_inputs(creature: CreatureSpec, task: TaskSpec) -> None:
    """Cross-validate inputs before simulating: warn on soft issues, abort on hard errors."""
    try:
        warnings = validate_episode_inputs(creature, task)
    except EpisodeInputError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")


def _require_backend(name: str = "pybullet") -> tuple[type, str]:
    """Resolve a backend class + version string by name, exiting if it is missing."""
    if name == "pybullet":
        try:
            from creature_lab.backends.pybullet_backend import PyBulletBackend, backend_version
        except ImportError as exc:
            console.print(
                "[red]error:[/red] pybullet is not installed. Install it with "
                "`uv sync --extra sim`."
            )
            raise typer.Exit(code=2) from exc
        return PyBulletBackend, backend_version()
    if name == "mujoco":
        try:
            from creature_lab.backends.mujoco_backend import MuJoCoBackend, backend_version
        except ImportError as exc:
            console.print(
                "[red]error:[/red] mujoco is not installed. Install it with "
                "`uv sync --extra mujoco`."
            )
            raise typer.Exit(code=2) from exc
        return MuJoCoBackend, backend_version()
    console.print(f"[red]error:[/red] unknown backend {name!r} (choose: pybullet, mujoco)")
    raise typer.Exit(code=2)


def _build_meta(
    creature: CreatureSpec,
    task: TaskSpec,
    *,
    seed: int | None,
    score_summary: dict[str, float],
    backend_version: str,
) -> TraceMeta:
    """Build the provenance/reproducibility metadata stamped into a trace."""
    return TraceMeta(
        schema_version=TRACE_SCHEMA_VERSION,
        lab_version=VERSION,
        backend_version=backend_version,
        timestep=task.timestep,
        seed=seed,
        creature_hash=spec_hash(creature),
        task_hash=spec_hash(task),
        score_summary=score_summary,
        warnings=validate_episode_inputs(creature, task),
    )


def _trace_from_frames(
    creature: CreatureSpec,
    task: TaskSpec,
    frames: list[FrameState],
    *,
    meta: TraceMeta,
    backend: str = "pybullet",
) -> EpisodeTrace:
    return EpisodeTrace(
        run_id=new_run_id(),
        creature_name=creature.name,
        task_name=task.name,
        backend=backend,
        score=frames[-1].score,
        frames=frames,
        meta=meta,
    )


def _make_controller(name: str, creature: CreatureSpec):
    """Build an open-loop controller callable ``(t, prev_frame) -> targets`` by name."""
    if name == "sinusoid":
        return lambda t, prev=None: sinusoid_targets(creature, t)
    if name == "cpg":
        from creature_lab.controllers.cpg import CPGController

        return CPGController(creature)
    raise typer.BadParameter(f"unknown controller {name!r} (choose: sinusoid, cpg)")


def _simulate(
    creature: CreatureSpec,
    task: TaskSpec,
    *,
    gui: bool = False,
    seed: int | None = None,
    controller: str = "sinusoid",
    backend: str = "pybullet",
) -> EpisodeTrace:
    """Run one physics episode on the named backend and return its trace (unsaved)."""
    policy = _make_controller(controller, creature)
    backend_cls, version = _require_backend(backend)
    sim = backend_cls(gui=gui)
    try:
        sim.build(creature, task)
        frames: list[FrameState] = []
        prev: FrameState | None = None
        for step_index in range(task.step_count()):
            t = step_index * task.timestep
            sim.apply_motor_targets(policy(t, prev))
            prev = sim.step(task.timestep)
            frames.append(prev)
        score_summary = sim.score_summary()
    finally:
        sim.close()

    if not frames:
        console.print("[yellow]warning:[/yellow] task duration too short to run any steps")
        raise typer.Exit(code=1)

    meta = _build_meta(
        creature, task, seed=seed, score_summary=score_summary, backend_version=version
    )
    return _trace_from_frames(creature, task, frames, meta=meta, backend=backend)


@app.command(rich_help_panel="Advanced")
def version() -> None:
    """Print the Creature Lab version."""
    console.print(f"creature-lab {VERSION}")


_STATUS_STYLE = {"ok": "green", "missing": "red", "warn": "yellow", "info": "cyan"}


@app.command(rich_help_panel="Advanced")
def doctor() -> None:
    """Check the environment: optional extras, providers, and that examples run."""
    table = Table(title=f"creature-lab {VERSION} doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")
    for check in collect_doctor_checks():
        style = _STATUS_STYLE.get(check.status, "white")
        table.add_row(check.name, f"[{style}]{check.status}[/{style}]", check.detail)
    console.print(table)


@app.command(rich_help_panel="Advanced")
def validate(
    path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[
        Path | None,
        typer.Option(help="Also validate a TaskSpec and cross-check it against the creature."),
    ] = None,
) -> None:
    """Validate a creature JSON file (and optionally a task) against the schema."""
    creature = _load_spec(path, CreatureSpec)
    console.print(
        f"[green]valid[/green] creature {creature.name!r}: "
        f"{len(creature.parts)} part(s), {len(creature.joints)} joint(s), "
        f"{len(creature.motors)} motor(s)"
    )
    if task is not None:
        task_spec = _load_spec(task, TaskSpec)
        console.print(f"[green]valid[/green] task {task_spec.name!r}")
        _check_inputs(creature, task_spec)
        console.print("[green]ok[/green] creature and task are compatible")


@app.command(rich_help_panel="Run And Improve")
def run(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[Path, typer.Option(help="Path to a TaskSpec JSON file.")],
    controller: Annotated[
        str, typer.Option(help="Open-loop controller: 'sinusoid' or 'cpg'.")
    ] = "sinusoid",
    backend: Annotated[
        str, typer.Option(help="Physics backend: 'pybullet' or 'mujoco'.")
    ] = "pybullet",
    gui: Annotated[bool, typer.Option(help="Open a PyBullet GUI window.")] = False,
    seed: Annotated[int | None, typer.Option(help="Seed recorded in the trace metadata.")] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the episode trace under.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable run metadata.")
    ] = False,
) -> None:
    """Run a short physics episode, save its trace, and print the final score."""
    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)
    _check_inputs(creature, task_spec)

    trace = _simulate(
        creature, task_spec, gui=gui, seed=seed, controller=controller, backend=backend
    )
    run_dir = save_run(creature, trace, runs_dir=runs_dir, task=task_spec)
    if json_output:
        _print_json(_saved_run_payload(creature, task_spec, trace, run_dir))
        return

    console.print(
        f"[green]done[/green] {creature.name!r} on {task_spec.name!r}: "
        f"score={trace.score:.4f} ({len(trace.frames)} step(s)) -> {run_dir}"
    )


@app.command(rich_help_panel="Start Here")
def demo(
    creature_path: Annotated[
        Path | None, typer.Argument(help="CreatureSpec JSON (overrides --creature).")
    ] = None,
    creature_name: Annotated[
        str | None,
        typer.Option(
            "--creature",
            help="Built-in creature to demo (quadruped, worm, tripod). Default: quadruped.",
        ),
    ] = None,
    task: Annotated[
        Path | None, typer.Option(help="TaskSpec JSON (default: built-in crawl_forward).")
    ] = None,
    fps: Annotated[float, typer.Option(help="Playback frames per second.")] = 60.0,
    port: Annotated[int, typer.Option(help="Port for the Viser server.")] = 8080,
    save: Annotated[bool, typer.Option(help="Save the streamed episode as a trace.")] = True,
    hold: Annotated[
        bool, typer.Option(help="Keep serving and looping after the run (Ctrl+C to stop).")
    ] = True,
    seed: Annotated[int | None, typer.Option(help="Seed recorded in the trace metadata.")] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the episode trace under.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Simulate a creature and stream its motion live to a Viser browser viewer.

    With no arguments it uses the built-in quadruped and crawl-forward task, so it
    works from an installed package without the repository's examples/ directory.
    Use ``--creature worm`` (or ``tripod``) to pick a different built-in, or pass a
    CreatureSpec JSON path to load your own.
    """
    if creature_path:
        creature = _load_spec(creature_path, CreatureSpec)
    elif creature_name:
        try:
            creature = creature_by_name(creature_name)
        except KeyError as exc:
            available = ", ".join(builtin_creature_names())
            console.print(
                f"[red]error:[/red] unknown creature {creature_name!r}; choose one of: {available}"
            )
            raise typer.Exit(code=2) from exc
    else:
        creature = default_creature()
    task_spec = _load_spec(task, TaskSpec) if task else default_task()
    _check_inputs(creature, task_spec)

    backend_cls, version = _require_backend()
    try:
        from creature_lab.viewers.viser_viewer import stream_frames
    except ImportError as exc:
        console.print(
            "[red]error:[/red] viser is not installed. Install it with `uv sync --extra viz`."
        )
        raise typer.Exit(code=2) from exc

    backend_holder: list = []

    def live_frames() -> Iterator[FrameState]:
        backend = backend_cls()
        backend_holder.append(backend)
        try:
            backend.build(creature, task_spec)
            for step_index in range(task_spec.step_count()):
                targets = sinusoid_targets(creature, step_index * task_spec.timestep)
                backend.apply_motor_targets(targets)
                yield backend.step(task_spec.timestep)
        finally:
            backend.close()

    console.print(
        f"[green]serving[/green] {creature.name!r} on http://localhost:{port} (Ctrl+C to stop)"
    )
    frames = stream_frames(creature, live_frames(), task=task_spec, fps=fps, port=port, hold=hold)

    if save and frames:
        summary = backend_holder[0].score_summary() if backend_holder else {}
        meta = _build_meta(
            creature, task_spec, seed=seed, score_summary=summary, backend_version=version
        )
        trace = _trace_from_frames(creature, task_spec, frames, meta=meta)
        run_dir = save_run(creature, trace, runs_dir=runs_dir, task=task_spec)
        console.print(f"[green]saved[/green] {len(frames)} frame(s) -> {run_dir}")


def _gait_symmetry(trace: EpisodeTrace) -> float:
    """Right-side share of ground contacts in [0, 1] (0.5 = symmetric / no l/r parts)."""
    left = right = 0
    for frame in trace.frames:
        for part_id in {c.part_id for c in frame.contacts}:
            if part_id.endswith("_l"):
                left += 1
            elif part_id.endswith("_r"):
                right += 1
    total = left + right
    return 0.5 if total == 0 else right / total


def _feature_evaluate(creature: CreatureSpec, task: TaskSpec) -> Evaluation:
    """Evaluate a creature, returning its score plus a (forward, symmetry) descriptor."""
    trace = _simulate(creature, task)
    summary = summarize_episode(trace, task)
    return Evaluation(trace.score, (summary.forward_displacement, _gait_symmetry(trace)))


@app.command(rich_help_panel="Run And Improve")
def evolve(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[Path, typer.Option(help="Path to a TaskSpec JSON file.")],
    strategy: Annotated[
        str, typer.Option(help="hill_climb, genetic, map_elites, or cmaes.")
    ] = "hill_climb",
    mutate_opt: Annotated[
        str, typer.Option("--mutate", help="What to mutate: body, controller, or body,controller.")
    ] = "body,controller",
    attempts: Annotated[int, typer.Option(help="Number of candidate evaluations.")] = 10,
    seed: Annotated[int, typer.Option(help="Random seed for reproducible evolution.")] = 0,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the best creature and trace under.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable best-run metadata.")
    ] = False,
) -> None:
    """Evolve a creature from a seed, saving the best one, a lineage, and any archive."""
    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)
    _check_inputs(creature, task_spec)
    rng = random.Random(seed)

    if strategy not in {"hill_climb", "genetic", "map_elites", "cmaes"}:
        console.print(
            "[red]error:[/red] --strategy must be hill_climb, genetic, map_elites, or cmaes"
        )
        raise typer.Exit(code=2)

    targets = {part.strip() for part in mutate_opt.split(",") if part.strip()}
    if not targets <= {"body", "controller"}:
        console.print("[red]error:[/red] --mutate must be 'body', 'controller', or both")
        raise typer.Exit(code=2)
    mutate_fn = make_mutator("body" in targets, "controller" in targets)

    def evaluate(candidate: CreatureSpec) -> float:
        return _simulate(candidate, task_spec).score

    try:
        if strategy == "hill_climb":
            result = hill_climb(creature, evaluate, attempts=attempts, rng=rng, mutate_fn=mutate_fn)
        elif strategy == "genetic":
            result = genetic(creature, evaluate, attempts=attempts, rng=rng, mutate_fn=mutate_fn)
        elif strategy == "map_elites":
            result = map_elites(
                creature,
                lambda c: _feature_evaluate(c, task_spec),
                attempts=attempts,
                rng=rng,
                mutate_fn=mutate_fn,
            )
        else:  # cmaes
            result = cmaes(creature, evaluate, attempts=attempts, rng=rng)
    except (RuntimeError, ValueError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    best_trace = _simulate(result.best, task_spec, seed=seed)
    run_dir = save_run(result.best, best_trace, runs_dir=runs_dir, task=task_spec)

    # Persist the lineage (and MAP-Elites archive) so `lineage` can render them later.
    lineage = [
        {
            "index": a.index,
            "parent": a.parent,
            "generation": a.generation,
            "score": a.score,
            "accepted": a.accepted,
            "cell": list(a.cell) if a.cell is not None else None,
        }
        for a in result.history
    ]
    (run_dir / "lineage.json").write_text(
        json.dumps({"strategy": strategy, "nodes": lineage}, indent=2)
    )
    if result.archive:
        archive = {
            f"{cell[0]},{cell[1]}": {"score": entry["score"], "features": list(entry["features"])}
            for cell, entry in result.archive.items()
        }
        (run_dir / "archive.json").write_text(json.dumps(archive, indent=2))

    if json_output:
        payload = _saved_run_payload(result.best, task_spec, best_trace, run_dir)
        payload["strategy"] = strategy
        payload["attempts"] = attempts
        payload["seed_score"] = result.history[0].score
        payload["best_score"] = result.best_score
        _print_json(payload)
        return

    table = Table(title=f"{creature.name!r} evolve ({strategy}, {attempts} attempts, seed {seed})")
    table.add_column("attempt", justify="right")
    table.add_column("score", justify="right")
    table.add_column("result")
    for attempt in result.history:
        label = "seed" if attempt.index == 0 else ("kept" if attempt.accepted else "rejected")
        style = "green" if attempt.accepted else "dim"
        table.add_row(str(attempt.index), f"{attempt.score:.4f}", f"[{style}]{label}[/{style}]")
    console.print(table)
    if result.archive:
        console.print(f"[cyan]archive[/cyan]: {len(result.archive)} behaviour cell(s) filled")
    console.print(
        f"[green]best[/green] score={result.best_score:.4f} "
        f"(seed score={result.history[0].score:.4f}) -> {run_dir}"
    )


@app.command(rich_help_panel="Run And Improve")
def bench(
    zoo: Annotated[bool, typer.Option("--zoo", help="Benchmark packaged zoo creatures.")] = False,
    task: Annotated[
        str | None,
        typer.Option(help="Only run zoo creatures that include this task name."),
    ] = None,
    attempts: Annotated[int, typer.Option(help="Runs per creature/task pair.")] = 1,
    seed: Annotated[int, typer.Option(help="Base seed recorded in each trace.")] = 0,
    backend: Annotated[
        str, typer.Option(help="Physics backend: 'pybullet' or 'mujoco'.")
    ] = "pybullet",
    controller: Annotated[
        str, typer.Option(help="Open-loop controller: 'sinusoid' or 'cpg'.")
    ] = "sinusoid",
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save benchmark runs under.")
    ] = DEFAULT_RUNS_DIR,
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Write benchmark JSON here.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print benchmark JSON instead of a table.")
    ] = False,
) -> None:
    """Run a reproducible local benchmark over the packaged zoo."""
    if not zoo:
        console.print("[red]error:[/red] use --zoo to benchmark packaged creatures")
        raise typer.Exit(code=2)
    if attempts < 1:
        console.print("[red]error:[/red] --attempts must be at least 1")
        raise typer.Exit(code=2)

    from creature_lab.zoo import (
        default_task_name,
        list_zoo_creatures,
        zoo_baseline,
        zoo_creature,
        zoo_tasks,
    )

    pairs: list[tuple[str, str]] = []
    for name in list_zoo_creatures():
        task_name = task or default_task_name(name)
        if task_name in zoo_tasks(name):
            pairs.append((name, task_name))
    if not pairs:
        console.print(f"[red]error:[/red] no zoo creatures include task {task!r}")
        raise typer.Exit(code=1)

    results: list[dict[str, Any]] = []
    for name, task_name in pairs:
        creature, task_spec = zoo_creature(name, task_name)
        _check_inputs(creature, task_spec)
        scores: list[float] = []
        run_dirs: list[str] = []
        for index in range(attempts):
            trace = _simulate(
                creature,
                task_spec,
                seed=seed + index,
                controller=controller,
                backend=backend,
            )
            run_dir = save_run(creature, trace, runs_dir=runs_dir, task=task_spec)
            scores.append(trace.score)
            run_dirs.append(str(run_dir))

        baseline = zoo_baseline(name, task_name)
        baseline_score = baseline.get("best_score") if baseline else None
        threshold = None
        passed = None
        best_score = max(scores)
        if isinstance(baseline_score, int | float):
            threshold = baseline_score * 0.9 if baseline_score > 0 else baseline_score
            passed = best_score >= threshold
        results.append(
            {
                "creature": name,
                "task": task_name,
                "backend": backend,
                "controller": controller,
                "seed": seed,
                "attempts": attempts,
                "scores": scores,
                "best_score": best_score,
                "mean_score": sum(scores) / len(scores),
                "baseline_score": baseline_score,
                "pass_threshold": threshold,
                "passed": passed,
                "runs": run_dirs,
            }
        )

    payload = {
        "kind": "zoo_benchmark",
        "backend": backend,
        "controller": controller,
        "seed": seed,
        "attempts": attempts,
        "results": results,
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2))

    if json_output:
        _print_json(payload)
        return

    table = Table(title=f"zoo benchmark ({len(results)} pair(s), {attempts} attempt(s))")
    table.add_column("creature")
    table.add_column("task")
    table.add_column("best", justify="right")
    table.add_column("baseline", justify="right")
    table.add_column("pass")
    for result in results:
        passed_value = result["passed"]
        if passed_value is None:
            status = "-"
        else:
            status = "[green]yes[/green]" if passed_value else "[red]no[/red]"
        baseline_value = result["baseline_score"]
        table.add_row(
            result["creature"],
            result["task"],
            f"{result['best_score']:.4f}",
            "-" if baseline_value is None else f"{baseline_value:.4f}",
            status,
        )
    console.print(table)
    if out is not None:
        console.print(f"[green]wrote[/green] benchmark JSON -> {out}")


@app.command(rich_help_panel="Advanced")
def lineage(
    path: Annotated[
        Path, typer.Argument(help="Path to an evolve run directory (or lineage.json).")
    ],
    best: Annotated[
        int | None, typer.Option(help="Instead of the tree, list the top-N scoring candidates.")
    ] = None,
) -> None:
    """Print the ancestral lineage of an evolve run as a tree (or its top candidates)."""
    lineage_path = path / "lineage.json" if path.is_dir() else path
    if not lineage_path.exists():
        console.print(f"[red]error:[/red] no lineage.json at {lineage_path}")
        raise typer.Exit(code=2)
    data = json.loads(lineage_path.read_text())
    nodes = data["nodes"]

    if best is not None:
        ranked = sorted(nodes, key=lambda n: n["score"], reverse=True)[: max(0, best)]
        table = Table(title=f"top {best} candidates ({data.get('strategy', '?')})")
        table.add_column("rank", justify="right")
        table.add_column("attempt", justify="right")
        table.add_column("score", justify="right")
        for rank, node in enumerate(ranked, start=1):
            table.add_row(str(rank), str(node["index"]), f"{node['score']:.4f}")
        console.print(table)
        return

    children: dict[int | None, list[dict]] = {}
    for node in nodes:
        children.setdefault(node["parent"], []).append(node)

    console.print(f"[bold]lineage[/bold] ({data.get('strategy', '?')}) - {len(nodes)} candidate(s)")

    def render(parent: int | None, depth: int) -> None:
        for node in sorted(children.get(parent, []), key=lambda n: n["index"]):
            mark = "[green]*[/green]" if node["accepted"] else " "
            indent = "  " * depth
            console.print(f"{indent}{mark} #{node['index']} score={node['score']:.4f}")
            render(node["index"], depth + 1)

    render(None, 0)


@app.command(rich_help_panel="Run And Improve")
def ask(
    goal: Annotated[str, typer.Argument(help="Plain-language design goal.")],
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[Path, typer.Option(help="Path to a TaskSpec JSON file.")],
    attempts: Annotated[int, typer.Option(help="Number of design attempts.")] = 5,
    offline: Annotated[
        bool, typer.Option(help="Use the built-in no-LLM tool policy instead of a model.")
    ] = False,
    model: Annotated[str, typer.Option(help="LiteLLM model id (online mode).")] = "gpt-4o-mini",
    seed: Annotated[int, typer.Option(help="Seed for the offline policy.")] = 0,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the best creature and traces under.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable best-run metadata.")
    ] = False,
) -> None:
    """Iteratively improve a creature toward a goal using validated design tools.

    Online mode asks an LLM (via LiteLLM, the `llm` extra) for each tool call;
    `--offline` uses a deterministic no-provider policy so it runs anywhere.
    """
    from creature_lab.agents.loop import Policy, design_loop

    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)
    _check_inputs(creature, task_spec)

    policy: Policy
    if offline:
        from creature_lab.agents.baseline import RandomToolPolicy

        policy = RandomToolPolicy(seed)
    else:
        try:
            import litellm  # noqa: F401

            from creature_lab.agents.llm import LLMPolicy
        except ImportError as exc:
            console.print(
                "[red]error:[/red] litellm is not installed. Use --offline or "
                "`uv sync --extra llm`."
            )
            raise typer.Exit(code=2) from exc
        policy = LLMPolicy(model=model)

    result = design_loop(
        creature,
        lambda candidate: _simulate(candidate, task_spec).score,
        policy,
        attempts=attempts,
        goal=goal,
        task_name=task_spec.name,
    )

    best_trace = _simulate(result.best, task_spec, seed=seed)
    run_dir = save_run(result.best, best_trace, runs_dir=runs_dir, task=task_spec)
    (run_dir / "agent.json").write_text(result.trace.model_dump_json(indent=2))
    if json_output:
        payload = _saved_run_payload(result.best, task_spec, best_trace, run_dir)
        payload["goal"] = goal
        payload["attempts"] = attempts
        payload["best_score"] = result.best_score
        payload["accepted_edits"] = len(
            [step for step in result.trace.steps if step.accepted and step.attempt > 0]
        )
        _print_json(payload)
        return

    table = Table(title=f"ask {goal!r} ({attempts} attempts)")
    table.add_column("attempt", justify="right")
    table.add_column("action")
    table.add_column("score", justify="right")
    table.add_column("result")
    for step in result.trace.steps:
        if step.attempt == 0:
            label, style = "seed", "green"
        elif not step.valid:
            label, style = "invalid", "red"
        elif step.accepted:
            label, style = "kept", "green"
        else:
            label, style = "rejected", "dim"
        score = f"{step.score:.4f}" if step.score is not None else "-"
        table.add_row(str(step.attempt), step.action, score, f"[{style}]{label}[/{style}]")
    console.print(table)

    console.print(
        f"[green]best[/green] score={result.best_score:.4f} "
        f"(seed score={result.trace.steps[0].score:.4f}) -> {run_dir}"
    )


@app.command(rich_help_panel="Replay And Debug")
def replay(
    path: Annotated[Path, typer.Argument(help="Path to a trace.json file or run directory.")],
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Print a summary of a saved episode trace."""
    trace = _load_spec(_resolve_trace_path(path, runs_dir), EpisodeTrace)
    duration = trace.frames[-1].t  # total simulated time (final frame timestamp)
    console.print(
        f"[green]trace[/green] {trace.run_id!r}: {trace.creature_name!r} on "
        f"{trace.task_name!r} via {trace.backend!r} — {len(trace.frames)} frame(s), "
        f"{duration:.2f}s, score={trace.score:.4f}"
    )


@app.command(rich_help_panel="Replay And Debug")
def inspect(
    path: Annotated[Path, typer.Argument(help="Path to a run directory (or trace.json).")],
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable inspection data.")
    ] = False,
) -> None:
    """Print a detailed diagnostic summary of a saved run."""
    trace = _load_spec(_resolve_trace_path(path, runs_dir), EpisodeTrace)
    task = _load_task_for_trace(path, None, runs_dir)
    summary = summarize_episode(trace, task)
    meta = trace.meta
    if json_output:
        _print_json(
            {
                "run_id": trace.run_id,
                "creature": trace.creature_name,
                "task": trace.task_name,
                "backend": trace.backend,
                "score": trace.score,
                "summary": summary.model_dump(),
                "meta": meta.model_dump() if meta else None,
            }
        )
        return

    table = Table(title=f"run {trace.run_id!r}: {trace.creature_name!r} on {trace.task_name!r}")
    table.add_column("field")
    table.add_column("value")

    def row(field: str, value: object) -> None:
        table.add_row(field, str(value))

    if meta is not None:
        row("schema / lab version", f"{meta.schema_version} / {meta.lab_version}")
        row("backend", meta.backend_version or "-")
        row("creature hash", meta.creature_hash or "-")
        row("task hash", meta.task_hash or "-")
        row("timestep / seed", f"{meta.timestep} / {meta.seed}")
    else:
        row("metadata", "[yellow]none (legacy trace)[/yellow]")
    row("frames / duration (s)", f"{summary.frame_count} / {summary.duration:.2f}")
    row("final score", f"{summary.final_score:.4f}")
    if summary.component_scores:
        breakdown = ", ".join(f"{k}={v:.4f}" for k, v in summary.component_scores.items())
        row("score breakdown", breakdown)
    row(
        "net displacement / forward Δx",
        f"{summary.net_displacement:.4f} / {summary.forward_displacement:.4f}",
    )
    if summary.target_progress is not None:
        row("target progress", f"{summary.target_progress:.4f}")
    row("joint motion (Σ|Δrad|)", f"{summary.total_joint_motion:.4f}")
    row("fell", "-" if summary.fell is None else summary.fell)
    row("damage events", ", ".join(summary.damage_events) or "none")
    row(
        "contacts by part",
        ", ".join(f"{part}={count}" for part, count in summary.contacts_by_part.items()) or "none",
    )
    console.print(table)
    for warning in summary.warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")


@app.command(rich_help_panel="Replay And Debug")
def report(
    path: Annotated[Path, typer.Argument(help="Path to a run directory, trace.json, or `latest`.")],
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Write the report here instead of stdout.")
    ] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Render the report as JSON instead of Markdown.")
    ] = False,
) -> None:
    """Generate a concise run report with score, diagnostics, and artifact paths."""
    from creature_lab.reports import build_report, report_to_markdown

    try:
        data = build_report(path, runs_dir=runs_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    rendered = (
        json.dumps(data, indent=2, sort_keys=True) if json_output else report_to_markdown(data)
    )
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered)
        console.print(f"[green]wrote[/green] report -> {out}")
        return
    _write_stdout(rendered)


@app.command(rich_help_panel="Replay And Debug")
def diagnose(
    path: Annotated[Path, typer.Argument(help="Path to a run directory (or trace.json).")],
    creature_path: Annotated[
        Path | None,
        typer.Option(
            "--creature", help="CreatureSpec JSON (defaults to creature.json in the run dir)."
        ),
    ] = None,
    task: Annotated[
        Path | None, typer.Option(help="TaskSpec JSON (defaults to task.json in the run dir).")
    ] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable diagnosis data.")
    ] = False,
) -> None:
    """Explain *why* a creature failed: locomotion signals + matched failure patterns."""
    from creature_lab.diagnosis import diagnose as run_diagnosis

    trace = _load_spec(_resolve_trace_path(path, runs_dir), EpisodeTrace)
    creature = _load_creature_for_trace(path, creature_path, runs_dir)
    task_spec = _load_task_for_trace(path, task, runs_dir)
    result = run_diagnosis(trace, creature, task_spec)
    if json_output:
        _print_json(
            {
                "run_id": trace.run_id,
                "creature": trace.creature_name,
                "task": trace.task_name,
                "metrics": result.metrics,
                "patterns": result.patterns,
                "explanations": result.explanations,
                "suggestions": result.suggestions,
            }
        )
        return

    table = Table(title=f"diagnosis: {trace.run_id!r} ({trace.creature_name!r})")
    table.add_column("signal")
    table.add_column("value", justify="right")
    m = result.metrics
    table.add_row("forward displacement (m)", f"{m['forward_displacement']:+.3f}")
    table.add_row("lateral displacement (m)", f"{m['lateral_displacement']:.3f}")
    table.add_row("net horizontal travel (m)", f"{m['net_displacement']:.3f}")
    table.add_row("total joint motion (rad)", f"{m['total_joint_motion']:.1f}")
    fall = m["fall_time"]
    table.add_row("fall", "no" if fall < 0 else f"yes at t={fall:.2f}s")
    table.add_row("CoM height std (m)", f"{m['com_height_std']:.3f}")
    table.add_row("frames in ground contact", f"{m['contact_frames_fraction']:.0%}")
    console.print(table)

    if not result.patterns:
        console.print("[green]no failure patterns detected[/green] - this run looks healthy.")
        return

    console.print("\n[bold]Root-cause patterns detected:[/bold]")
    for pattern, explanation in zip(result.patterns, result.explanations, strict=True):
        console.print(f"  [yellow]! {pattern}[/yellow] - {explanation}")
    console.print("\n[bold]Suggested edits:[/bold]")
    for index, suggestion in enumerate(result.suggestions, start=1):
        console.print(f"  {index}. {suggestion}")


@app.command(rich_help_panel="Replay And Debug")
def view(
    path: Annotated[Path, typer.Argument(help="Path to a trace.json file or run directory.")],
    creature_path: Annotated[
        Path | None,
        typer.Option(
            "--creature", help="CreatureSpec JSON (defaults to creature.json in the run dir)."
        ),
    ] = None,
    task: Annotated[
        Path | None, typer.Option(help="Optional TaskSpec JSON to draw the target marker.")
    ] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
    fps: Annotated[float, typer.Option(help="Playback frames per second.")] = 30.0,
    port: Annotated[int, typer.Option(help="Port for the Viser server.")] = 8080,
    debug: Annotated[bool, typer.Option(help="Overlay CoM/root trails and a fall marker.")] = False,
) -> None:
    """Replay a saved trace in a Viser browser viewer (renders poses, no physics)."""
    trace = _load_spec(_resolve_trace_path(path, runs_dir), EpisodeTrace)
    creature = _load_creature_for_trace(path, creature_path, runs_dir)
    task_spec = _load_task_for_trace(path, task, runs_dir)

    try:
        from creature_lab.viewers.viser_viewer import play_trace
    except ImportError as exc:
        console.print(
            "[red]error:[/red] viser is not installed. Install it with `uv sync --extra viz`."
        )
        raise typer.Exit(code=2) from exc

    console.print(
        f"[green]serving[/green] {trace.run_id!r} on http://localhost:{port} (Ctrl+C to stop)"
    )
    play_trace(creature, trace, task=task_spec, fps=fps, port=port, debug=debug)


@app.command(rich_help_panel="Advanced")
def compare(
    run_a: Annotated[Path, typer.Argument(help="First run directory (or trace.json).")],
    run_b: Annotated[Path, typer.Argument(help="Second run directory (or trace.json).")],
    gap: Annotated[float, typer.Option(help="Sideways spacing between the two creatures.")] = 1.0,
    fps: Annotated[float, typer.Option(help="Playback frames per second.")] = 30.0,
    port: Annotated[int, typer.Option(help="Port for the Viser server.")] = 8080,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving bare run ids or `latest`.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Replay two saved runs side by side in one Viser scene."""
    trace_a = _load_spec(_resolve_trace_path(run_a, runs_dir), EpisodeTrace)
    trace_b = _load_spec(_resolve_trace_path(run_b, runs_dir), EpisodeTrace)
    creature_a = _load_creature_for_trace(run_a, None, runs_dir)
    creature_b = _load_creature_for_trace(run_b, None, runs_dir)

    try:
        from creature_lab.viewers.viser_viewer import compare_traces
    except ImportError as exc:
        console.print(
            "[red]error:[/red] viser is not installed. Install it with `uv sync --extra viz`."
        )
        raise typer.Exit(code=2) from exc

    console.print(
        f"[green]serving[/green] {trace_a.run_id!r} vs {trace_b.run_id!r} "
        f"on http://localhost:{port} (Ctrl+C to stop)"
    )
    compare_traces(
        creature_a,
        trace_a,
        creature_b,
        trace_b,
        task_a=_load_task_for_trace(run_a, None, runs_dir),
        task_b=_load_task_for_trace(run_b, None, runs_dir),
        gap=gap,
        fps=fps,
        port=port,
    )


@app.command(rich_help_panel="Advanced")
def plot(
    path: Annotated[Path, typer.Argument(help="Path to a run directory (or trace.json).")],
    metric: Annotated[
        str, typer.Option(help="Metric: joint_energy, score, com_height, forward_x.")
    ] = "joint_energy",
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Save a PNG here (else open a window).")
    ] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Plot a per-frame metric for a saved run."""
    trace = _load_spec(_resolve_trace_path(path, runs_dir), EpisodeTrace)
    creature = _load_creature_for_trace(path, None, runs_dir)

    try:
        from creature_lab.viewers.plotting import plot_metric
    except ImportError as exc:
        console.print(
            "[red]error:[/red] matplotlib is not installed. Install it with `uv sync --extra viz`."
        )
        raise typer.Exit(code=2) from exc

    try:
        result = plot_metric(creature, trace, metric, out=out)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if result is not None:
        console.print(f"[green]saved[/green] {metric} plot -> {result}")


@app.command(rich_help_panel="Replay And Debug")
def export(
    path: Annotated[Path, typer.Argument(help="Path to a trace.json file or run directory.")],
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Output .gif or .mp4 path.")
    ] = None,
    gif: Annotated[
        Path | None, typer.Option("--gif", help="Output GIF path (alias for --out).")
    ] = None,
    creature_path: Annotated[
        Path | None,
        typer.Option(
            "--creature", help="CreatureSpec JSON (defaults to creature.json in the run dir)."
        ),
    ] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory used when resolving the `latest` alias.")
    ] = DEFAULT_RUNS_DIR,
    fps: Annotated[float, typer.Option(help="Frames per second in the output.")] = 30.0,
    width: Annotated[int, typer.Option(help="Render width in pixels.")] = 640,
    height: Annotated[int, typer.Option(help="Render height in pixels.")] = 480,
) -> None:
    """Render a saved trace to a shareable GIF or MP4 (replays poses, no physics)."""
    out_path = gif or out
    if out_path is None:
        console.print("[red]error:[/red] provide --out or --gif")
        raise typer.Exit(code=2)
    trace = _load_spec(_resolve_trace_path(path, runs_dir), EpisodeTrace)
    creature = _load_creature_for_trace(path, creature_path, runs_dir)

    try:
        from creature_lab.backends.pybullet_backend import render_trace
    except ImportError as exc:
        console.print(
            "[red]error:[/red] pybullet is not installed. Install it with `uv sync --extra sim`."
        )
        raise typer.Exit(code=2) from exc

    try:
        from creature_lab.viewers.video_exporter import write_animation
    except ImportError as exc:
        console.print(
            "[red]error:[/red] imageio is not installed. Install it with `uv sync --extra export`."
        )
        raise typer.Exit(code=2) from exc

    frames = render_trace(creature, trace, width=width, height=height)
    saved_path = write_animation(frames, out_path, fps=fps)
    console.print(f"[green]exported[/green] {len(frames)} frame(s) -> {saved_path}")


def _write_creature(creature: CreatureSpec, out: Path) -> None:
    """Serialize a creature to JSON and report part/joint/motor counts."""
    out.write_text(creature.model_dump_json(indent=2, exclude_none=True))
    console.print(
        f"[green]wrote[/green] {creature.name!r} -> {out} "
        f"({len(creature.parts)} part(s), {len(creature.joints)} joint(s), "
        f"{len(creature.motors)} motor(s))"
    )


schema_app = typer.Typer(help="Export Creature Lab JSON Schemas.")
app.add_typer(schema_app, name="schema", rich_help_panel="Advanced")


def _write_schema(model: type[BaseModel], out: Path | None) -> None:
    rendered = json.dumps(model.model_json_schema(), indent=2, sort_keys=True)
    if out is None:
        _write_stdout(rendered)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered)
    console.print(f"[green]wrote[/green] {model.__name__} schema -> {out}")


@schema_app.command("creature")
def schema_creature(
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write schema JSON here.")] = None,
) -> None:
    """Export the CreatureSpec JSON Schema."""
    _write_schema(CreatureSpec, out)


@schema_app.command("task")
def schema_task(
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write schema JSON here.")] = None,
) -> None:
    """Export the TaskSpec JSON Schema."""
    _write_schema(TaskSpec, out)


@schema_app.command("trace")
def schema_trace(
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write schema JSON here.")] = None,
) -> None:
    """Export the EpisodeTrace JSON Schema."""
    _write_schema(EpisodeTrace, out)


gallery_app = typer.Typer(help="Build static zoo gallery files.")
app.add_typer(gallery_app, name="gallery", rich_help_panel="Start Here")


def _gallery_failure_note(name: str, task_name: str) -> str:
    if "humanoid" in name:
        return "Balance and early falls are the first things to inspect."
    if "damaged" in name or "recover" in task_name:
        return "Compare pre-damage and post-damage movement in the report."
    if task_name == "reach_target":
        return "Check target progress and wasted joint motion."
    return "Check forward displacement, contact balance, and motor limits."


def _gallery_card(
    name: str, task_name: str, baseline: dict[str, Any] | None, gif: str | None
) -> str:
    expected = baseline.get("best_score") if baseline else None
    lines = [
        f"# {name}",
        "",
        f"- Default task: `{task_name}`",
        f"- Expected score: {'-' if expected is None else f'{expected:.4f}'}",
        f"- Common failure mode: {_gallery_failure_note(name, task_name)}",
        f"- Run: `uv run creature-lab zoo run {name}`",
    ]
    if gif is not None:
        lines.append(f"- GIF: `{gif}`")
    lines.append("")
    return "\n".join(lines)


@gallery_app.command("build")
def gallery_build(
    zoo: Annotated[
        bool, typer.Option("--zoo", help="Build cards for packaged zoo creatures.")
    ] = False,
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Output directory for gallery files.")
    ] = Path("docs/assets/zoo"),
    media: Annotated[
        bool, typer.Option("--media/--no-media", help="Also render one GIF per zoo creature.")
    ] = True,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save gallery render runs under.")
    ] = DEFAULT_RUNS_DIR,
    width: Annotated[int, typer.Option(help="GIF render width in pixels.")] = 320,
    height: Annotated[int, typer.Option(help="GIF render height in pixels.")] = 240,
) -> None:
    """Build local static cards, and optionally GIFs, for the Creature Zoo."""
    if not zoo:
        console.print("[red]error:[/red] use --zoo to build the packaged zoo gallery")
        raise typer.Exit(code=2)

    from creature_lab.zoo import default_task_name, list_zoo_creatures, zoo_baseline, zoo_creature

    out.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for name in list_zoo_creatures():
        task_name = default_task_name(name)
        creature, task_spec = zoo_creature(name, task_name)
        baseline = zoo_baseline(name, task_name)
        gif_name: str | None = None
        if media:
            try:
                from creature_lab.backends.pybullet_backend import render_trace
                from creature_lab.viewers.video_exporter import write_animation
            except ImportError as exc:
                console.print(
                    "[red]error:[/red] gallery media needs `uv sync --extra sim --extra export`."
                )
                raise typer.Exit(code=2) from exc
            trace = _simulate(creature, task_spec)
            save_run(creature, trace, runs_dir=runs_dir, task=task_spec)
            gif_path = out / f"{name}.gif"
            write_animation(render_trace(creature, trace, width=width, height=height), gif_path)
            gif_name = gif_path.name
        card = _gallery_card(name, task_name, baseline, gif_name)
        card_path = out / f"{name}.md"
        card_path.write_text(card)
        cards.append(f"- [{name}]({card_path.name})")

    (out / "index.md").write_text("# Creature Zoo Gallery\n\n" + "\n".join(cards) + "\n")
    console.print(f"[green]built[/green] {len(cards)} zoo gallery card(s) -> {out}")


scaffold_app = typer.Typer(help="Generate creatures procedurally (no URDF/MJCF by hand).")
app.add_typer(scaffold_app, name="scaffold", rich_help_panel="Advanced")


@scaffold_app.command("worm")
def scaffold_worm(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CreatureSpec path.")],
    segments: Annotated[int, typer.Option(help="Number of body segments.")] = 5,
) -> None:
    """Scaffold a multi-segment worm that crawls forward."""
    from creature_lab.scaffold import generate_worm

    _write_creature(generate_worm(segments), out)


@scaffold_app.command("quadruped")
def scaffold_quadruped(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CreatureSpec path.")],
    leg_length: Annotated[float, typer.Option(help="Leg capsule length (m).")] = 0.22,
) -> None:
    """Scaffold a four-legged walker."""
    from creature_lab.scaffold import generate_quadruped

    _write_creature(generate_quadruped(leg_length=leg_length), out)


@scaffold_app.command("hexapod")
def scaffold_hexapod(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CreatureSpec path.")],
) -> None:
    """Scaffold a six-legged walker."""
    from creature_lab.scaffold import generate_hexapod

    _write_creature(generate_hexapod(), out)


@scaffold_app.command("humanoid")
def scaffold_humanoid(
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CreatureSpec path.")],
    dof: Annotated[int, typer.Option(help="Actuated hinges: 8 or 12.")] = 8,
    height: Annotated[float, typer.Option(help="Approximate standing height (m).")] = 1.6,
) -> None:
    """Scaffold a bipedal humanoid skeleton."""
    from creature_lab.scaffold import generate_humanoid

    if dof not in (8, 12):
        console.print("[red]error:[/red] --dof must be 8 or 12")
        raise typer.Exit(code=2)
    _write_creature(generate_humanoid(height=height, dof=dof), out)  # type: ignore[arg-type]


@app.command("mirror-limb", rich_help_panel="Advanced")
def mirror_limb_cmd(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CreatureSpec path.")],
    side: Annotated[
        str, typer.Option(help="Side to mirror from: 'left' (Y>0) or 'right' (Y<0).")
    ] = "left",
) -> None:
    """Mirror a creature's limbs from one side to the other for symmetry."""
    from creature_lab.scaffold import mirror_limb

    creature = _load_spec(creature_path, CreatureSpec)
    try:
        mirrored = mirror_limb(creature, side=side)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _write_creature(mirrored, out)


zoo_app = typer.Typer(help="Browse and run the curated Creature Zoo.")
app.add_typer(zoo_app, name="zoo", rich_help_panel="Start Here")


@zoo_app.command("list")
def zoo_list(
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable zoo metadata.")
    ] = False,
) -> None:
    """List the built-in zoo creatures and their tasks."""
    from creature_lab.zoo import default_task_name, list_zoo_creatures, zoo_tasks

    if json_output:
        _print_json(
            [
                {
                    "creature": name,
                    "tasks": zoo_tasks(name),
                    "default_task": default_task_name(name),
                }
                for name in list_zoo_creatures()
            ]
        )
        return

    table = Table(title="Creature Zoo")
    table.add_column("creature")
    table.add_column("tasks")
    table.add_column("default task")
    for name in list_zoo_creatures():
        tasks = zoo_tasks(name)
        table.add_row(name, ", ".join(tasks), default_task_name(name))
    console.print(table)


@zoo_app.command("run")
def zoo_run(
    name: Annotated[str, typer.Argument(help="Zoo creature name (see `zoo list`).")],
    task: Annotated[
        str | None, typer.Option(help="Task name for this creature (default: its crawl task).")
    ] = None,
    gui: Annotated[bool, typer.Option(help="Open a PyBullet GUI window.")] = False,
    seed: Annotated[int | None, typer.Option(help="Seed recorded in the trace metadata.")] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the episode trace under.")
    ] = DEFAULT_RUNS_DIR,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print machine-readable run metadata.")
    ] = False,
) -> None:
    """Run a zoo creature on one of its tasks and save the trace."""
    from creature_lab.zoo import zoo_creature

    try:
        creature, task_spec = zoo_creature(name, task)
    except KeyError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    _check_inputs(creature, task_spec)
    trace = _simulate(creature, task_spec, gui=gui, seed=seed)
    run_dir = save_run(creature, trace, runs_dir=runs_dir, task=task_spec)
    if json_output:
        _print_json(_saved_run_payload(creature, task_spec, trace, run_dir))
        return
    console.print(
        f"[green]done[/green] {creature.name!r} on {task_spec.name!r}: "
        f"score={trace.score:.4f} ({len(trace.frames)} step(s)) -> {run_dir}"
    )


@zoo_app.command("validate-all")
def zoo_validate_all() -> None:
    """Cross-validate every creature/task pair in the zoo."""
    from creature_lab.validation import EpisodeInputError
    from creature_lab.zoo import validate_all

    try:
        pairs = validate_all()
    except EpisodeInputError as exc:
        console.print(f"[red]error:[/red] zoo has an invalid creature/task: {exc}")
        raise typer.Exit(code=1) from exc
    for creature_name, task_name in pairs:
        console.print(f"[green]ok[/green] {creature_name} / {task_name}")
    console.print(f"[green]valid[/green] all {len(pairs)} zoo creature/task pair(s)")


@app.command("export-urdf", rich_help_panel="Advanced")
def export_urdf_cmd(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output .urdf path.")],
) -> None:
    """Export a creature to a URDF robot description (capsules become cylinders)."""
    from creature_lab.export import export_urdf

    creature = _load_spec(creature_path, CreatureSpec)
    out.write_text(export_urdf(creature))
    console.print(f"[green]exported[/green] {creature.name!r} URDF -> {out}")


@app.command("export-mjcf", rich_help_panel="Advanced")
def export_mjcf_cmd(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output .xml path.")],
) -> None:
    """Export a creature to a MuJoCo MJCF model."""
    from creature_lab.export import export_mjcf

    creature = _load_spec(creature_path, CreatureSpec)
    out.write_text(export_mjcf(creature))
    console.print(f"[green]exported[/green] {creature.name!r} MJCF -> {out}")


@app.command("import-urdf", rich_help_panel="Advanced")
def import_urdf_cmd(
    urdf_path: Annotated[Path, typer.Argument(help="Path to a .urdf file.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output CreatureSpec path.")],
) -> None:
    """Best-effort import of a simple URDF into a CreatureSpec (skips meshes/sensors)."""
    from creature_lab.export import import_urdf

    if not urdf_path.exists():
        console.print(f"[red]error:[/red] file not found: {urdf_path}")
        raise typer.Exit(code=2)
    try:
        result = import_urdf(urdf_path.read_text())
    except (ValueError, ET_PARSE_ERROR) as exc:
        console.print(f"[red]error:[/red] could not import URDF: {exc}")
        raise typer.Exit(code=1) from exc

    out.write_text(result.creature.model_dump_json(indent=2, exclude_none=True))
    console.print(
        f"[green]imported[/green] {result.creature.name!r} -> {out} "
        f"({len(result.creature.parts)} part(s), {len(result.creature.joints)} joint(s))"
    )
    for warning in result.warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")


if __name__ == "__main__":
    app()
