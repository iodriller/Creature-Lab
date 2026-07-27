# Task Spec

`TaskSpec` describes the world, objective, target, and one-shot events for a run.

```bash
uv run creature-lab schema task --out docs/schemas/task.schema.json
uv run creature-lab validate examples/quadruped.json --task examples/crawl_forward.json
```

## Shape

```json
{
  "name": "crawl_forward",
  "duration": 5.0,
  "timestep": 0.016666666666666666,
  "terrain": {"type": "plane", "friction": 1.0},
  "reward": {"forward_distance": 1.0}
}
```

- `duration` is episode length in seconds.
- `timestep` is simulation step size and must not exceed `duration`.
- `terrain.friction` controls contact friction on every terrain type.
- `terrain.type` is one of:
  - `plane` (default): an infinite flat ground.
  - `slope`: a fixed incline along +x, set by `terrain.slope_angle` (radians).
  - `steps`: a staircase along +x, set by `terrain.step_height` and `terrain.step_length`.
  - `gaps`: periodic impassable gaps along +x (`terrain.gap_width`, `terrain.gap_period`),
    with a solid platform around the origin so a creature always spawns on ground.
  - `rough`: seeded per-cell noise (`terrain.roughness`, `terrain.seed`) for a reproducible
    bumpy surface.

  Non-`plane` terrain builds a deterministic heightfield (see `creature_lab/terrain.py`)
  that both the PyBullet and MuJoCo backends simulate with the same shape; exact contact
  dynamics still differ by backend, same as with creature bodies (see [Concepts](CONCEPTS.md)).
- `reward` combines forward distance, target progress, energy penalty, fall penalty, and
  survival: `forward_distance`/`target_distance` reward movement (weight x displacement/progress
  in meters), `energy_penalty` subtracts accumulated actuation effort (weight x a raw quantity
  typically in the tens-to-hundreds over a few seconds — a small-looking weight like `0.01` can
  still dominate; `0.001` is closer to a real tie-breaker), `fall_penalty` subtracts a fixed
  amount if the creature has toppled by the end of the episode, and `survival` adds a fixed
  amount if it has *not* — the positive mirror of `fall_penalty`, needed for a pure balance task
  (built only from penalties) to be able to score above 0 at all.
- `target` is optional and currently supports a sphere target.
- `damage_event` removes one part at a given time.
- `impulse_event` applies a one-step world-frame force to one part.

## Challenge Pack

The packaged zoo ships these task styles as ready-to-run `TaskSpec` examples — see
[Zoo - Challenge Pack](ZOO.md#challenge-pack) for the full, current list and terrain variants:

```bash
uv run creature-lab zoo list
uv run creature-lab bench --zoo --task crawl_forward --attempts 3 --seed 0
```

## Common Validation Failures

Bad timing:

```json
{"name": "bad", "duration": 0.1, "timestep": 0.2}
```

Target reward without a target:

```json
{"name": "bad", "duration": 1.0, "reward": {"target_distance": 1.0}}
```

Damage event after the episode ends:

```json
{"name": "bad", "duration": 1.0, "damage_event": {"time": 2.0, "part_id": "leg"}}
```

Task event targeting a missing part:

```json
{"name": "bad", "duration": 1.0, "impulse_event": {"time": 0.5, "part_id": "missing", "force": [0, 100, 0]}}
```

The schema catches shape and timing errors. `validate --task` also checks that event part ids
exist in the creature.
