# Run Artifacts

Every saved episode lives under `runs/<run-id>/`.

```text
runs/
  latest.txt
  <run-id>/
    creature.json
    task.json
    trace.json
    lineage.json    # evolve only
    archive.json    # map-elites evolve only
    agent.json      # ask only; design-tool trace, not an agent framework
```

`latest.txt` records the most recently saved run id. Any run-reading command can use
`latest` instead of a path:

```bash
uv run creature-lab zoo run quadruped
uv run creature-lab inspect latest
uv run creature-lab report latest
uv run creature-lab export latest --gif creature.gif
```

## Required Files

- `creature.json`: the exact `CreatureSpec` used for rendering and reproducibility.
- `task.json`: the `TaskSpec` used for the episode.
- `trace.json`: the `EpisodeTrace` with poses, joint angles, contacts, scores, events, and
  metadata.

## Optional Files

- `lineage.json`: evolution strategy, candidate scores, parent links, and accepted candidates.
- `archive.json`: MAP-Elites behavior cells when that strategy is used.
- `agent.json`: validated design-tool attempts from `ask`. This is a design trace artifact,
  not a generic multi-agent runtime.

## Reports

Generate a Markdown report:

```bash
uv run creature-lab report latest --out report.md
```

Generate JSON for another tool:

```bash
uv run creature-lab report latest --json
```

Reports include score breakdowns, hashes, backend metadata, warnings, diagnosis patterns,
improvement summaries, and artifact paths.
