---
name: Creature submission
about: Propose a new packaged zoo creature
title: "Zoo creature: "
labels: zoo
---

## Creature name

Use lowercase words with underscores.

## What should it demonstrate?

## Files

- `creature.json`:
- task JSON:
- baseline JSON, if available:
- GIF or report, if available:

## Validation

```bash
uv run creature-lab validate path/to/creature.json --task path/to/task.json
uv run creature-lab run path/to/creature.json --task path/to/task.json
uv run creature-lab report latest
```
