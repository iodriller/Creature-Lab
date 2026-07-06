# Getting Started

This guide is the shortest path from a fresh clone to a moving creature.

## 1. Install The Demo Dependencies

```bash
uv sync --extra sim --extra viz
```

The `sim` extra installs PyBullet. The `viz` extra installs the browser viewer.

## 2. Run The Demo

```bash
uv run creature-lab demo --no-hold
```

The default demo runs the built-in quadruped on the built-in `crawl_forward` task. It opens a
local Viser browser viewer, saves a run under `runs/`, and exits after one pass.

Use a different built-in creature:

```bash
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
uv run creature-lab doctor
```

`doctor` reports installed extras, optional providers, and whether the built-in example can
simulate.
