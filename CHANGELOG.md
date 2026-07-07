# Changelog

All notable changes to Creature Lab are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Phases from [`docs/IMPROVEMENT_PLAN_2026.md`](docs/IMPROVEMENT_PLAN_2026.md), building on
the complete MVP.

### Added

- **Self-contained HTML reports** (Phase R): `report --html` writes a single offline run
  card (score breakdown, signal sparklines, root-path plot, optional embedded GIF,
  diagnosis, and a reproducibility block with a runnable reproduce command).
  `compare --html` writes a before/after comparison report. `gallery build --zoo` now also
  emits `index.html` with baseline-vs-current score coloring per creature.
- **Terrain library** (Phase 1): `TaskSpec.terrain.type` gains `slope`, `steps`, `gaps`, and
  `rough`, built from a shared, deterministic heightfield (`creature_lab/terrain.py`) that
  both the PyBullet and MuJoCo backends simulate with the same shape. Three new quadruped
  zoo tasks: `slope_climb`, `step_over`, `gap_cross`.
- **Robustness and sim2sim analysis** (Phase 2): `robustness <run> --trials N` re-simulates
  under small seeded mass/friction perturbations and reports the score distribution and
  fail rate. `sim2sim <run>` runs the same creature/task on PyBullet and MuJoCo and reports
  the score gap and trajectory divergence. Both support `--save` to write a reportable run.
- **Quality-diversity gallery** (Phase 3): `evolve --strategy map_elites` now persists each
  filled cell's `CreatureSpec`. `archive show <run> --html` renders a scored heatmap (with
  optional per-cell replay GIFs via `--task`); `archive export --cell row,col` pulls one
  elite out as a standalone spec.
- **Sharpened LLM design loop** (Phase 4): `ask`'s prompt (and the offline policy's
  `Observation`) now includes the current diagnosis, so proposals can target a detected
  failure pattern instead of guessing blind. New `evolve --strategy llm` mutation operator
  reuses the offline, no-API-key `RandomToolPolicy` through the validated tool layer;
  per-attempt rationale is saved into `lineage.json`.
- **MuJoCo baselines** (Phase 5): every packaged zoo creature/task pair now has a
  real, measured MuJoCo baseline (`baselines/<task>.mujoco.json`) alongside the existing
  PyBullet one; `zoo_baseline(..., backend=...)` and `bench --backend mujoco --zoo` compare
  against the correct one (previously `bench` always compared against the PyBullet
  baseline, even when benchmarking MuJoCo — this silently made the pass/fail threshold
  wrong for every non-default-backend benchmark run).

- **Terrain fidelity in viewer/export/report**: `view`, `compare`, `export`, and the run
  report's embedded GIF now draw the *actual* terrain shape (a `trimesh` heightfield mesh
  in the Viser viewer, a PyBullet heightfield body in `render_trace`) instead of always a
  flat floor. Found in a post-implementation review: the terrain physics was correct but
  every visualization still showed a flat plane, so a `slope_climb`/`gap_cross` replay
  misleadingly showed the creature floating above or sinking into nothing.
- **Terrain surfaced in reports/inspect**: `creature_lab/terrain.describe_terrain()` gives
  a one-line summary (e.g. `"slope (angle=0.2 rad, friction=1)"`), now shown by `inspect`
  and included in every run report (Markdown, HTML, and JSON) — previously a report gave
  no indication of which terrain a run used.
- `docs/KNOWN_ISSUES.md`: a living list of latent gaps and deliberate limitations found in
  review, so findings have a home instead of being re-discovered or lost.

### Fixed

- `bench --zoo --backend mujoco` compared results against the PyBullet baseline (a much
  higher score than nearly every gait achieves on MuJoCo), so the pass/fail threshold was
  meaningless for any backend other than the default.
- `evolve --strategy map_elites` discarded each archived cell's `CreatureSpec`, saving only
  its score/features — `archive export` had nothing to export until this was fixed.

## [0.1.0]

Initial MVP: schemas, CLI, PyBullet and MuJoCo backends, Viser replay, local evolution
(hill-climb/genetic/MAP-Elites/CMA-ES), offline/online `ask` design loop, the Creature Zoo,
diagnosis, URDF/MJCF export, and reports. See [`docs/archive/`](docs/archive/) for the
phase-by-phase history.
