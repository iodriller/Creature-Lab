"""Command-line interface for Creature Lab."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.table import Table

from creature_lab import VERSION
from creature_lab.controllers.sinusoid import sinusoid_targets
from creature_lab.evolve import hill_climb
from creature_lab.runs import DEFAULT_RUNS_DIR, new_run_id, resolve_trace_path, save_trace
from creature_lab.schema import CreatureSpec, EpisodeTrace, FrameState, TaskSpec

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


def _simulate(creature: CreatureSpec, task: TaskSpec, *, gui: bool = False) -> EpisodeTrace:
    """Run one PyBullet episode and return its trace (without saving)."""
    try:
        from creature_lab.backends.pybullet_backend import PyBulletBackend
    except ImportError as exc:
        console.print(
            "[red]error:[/red] pybullet is not installed. Install it with `uv sync --extra sim`."
        )
        raise typer.Exit(code=2) from exc

    backend = PyBulletBackend(gui=gui)
    try:
        backend.build(creature, task)
        steps = int(task.duration / task.timestep)
        frames: list[FrameState] = []
        for step_index in range(steps):
            t = step_index * task.timestep
            backend.apply_motor_targets(sinusoid_targets(creature, t))
            frames.append(backend.step(task.timestep))
    finally:
        backend.close()

    if not frames:
        console.print("[yellow]warning:[/yellow] task duration too short to run any steps")
        raise typer.Exit(code=1)

    return EpisodeTrace(
        run_id=new_run_id(),
        creature_name=creature.name,
        task_name=task.name,
        backend="pybullet",
        score=frames[-1].score,
        frames=frames,
    )


@app.command()
def version() -> None:
    """Print the Creature Lab version."""
    console.print(f"creature-lab {VERSION}")


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
) -> None:
    """Validate a creature JSON file against the schema."""
    creature = _load_spec(path, CreatureSpec)
    console.print(
        f"[green]valid[/green] creature {creature.name!r}: "
        f"{len(creature.parts)} part(s), {len(creature.joints)} joint(s), "
        f"{len(creature.motors)} motor(s)"
    )


@app.command()
def run(
    creature_path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
    task: Annotated[Path, typer.Option(help="Path to a TaskSpec JSON file.")],
    gui: Annotated[bool, typer.Option(help="Open a PyBullet GUI window.")] = False,
    runs_dir: Annotated[
        Path, typer.Option(help="Directory to save the episode trace under.")
    ] = DEFAULT_RUNS_DIR,
) -> None:
    """Run a short PyBullet episode, save its trace, and print the final score."""
    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)

    trace = _simulate(creature, task_spec, gui=gui)
    trace_path = save_trace(trace, runs_dir=runs_dir)

    console.print(
        f"[green]done[/green] {creature.name!r} on {task_spec.name!r}: "
        f"score={trace.score:.4f} ({len(trace.frames)} step(s)) -> {trace_path}"
    )


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
    rng = random.Random(seed)

    result = hill_climb(
        creature,
        lambda candidate: _simulate(candidate, task_spec).score,
        attempts=attempts,
        rng=rng,
    )

    best_trace = _simulate(result.best, task_spec)
    trace_path = save_trace(best_trace, runs_dir=runs_dir)
    run_dir = trace_path.parent
    (run_dir / "best.json").write_text(result.best.model_dump_json(indent=2))

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
def replay(
    path: Annotated[Path, typer.Argument(help="Path to a trace.json file or run directory.")],
) -> None:
    """Print a summary of a saved episode trace."""
    trace = _load_spec(resolve_trace_path(path), EpisodeTrace)
    duration = trace.frames[-1].t - trace.frames[0].t
    console.print(
        f"[green]trace[/green] {trace.run_id!r}: {trace.creature_name!r} on "
        f"{trace.task_name!r} via {trace.backend!r} — {len(trace.frames)} frame(s), "
        f"{duration:.2f}s, score={trace.score:.4f}"
    )


if __name__ == "__main__":
    app()
