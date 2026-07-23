# Run Artifacts

Every saved episode lives under `runs/<run-id>/`.

```text
runs/
  latest.txt
  <run-id>/
    creature.json
    task.json
    controller.json # exact controller snapshot
    policy.zip      # policy controllers only
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
- `controller.json`: the exact built-in/tuned/policy controller snapshot used for the episode.
- `policy.zip`: copied beside `controller.json` when the controller is a trained policy. Treat
  policy files as trusted-code artifacts; do not load an untrusted policy bundle.
- `trace.json`: the `EpisodeTrace` with poses, joint angles, contacts, scores, events, and
  metadata, including controller/policy hashes and the run-relative controller artifact.

## Sharing a Run

`creature-lab export-pack <run>` bundles the exact creature/task/controller/trace plus optional
policy payload and a reproducibility-hash `manifest.json` into one portable
directory — nothing left implicit in `runs/` or `latest.txt`:

```bash
uv run creature-lab export-pack latest --out outputs/my_design_pack
uv run creature-lab verify-pack outputs/my_design_pack
```

Version 2 packs hash every byte artifact and each semantic JSON model. Verification detects
tampering, missing files, unsupported layouts, unsafe bundle paths, and absent policy payloads.

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
