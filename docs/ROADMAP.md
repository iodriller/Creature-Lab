# Roadmap

The MVP is complete. The repo already has schemas, CLI commands, PyBullet and MuJoCo backends,
Viser replay, exported traces, diagnosis, zoo creatures, local evolution, offline design edits,
reports, zoo benchmarks, schema export, and tests.

Future work should make the product clearer and easier to trust before adding more simulation
surface area.

## Priorities

1. Keep onboarding proof fresh: regenerate the demo GIF and zoo gallery for releases.
2. Improve benchmark trust: add calibrated baselines for every packaged task and backend.
3. Polish release packaging: publish wheels, add versioned docs, and ensure packaged data works
   outside the repo checkout.
4. Expand compatibility carefully: keep URDF/MJCF/MuJoCo as bridges, not the main onboarding path.
5. Add richer physical tasks only after reports, benchmarks, and zoo docs stay stable.

## Guard Rails

- Do not make new users choose between many backends before they see a creature move.
- Do not front-load architecture language ahead of the design/run/improve loop.
- Do not add a dashboard until the CLI and docs feel obvious.
- Do not add generic agent orchestration, personas, or memory APIs; Creature Lab is the physical
  experiment layer.
- Do not remove advanced commands that already work; keep them lower in the docs.
