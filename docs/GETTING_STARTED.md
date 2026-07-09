# Getting Started

This guide is the shortest path from a fresh clone to a moving creature.

## 1. Launch The Demo

Use the launcher from the repository root:

```bash
python scripts/start.py
```

On Windows PowerShell:

```powershell
.\scripts\start.ps1
```

The launcher installs the demo dependencies, runs `doctor`, opens the browser viewer, and keeps
the creature looping until `Ctrl+C`.

What you should see:

- A terminal progress log with the viewer URL.
- A browser tab at `http://localhost:8080` or the next free port.
- A moving quadruped in the Viser scene.

For a one-pass smoke run:

```bash
python scripts/start.py --once
```

## 2. Manual Demo

```bash
uv sync --inexact --extra sim --extra viz
uv run creature-lab demo --open-browser
```

The `sim` extra installs PyBullet. The `viz` extra installs the browser viewer. The default demo
runs the built-in quadruped on the built-in `crawl_forward` task. Add `--no-hold` if you want
the command to save a trace and exit after one pass.

Use a different built-in creature:

```bash
python scripts/start.py --creature worm
uv run creature-lab demo --creature worm --no-hold
uv run creature-lab demo --creature tripod --no-hold
```

## 3. Browse The Creature Zoo

```bash
uv run creature-lab zoo list
uv run creature-lab zoo run quadruped
uv run creature-lab report latest
uv run creature-lab zoo run worm
```

Zoo creatures are packaged with the library, so these commands work from an installed wheel.
Each saved run updates `runs/latest.txt`, which lets follow-up commands accept `latest`.

## 4. Improve One Creature

Build or tune a creature visually:

```bash
uv run creature-lab build --preset humanoid
```

The build editor opens in the browser, starts from a preset, lets you tune body and motor
parameters, validates the creature/task pair, and saves a normal CreatureSpec JSON.

Then improve a saved creature with the local evolution loop:

```bash
uv run creature-lab evolve examples/quadruped.json --task examples/crawl_forward.json --attempts 20
```

`evolve` evaluates candidate edits, keeps the best creature, and saves the best run plus its
lineage under `runs/`.

For a deterministic no-provider design loop:

```bash
uv run creature-lab ask "make it crawl farther" examples/tripod.json --task examples/crawl_forward.json --offline
```

## 5. Replay Or Export A Run

```bash
uv run creature-lab view runs/<run-id>
uv run creature-lab diagnose runs/<run-id>
uv run creature-lab report latest --out report.md
```

GIF/MP4 export needs the export extra:

```bash
uv sync --extra sim --extra export
uv run creature-lab export latest --gif creature.gif
```

## Troubleshooting

Run:

```bash
python scripts/start.py --dry-run
uv run creature-lab doctor
```

`--dry-run` prints the launcher commands without running them. `doctor` reports installed extras,
optional providers, and whether the built-in example can simulate.

Common fixes:

- Browser did not open: copy the printed `http://localhost:<port>` URL into your browser.
- Port is busy: rerun with `python scripts/start.py --port 8090`.
- Dependencies failed to install: run `uv sync --inexact --extra sim --extra viz` and retry.
- You only want a quick verification run: use `python scripts/start.py --once --no-open-browser`.
