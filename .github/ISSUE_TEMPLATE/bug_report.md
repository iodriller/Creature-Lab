---
name: Bug report
about: Report a crash, incorrect run artifact, or broken CLI workflow
title: "Bug: "
labels: bug
---

## What happened?

## Command

```bash

```

## Expected behavior

## Environment

- OS:
- Python:
- Creature Lab version:
- Backend: pybullet / mujoco / none

## Artifacts

Prefer a verified design pack—it contains the exact creature, task, controller, trace, and hashes:

```bash
creature-lab export-pack latest --out creature-lab-bug-pack
creature-lab verify-pack creature-lab-bug-pack
```

Attach the pack, or paste `report latest --json` when a pack cannot be shared. Policy packs may
contain serialized code; do not attach secrets or a policy you are not allowed to redistribute.
