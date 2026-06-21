"""Command-line interface for Creature Lab."""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.table import Table

from creature_lab import VERSION
from creature_lab.controllers.sinusoid import sinusoid_targets
from creature_lab.diagnostics import collect_doctor_checks, summarize_episode
from creature_lab.evolve import hill_climb
from creature_lab.hashing import spec_hash
from creature_lab.library import default_creature, default_task
from creature_lab.runs import (
    DEFAULT_RUNS_DIR,
    load_run,
    new_run_id,
    resolve_trace_path,
    save_run,
)
from creature_lab.schema import CreatureSpec, EpisodeTrace, FrameState, TaskSpec, TraceMeta
from creature_lab.schema.trace import TRACE_SCHEMA_VERSION
from creature_lab.validation import EpisodeInputError, validate_episode_inputs

app = typer.Typer(help="Minimal, visual, backend-agnostic creature simulation lab.")
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


def _load_creature_for_trace(path: Path, creature_path: Path | None) -> CreatureSpec:
    """Load the creature for a trace, defaulting to creature.json in the run directory."""
    if creature_path is None:
        run_dir = path if path.is_dir() else path.parent
        creature_path = run_dir / "creature.json"
    return _load_spec(creature_path, CreatureSpec)


def _load_task_for_trace(path: Path, task_path: Path | None) -> TaskSpec | None:
    """Load the task for a trace: explicit --task, else task.json in the run dir if present."""
    if task_path is not None:
        return _load_spec(task_path, TaskSpec)
    run_dir = path if path.is_dir() else path.parent
    candidate = run_dir / "task.json"
    return _load_spec(candidate, TaskSpec) if candidate.exists() else None


def _check_inputs(creature: CreatureSpec, task: TaskSpec) -> None:
    """Cross-validate inputs before simulating: warn on soft issues, abort on hard errors."""
    try:
        warnings = validate_episode_inputs(creature, task)
    except EpisodeInputError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")


def _require_backend() -> type:
    """Import the PyBullet backend, exiting with a friendly message if it is missing."""
    try:
        from creature_lab.backends.pybullet_backend import PyBulletBackend
    except ImportError as exc:
        console.print(
            "[red]error:[/red] pybullet is not installed. Install it with `uv sync --extra sim`."
        )
        raise typer.Exit(code=2) from exc
    return PyBulletBackend


def _build_meta(
    creature: CreatureSpec,
    task: TaskSpec,
    *,
    seed: int | None,
    score_summary: dict[str, float],
) -> TraceMeta:
    """Build the provenance/reproducibility metadata stamped into a trace."""
    from creature_lab.backends.pybullet_backend import backend_version

    return TraceMeta(
        schema_version=TRACE_SCHEMA_VERSION,
        lab_version=VERSION,
        backend_version=backend_version(),
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
) -> EpisodeTrace:
    return EpisodeTrace(
        run_id=new_run_id(),
        creature_name=creature.name,
        task_name=task.name,
        backend="pybullet",
        score=frames[-1].score,
        frames=frames,
        meta=meta,
    )


def _simulate(
    creature: CreatureSpec, task: TaskSpec, *, gui: bool = False, seed: int | None = None
) -> EpisodeTrace:
    """Run one PyBullet episode and return its trace (without saving)."""
    backend = _require_backend()(gui=gui)
    try:
        backend.build(creature, task)
        frames: list[FrameState] = []
        for step_index in range(task.step_count()):
            t = step_index * task.timestep
            backend.apply_motor_targets(sinusoid_targets(creature, t))
            frames.append(backend.step(task.timestep))
        score_summary = backend.score_summary()
    finally:
        backend.close()

    if not frames:
        console.print("[yellow]warning:[/yellow] task duration too short to run any steps")
        raise typer.Exit(code=1)

    meta = _build_meta(creature, task, seed=seed, score_summary=score_summary)
    return _trace_from_frames(creature, task, frames, meta=meta)


@app.command()
def version() -> None:
    """Print the Creature Lab version."""
    console.print(f"creature-lab {VERSION}")


_STATUS_STYLE = {"ok": "green", "missing": "red", "warn": "yellow", "info": "cyan"}


@app.command()
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


@app.command()
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


@app.command()
def run(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[Path, typer.Option(help="Path to a TaskSpec JSON file.")],
    gui: Annotated[bool, typer.Option(help="Open a PyBullet GUI window.")] = False,
    seed: Annotated[int | None, typer.Option(help="Seed recorded in the trace metadata.")] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the episode trace under.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Run a short PyBullet episode, save its trace, and print the final score."""
    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)
    _check_inputs(creature, task_spec)

    trace = _simulate(creature, task_spec, gui=gui, seed=seed)
    run_dir = save_run(creature, trace, runs_dir=runs_dir, task=task_spec)

    console.print(
        f"[green]done[/green] {creature.name!r} on {task_spec.name!r}: "
        f"score={trace.score:.4f} ({len(trace.frames)} step(s)) -> {run_dir}"
    )


@app.command()
def demo(
    creature_path: Annotated[
        Path | None, typer.Argument(help="CreatureSpec JSON (default: built-in tripod).")
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

    With no arguments it uses the built-in tripod and crawl-forward task, so it
    works from an installed package without the repository's examples/ directory.
    """
    creature = _load_spec(creature_path, CreatureSpec) if creature_path else default_creature()
    task_spec = _load_spec(task, TaskSpec) if task else default_task()
    _check_inputs(creature, task_spec)

    backend_cls = _require_backend()
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
        meta = _build_meta(creature, task_spec, seed=seed, score_summary=summary)
        trace = _trace_from_frames(creature, task_spec, frames, meta=meta)
        run_dir = save_run(creature, trace, runs_dir=runs_dir, task=task_spec)
        console.print(f"[green]saved[/green] {len(frames)} frame(s) -> {run_dir}")


@app.command()
def evolve(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[Path, typer.Option(help="Path to a TaskSpec JSON file.")],
    attempts: Annotated[int, typer.Option(help="Number of mutation attempts.")] = 10,
    seed: Annotated[int, typer.Option(help="Random seed for reproducible mutations.")] = 0,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the best creature and trace under.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Hill-climb from a seed creature, keeping the best-scoring mutation."""
    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)
    _check_inputs(creature, task_spec)
    rng = random.Random(seed)

    result = hill_climb(
        creature,
        lambda candidate: _simulate(candidate, task_spec).score,
        attempts=attempts,
        rng=rng,
    )

    best_trace = _simulate(result.best, task_spec, seed=seed)
    run_dir = save_run(result.best, best_trace, runs_dir=runs_dir, task=task_spec)

    table = Table(title=f"{creature.name!r} lineage ({attempts} attempts, seed {seed})")
    table.add_column("attempt", justify="right")
    table.add_column("score", justify="right")
    table.add_column("result")
    for attempt in result.history:
        label = "seed" if attempt.index == 0 else ("kept" if attempt.accepted else "rejected")
        style = "green" if attempt.accepted else "dim"
        table.add_row(str(attempt.index), f"{attempt.score:.4f}", f"[{style}]{label}[/{style}]")
    console.print(table)

    console.print(
        f"[green]best[/green] score={result.best_score:.4f} "
        f"(seed score={result.history[0].score:.4f}) -> {run_dir}"
    )


@app.command()
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


@app.command()
def replay(
    path: Annotated[Path, typer.Argument(help="Path to a trace.json file or run directory.")],
) -> None:
    """Print a summary of a saved episode trace."""
    trace = _load_spec(resolve_trace_path(path), EpisodeTrace)
    duration = trace.frames[-1].t  # total simulated time (final frame timestamp)
    console.print(
        f"[green]trace[/green] {trace.run_id!r}: {trace.creature_name!r} on "
        f"{trace.task_name!r} via {trace.backend!r} — {len(trace.frames)} frame(s), "
        f"{duration:.2f}s, score={trace.score:.4f}"
    )


@app.command()
def inspect(
    path: Annotated[Path, typer.Argument(help="Path to a run directory (or trace.json).")],
) -> None:
    """Print a detailed diagnostic summary of a saved run."""
    _, task, trace = load_run(path)
    summary = summarize_episode(trace, task)
    meta = trace.meta

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


@app.command()
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
    fps: Annotated[float, typer.Option(help="Playback frames per second.")] = 30.0,
    port: Annotated[int, typer.Option(help="Port for the Viser server.")] = 8080,
) -> None:
    """Replay a saved trace in a Viser browser viewer (renders poses, no physics)."""
    trace = _load_spec(resolve_trace_path(path), EpisodeTrace)
    creature = _load_creature_for_trace(path, creature_path)
    task_spec = _load_task_for_trace(path, task)

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
    play_trace(creature, trace, task=task_spec, fps=fps, port=port)


@app.command()
def export(
    path: Annotated[Path, typer.Argument(help="Path to a trace.json file or run directory.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output .gif or .mp4 path.")],
    creature_path: Annotated[
        Path | None,
        typer.Option(
            "--creature", help="CreatureSpec JSON (defaults to creature.json in the run dir)."
        ),
    ] = None,
    fps: Annotated[float, typer.Option(help="Frames per second in the output.")] = 30.0,
    width: Annotated[int, typer.Option(help="Render width in pixels.")] = 640,
    height: Annotated[int, typer.Option(help="Render height in pixels.")] = 480,
) -> None:
    """Render a saved trace to a shareable GIF or MP4 (replays poses, no physics)."""
    trace = _load_spec(resolve_trace_path(path), EpisodeTrace)
    creature = _load_creature_for_trace(path, creature_path)

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
    out_path = write_animation(frames, out, fps=fps)
    console.print(f"[green]exported[/green] {len(frames)} frame(s) -> {out_path}")


if __name__ == "__main__":
    app()
