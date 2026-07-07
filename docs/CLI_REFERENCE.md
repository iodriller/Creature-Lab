# CLI Reference

Use `uv run creature-lab --help` for exact options. This page groups commands by workflow.

## Start Here

```bash
uv run creature-lab demo --no-hold
uv run creature-lab zoo list
uv run creature-lab zoo run quadruped
uv run creature-lab report latest
```

- `demo` runs a built-in creature in the live browser viewer.
- `zoo list` shows packaged creatures and tasks.
- `zoo run <name>` runs a packaged creature and saves a trace.
- `report latest` summarizes the last saved run.

## Run And Improve

```bash
uv run creature-lab run examples/quadruped.json --task examples/crawl_forward.json
uv run creature-lab evolve examples/quadruped.json --task examples/crawl_forward.json --attempts 20
uv run creature-lab ask "make it crawl farther" examples/tripod.json --task examples/crawl_forward.json --offline
```

- `run` simulates one creature/task pair.
- `evolve` searches for a better body/controller.
- `ask` applies validated design edits, offline or with an optional LLM provider.

## Replay And Debug

```bash
uv run creature-lab replay runs/<run-id>
uv run creature-lab inspect runs/<run-id>
uv run creature-lab diagnose runs/<run-id>
uv run creature-lab report latest --out report.md
uv run creature-lab report latest --html report.html
uv run creature-lab view runs/<run-id>
uv run creature-lab export latest --gif creature.gif
```

- `replay` prints a short trace summary.
- `inspect` prints metadata, hashes, score components, contacts, warnings, and run metrics.
- `diagnose` explains likely failure patterns and suggested edits.
- `report` writes a Markdown or JSON summary with score, diagnostics, artifacts, and a
  reproducibility block. `--html` also writes a self-contained HTML run card (score
  breakdown, signal sparklines, root-path plot, and an optional embedded GIF preview).
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
uv run creature-lab compare runs/<a> runs/<b> --html diff.html
uv run creature-lab plot runs/<run-id> --metric joint_energy --out energy.png
uv run creature-lab bench --zoo --task crawl_forward --attempts 3 --out runs/bench.json
uv run creature-lab schema creature --out docs/schemas/creature.schema.json
uv run creature-lab gallery build --zoo --out docs/assets/zoo --no-media
uv run creature-lab lineage runs/<evolve-run-id>
uv run creature-lab archive show runs/<map-elites-run-id> --html archive.html
uv run creature-lab archive export runs/<map-elites-run-id> --cell 3,2 --out elite.json
uv run creature-lab robustness runs/<run-id> --trials 10
uv run creature-lab sim2sim runs/<run-id>
uv run creature-lab doctor
uv run creature-lab version
```

These commands are useful for authoring, interoperability, run comparison, diagnostics, and
environment checks. They are intentionally outside the first-run path.

- `archive show` (only useful after `evolve --strategy map_elites`) prints the filled
  behaviour cells as a table, or `--html` renders a scored heatmap; add `--task` to embed a
  replay GIF per cell. `archive export --cell row,col` pulls one elite out as a standalone,
  editable `CreatureSpec` JSON.
- `robustness` re-simulates a creature/task under small seeded mass/friction perturbations
  and reports the score mean/std/fail-rate — a wide spread means the gait only works for the
  exact recorded parameters. Add `--save` to write a reportable run (`report <dir>` then
  shows a Robustness section).
- `sim2sim` runs the same creature/task on both PyBullet and MuJoCo and reports the score gap
  and mean root-position divergence — a concrete measure of the "specs are portable, physics
  is backend-dependent" contract. Add `--save` for a reportable run.

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
