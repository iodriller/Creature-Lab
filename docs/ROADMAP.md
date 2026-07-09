# Roadmap

The MVP is complete. The repo already has schemas, CLI commands, PyBullet and MuJoCo backends,
Viser replay, exported traces, diagnosis, zoo creatures, local evolution, offline design edits,
reports, zoo benchmarks, schema export, and tests.

Future work should make the product clearer and easier to trust before adding more simulation
surface area.

## Priorities

1. Keep onboarding proof fresh: regenerate the demo GIF and zoo gallery for releases.
2. ✅ Improve benchmark trust: every packaged task now has a calibrated baseline for **both**
   backends (`baselines/<task>.json` for PyBullet, `baselines/<task>.mujoco.json` for
   MuJoCo); `bench --backend <name> --zoo` compares against the matching one.
3. Polish release packaging: publish wheels, add versioned docs. Packaged zoo/data working
   outside the repo checkout is ✅ verified (built the wheel, installed it into a clean venv,
   ran `zoo run` from a foreign directory — reproduced the committed baseline score exactly).
   Publishing to PyPI needs a maintainer with real credentials — out of scope for an agent
   session; see [`docs/IMPROVEMENT_PLAN_2026.md`](IMPROVEMENT_PLAN_2026.md) Phase 5.
4. Expand compatibility carefully: keep URDF/MJCF/MuJoCo as bridges, not the main onboarding path.
5. Add richer physical tasks only after reports, benchmarks, and zoo docs stay stable.

See [`docs/IMPROVEMENT_PLAN_2026.md`](IMPROVEMENT_PLAN_2026.md) for the current, more
detailed improvement plan (report upgrade, terrain, robustness, MAP-Elites gallery, and the
LLM design loop) — this file stays as the high-level guard rails.

## Guard Rails

- Do not make new users choose between many backends before they see a creature move.
- Do not front-load architecture language ahead of the design/run/improve loop.
- Do not add a dashboard until the CLI and docs feel obvious.
- Do not add generic agent orchestration, personas, or memory APIs; Creature Lab is the physical
  experiment layer.
- Do not remove advanced commands that already work; keep them lower in the docs.
