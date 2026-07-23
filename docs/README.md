# Documentation

Start with the launcher, then use the topic docs when you need more detail.

## First Run

```bash
python scripts/start.py
```

On Windows PowerShell:

```powershell
.\scripts\start.ps1
```

The launcher installs starter extras, runs `creature-lab doctor`, and opens the interactive build
editor. Use `--mode demo` for looping read-only playback.

## Manual Path

```bash
uv sync --inexact --extra sim --extra viz
uv run creature-lab demo --open-browser
```

Use the manual path when you want to control dependency extras or call the CLI directly.

## Reading Order

1. [Getting Started](GETTING_STARTED.md) - first run, zoo, improvement, and troubleshooting.
2. [Build Editor](BUILD_EDITOR.md) - browser setup screen for creating CreatureSpec JSON.
3. [Concepts](CONCEPTS.md) - the mental model behind specs, tasks, traces, and backends.
4. [CLI Reference](CLI_REFERENCE.md) - commands grouped by workflow.
5. [Creature Spec](CREATURE_SPEC.md) and [Task Spec](TASK_SPEC.md) - JSON authoring.
6. [Run Artifacts](RUN_ARTIFACTS.md) - saved traces, reports, and reproducibility.
7. [Zoo](ZOO.md) - packaged creatures, tasks, baselines, benchmarks, and gallery.
8. [Failure Lab](FAILURE_LAB.md) - three reproducible education exercises.
9. [Grand Plan](GRAND_PLAN.md) - the single active roadmap: what Creature Lab is and where it's going.
10. [Roadmap](ROADMAP.md) - the durable guard rails (points to the Grand Plan).
11. [Releasing](RELEASING.md) - verified distributions, clean-install smoke, and publication gates.

Historical plans and audits live in [archive](archive/).
