# CLI Reference

Use `uv run creature-lab --help` for exact options. This page groups commands by workflow.

## Start Here

```bash
python scripts/start.py
uv run creature-lab demo --open-browser
uv run creature-lab build
uv run creature-lab zoo list
uv run creature-lab zoo run quadruped
uv run creature-lab report latest
```

- `demo` runs a built-in creature in the live browser viewer.
- `build` opens the browser setup screen for visual creature editing and simulation.
- `zoo list` shows packaged creatures and tasks.
- `zoo run <name>` runs a packaged creature and saves a trace.
- `report latest` summarizes the last saved run.

## Launcher Scripts

The launcher is the recommended first command from a repo checkout:

```bash
python scripts/start.py
```

Wrappers are available for common shells:

```powershell
.\scripts\start.ps1
```

```bash
bash scripts/start.sh
```

Useful options:

| Option | Purpose |
| --- | --- |
| `--once` | Run one pass, save the trace, and exit. |
| `--no-open-browser` | Print the viewer URL without opening a browser tab. |
| `--creature worm` | Run a different packaged demo creature. |
| `--creature-path path/to/creature.json` | Run a local CreatureSpec. |
| `--task path/to/task.json` | Override the default task. |
| `--port 8090` | Use a different Viser port. |
| `--full` | Install all optional extras before launching. |
| `--skip-sync` | Reuse the current environment. |
| `--dry-run` | Print commands without running them. |

## Run And Improve

```bash
uv run creature-lab build --preset humanoid
uv run creature-lab build mydude.json --out mydude.json
uv run creature-lab run examples/quadruped.json --task examples/crawl_forward.json
uv run creature-lab evolve examples/quadruped.json --task examples/crawl_forward.json --attempts 20
uv run creature-lab ask "make it crawl farther" examples/tripod.json --task examples/crawl_forward.json --offline
```

- `build` edits a CreatureSpec in a Viser browser UI, then saves JSON or simulates directly.
- `run` simulates one creature/task pair.
- `evolve` searches for a better body/controller.
- `ask` applies validated design edits, offline or with an optional LLM provider.

## Replay And Debug

```bash
uv run creature-lab replay runs/<run-id>
uv run creature-lab inspect runs/<run-id>
uv run creature-lab diagnose runs/<run-id>
uv run creature-lab report latest --out report.md
uv run creature-lab view runs/<run-id> --open-browser
uv run creature-lab export latest --gif creature.gif
```

- `replay` prints a short trace summary.
- `inspect` prints metadata, hashes, score components, contacts, warnings, and run metrics.
- `diagnose` explains likely failure patterns and suggested edits.
- `report` writes a Markdown or JSON summary with score, diagnostics, and artifact paths.
- `view` replays recorded poses in the browser viewer.
- `export` renders a recorded trace to GIF or MP4.

Most run-reading commands accept either `runs/<run-id>`, a `trace.json` path, a bare run id
under `runs/`, or `latest`.

## Advanced

```bash
uv run creature-lab scaffold quadruped --out quad.json
uv run creature-lab mirror-limb half_creature.json --side left --out symmetric.json
uv run creature-lab export-urdf quad.json --out quad.urdf
uv run creature-lab export-mjcf quad.json --out quad.xml
uv run creature-lab import-urdf robot.urdf --out robot.json
uv run creature-lab compare runs/<a> runs/<b>
uv run creature-lab plot runs/<run-id> --metric joint_energy --out energy.png
uv run creature-lab bench --zoo --task crawl_forward --attempts 3 --out runs/bench.json
uv run creature-lab schema creature --out docs/schemas/creature.schema.json
uv run creature-lab gallery build --zoo --out docs/assets/zoo --no-media
uv run creature-lab lineage runs/<evolve-run-id>
uv run creature-lab doctor
uv run creature-lab version
```

These commands are useful for authoring, interoperability, run comparison, diagnostics, and
environment checks. They are intentionally outside the first-run path.

## Machine-Readable Output

Use `--json` on `run`, `evolve`, `ask`, `inspect`, `diagnose`, `report`, `zoo list`, and
`zoo run` when another tool needs structured output instead of Rich tables.

## Optional Extras

| Extra | Enables |
| --- | --- |
| `sim` | PyBullet backend and physics rendering |
| `viz` | Viser browser viewer and plotting |
| `export` | GIF/MP4 writing |
| `evolve` | Optional CMA-ES strategy |
| `mujoco` | MuJoCo backend and MJCF loading tests |
| `llm` | Online `ask` mode through LiteLLM |
