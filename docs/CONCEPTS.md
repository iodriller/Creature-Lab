# Concepts

Creature Lab is built around a small loop:

```text
design -> run -> trace -> diagnose -> improve -> replay/export
```

## CreatureSpec

`CreatureSpec` is the JSON source of truth for a creature. It describes body parts, primitive
shapes, masses, colors, joints, joint limits, and motor settings. Users should not need to write
URDF or MJCF by hand for the normal workflow.

## TaskSpec

`TaskSpec` describes the world and scoring objective: duration, timestep, terrain, target,
reward terms, and optional events such as damage or impulse events.

## EpisodeTrace

Every run saves an `EpisodeTrace` under `runs/<run-id>/` with:

- `creature.json`
- `task.json`
- `trace.json`

The trace records part poses, joint angles, contacts, scores, metadata, hashes, warnings, and
backend information. Replays and exports render recorded poses; they do not re-run physics.

The newest saved run is recorded in `runs/latest.txt`, so `inspect latest`, `diagnose latest`,
`report latest`, `view latest`, and `export latest` all refer to the most recent artifact.
Benchmarks save ordinary run folders too, which keeps reports and replays available for every
benchmark episode.

## Backends

PyBullet is the default backend. MuJoCo is available as an optional backend. Backend adapters are
implementation details behind the portable creature/task/trace contracts.

Specs, tasks, traces, and replays are portable. Exact motion is backend-dependent because
physics engines solve contacts, joints, and actuators differently.

## Improvement Loops

`evolve` runs local search over creature body/controller parameters and saves the best result.

`ask` edits a creature through validated design tools. `ask --offline` works without an API key;
online mode uses LiteLLM when the `llm` extra and provider credentials are configured.

## Creature Zoo

The zoo is the first place to explore the system. It ships curated creatures, tasks, and baseline
data with the package so new users can run interesting examples immediately.
