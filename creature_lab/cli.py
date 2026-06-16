"""Command-line interface for Creature Lab.

Only the commands needed today are implemented. The simulation/viewer commands
described in ``docs/MVP_PLAN.md`` will be added as their backends land.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from creature_lab import VERSION
from creature_lab.schema import CreatureSpec

app = typer.Typer(help="Minimal, visual, backend-agnostic creature simulation lab.")
console = Console()


@app.command()
def version() -> None:
    """Print the Creature Lab version."""
    console.print(f"creature-lab {VERSION}")


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to a CreatureSpec JSON file.")],
) -> None:
    """Validate a creature JSON file against the schema."""
    if not path.exists():
        console.print(f"[red]error:[/red] file not found: {path}")
        raise typer.Exit(code=2)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]invalid JSON[/red] in {path}: {exc}")
        raise typer.Exit(code=1) from exc

    try:
        creature = CreatureSpec.model_validate(data)
    except ValidationError as exc:
        console.print(f"[red]invalid creature[/red] in {path}:")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "(root)"
            console.print(f"  [yellow]{location}[/yellow]: {error['msg']}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]valid[/green] creature {creature.name!r}: "
        f"{len(creature.parts)} part(s), {len(creature.joints)} joint(s), "
        f"{len(creature.motors)} motor(s)"
    )


if __name__ == "__main__":
    app()
