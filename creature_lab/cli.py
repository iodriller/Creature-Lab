"""Command-line interface for Creature Lab.

Only the commands needed today are implemented. The viewer/replay commands
described in ``docs/MVP_PLAN.md`` will be added as their backends land.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console

from creature_lab import VERSION
from creature_lab.controllers.sinusoid import sinusoid_targets
from creature_lab.schema import CreatureSpec, TaskSpec

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
) -> None:
    """Run a short PyBullet episode and print the final score."""
    try:
        from creature_lab.backends.pybullet_backend import PyBulletBackend
    except ImportError as exc:
        console.print(
            "[red]error:[/red] pybullet is not installed. Install it with `uv sync --extra sim`."
        )
        raise typer.Exit(code=2) from exc

    creature = _load_spec(creature_path, CreatureSpec)
    task_spec = _load_spec(task, TaskSpec)

    backend = PyBulletBackend(gui=gui)
    try:
        backend.build(creature, task_spec)
        steps = int(task_spec.duration / task_spec.timestep)
        frame = None
        for step_index in range(steps):
            t = step_index * task_spec.timestep
            backend.apply_motor_targets(sinusoid_targets(creature, t))
            frame = backend.step(task_spec.timestep)
    finally:
        backend.close()

    if frame is None:
        console.print("[yellow]warning:[/yellow] task duration too short to run any steps")
        raise typer.Exit(code=1)

    console.print(
        f"[green]done[/green] {creature.name!r} on {task_spec.name!r}: "
        f"score={frame.score:.4f} ({steps} step(s))"
    )


if __name__ == "__main__":
    app()
