# Build Editor

The build editor is a browser-based setup screen powered by Viser. It uses the same dependency
as the replay viewer, so there is no separate web app, server framework, or frontend build step.

## Start

```bash
uv sync --inexact --extra sim --extra viz
uv run creature-lab build
```

Edit an existing creature:

```bash
uv run creature-lab build mydude.json --out mydude.json
```

Use a different preset:

```bash
uv run creature-lab build --preset humanoid
uv run creature-lab build --preset worm
```

## What You Can Do

- Start from `quadruped`, `hexapod`, `worm`, or `humanoid`.
- Tune body parameters with sliders and see the static preview update.
- Select parts by clicking them in the scene or choosing them in the panel.
- Drag the selected-part transform gizmo to move its parent joint anchor.
- Edit part mass, shape, size, radius, length, and color.
- Add or delete limbs.
- Tune individual motor amplitude, frequency, and phase.
- Choose task presets and adjust duration/friction.
- Validate the creature/task pair before physics runs.
- Save a normal `CreatureSpec` JSON.
- Click Simulate to run the existing physics pipeline and save a trace under `runs/`.

## Mental Model

The editor writes ordinary Creature Lab JSON. After saving, every existing command still works:

```bash
uv run creature-lab validate outputs/build_creature.json --task examples/crawl_forward.json
uv run creature-lab run outputs/build_creature.json --task examples/crawl_forward.json
uv run creature-lab evolve outputs/build_creature.json --task examples/crawl_forward.json
```

## Troubleshooting

- Browser did not open: copy the printed `http://localhost:<port>` URL into your browser.
- Port is busy: rerun with `--port 8090`.
- Simulate is disabled: read the Errors section in the Run folder and fix validation issues.
- Physics dependency is missing: run `uv sync --inexact --extra sim --extra viz`.
