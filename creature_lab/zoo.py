"""The Creature Zoo: a curated gallery of ready-to-run creatures and tasks.

Each entry lives under ``creature_lab/zoo/<name>/`` with a ``creature.json`` and a
``tasks/`` directory. The files are static (shareable, diff-able) and shipped with
the package, so ``creature-lab zoo run <name>`` works from an installed wheel.
"""

from __future__ import annotations

from pathlib import Path

from creature_lab.schema import CreatureSpec, TaskSpec

ZOO_DIR = Path(__file__).parent / "zoo"

#: Preferred default task names (first match wins) when a creature offers several.
_PREFERRED_DEFAULTS = ("crawl_forward", "walk", "balance")


def list_zoo_creatures() -> list[str]:
    """Names of all zoo creatures (directories containing a ``creature.json``)."""
    if not ZOO_DIR.is_dir():
        return []
    return sorted(
        entry.name
        for entry in ZOO_DIR.iterdir()
        if entry.is_dir() and (entry / "creature.json").exists()
    )


def _creature_dir(name: str) -> Path:
    directory = ZOO_DIR / name
    if not (directory / "creature.json").exists():
        available = ", ".join(list_zoo_creatures())
        raise KeyError(f"unknown zoo creature {name!r}; choose one of: {available}")
    return directory


def zoo_tasks(name: str) -> list[str]:
    """Task names available for a zoo creature."""
    tasks_dir = _creature_dir(name) / "tasks"
    if not tasks_dir.is_dir():
        return []
    return sorted(path.stem for path in tasks_dir.glob("*.json"))


def default_task_name(name: str) -> str:
    """The task used when ``zoo run`` is given no ``--task`` (prefers crawl_forward)."""
    tasks = zoo_tasks(name)
    if not tasks:
        raise KeyError(f"zoo creature {name!r} has no tasks")
    for preferred in _PREFERRED_DEFAULTS:
        if preferred in tasks:
            return preferred
    return tasks[0]


def zoo_creature(name: str, task: str | None = None) -> tuple[CreatureSpec, TaskSpec]:
    """Load a zoo creature and one of its tasks (its default task if unspecified)."""
    directory = _creature_dir(name)
    creature = CreatureSpec.model_validate_json((directory / "creature.json").read_text())
    task_name = task or default_task_name(name)
    task_path = directory / "tasks" / f"{task_name}.json"
    if not task_path.exists():
        available = ", ".join(zoo_tasks(name))
        raise KeyError(f"unknown task {task_name!r} for {name!r}; choose one of: {available}")
    task_spec = TaskSpec.model_validate_json(task_path.read_text())
    return creature, task_spec


def validate_all() -> list[tuple[str, str]]:
    """Cross-validate every (creature, task) pair in the zoo.

    Returns the list of validated ``(creature, task)`` name pairs. Raises if any
    creature, task, or their combination is invalid (so ``zoo validate-all`` can
    surface a broken gallery before shipping).
    """
    from creature_lab.validation import validate_episode_inputs

    checked: list[tuple[str, str]] = []
    for name in list_zoo_creatures():
        for task_name in zoo_tasks(name):
            creature, task = zoo_creature(name, task_name)
            validate_episode_inputs(creature, task)  # raises EpisodeInputError on hard errors
            checked.append((name, task_name))
    return checked
