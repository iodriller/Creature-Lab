# Creature Zoo

The Creature Zoo is the packaged gallery of ready-to-run designs. Each entry ships with a
`creature.json`, one or more tasks, and optional baseline score metadata.

```bash
uv run creature-lab zoo list
uv run creature-lab zoo run quadruped
uv run creature-lab report latest
```

## Packaged Creatures

| Creature | Default Task | Useful For | Common Failure To Inspect |
| --- | --- | --- | --- |
| `quadruped` | `crawl_forward` | First demo, locomotion, challenge pack | Contact balance, motor limits, sideways drift |
| `worm` | `crawl_forward` | Simple body wave locomotion | High joint effort with low forward displacement |
| `tripod` | `crawl_forward` | Diagnosis examples | Wiggle-in-place behavior and weak thrust |
| `hexapod` | `crawl_forward` | More contacts and gait comparison | Single-limb drag or inefficient phases |
| `damaged_quadruped` | `recover` | Damage/recovery runs | Loss of contact after the damage event |
| `humanoid_minimal` | `walk` | Biped balance and push recovery | Early falls and narrow stance |
| `humanoid_12dof` | `walk` | Higher-DOF humanoid experiments | Knee limits, arm swing, balance |

## Challenge Pack

The repo now includes a small local challenge pack using existing simulator features:

- `crawl_forward`: move along +x.
- `low_friction_crawl`: move forward with low ground friction.
- `push_recovery`: stay useful after a lateral impulse.
- `reach_target`: reduce distance to a target sphere.
- `stability_hold`: avoid falling without forward-distance reward.

List exact creature/task availability with:

```bash
uv run creature-lab zoo list
```

## Benchmarks

Run all zoo creatures that have a task:

```bash
uv run creature-lab bench --zoo --task crawl_forward --attempts 3 --seed 0 --out runs/bench.json
```

Benchmark output includes scores, best/mean score, backend, controller, seed, saved run paths,
and pass/fail status when a packaged baseline exists.

## Gallery

Build static cards:

```bash
uv run creature-lab gallery build --zoo --out docs/assets/zoo --no-media
```

Build cards plus GIFs:

```bash
uv sync --extra sim --extra export
uv run creature-lab gallery build --zoo --out docs/assets/zoo --media
```
