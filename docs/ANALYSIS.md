# Repository Analysis — Bugs, Gaps, and Improvements

**Date:** 2026-06-16
**Scope:** Full repository audit (schemas, packaging, example, tests, docs).
**Method:** Findings were verified empirically — building with `uv sync`, importing the
package, probing the Pydantic validators with edge-case inputs, and running `ruff`.

At audit time the repo was an early bootstrap: only the three Pydantic schemas
(`creature.py`, `task.py`, `trace.py`) were implemented. The schema *logic* was sound, but
the packaging, example, and tests around it were broken, so **nothing installed or ran** and
all three "Preferred checks" in `CLAUDE.md` failed.

This document records what was found. Items marked ✅ were fixed in the same change set; items
marked ⏳ are tracked follow-ups (mostly unbuilt MVP phases).

---

## 🐞 Bugs

### B1 — Package could not be built or installed ✅ (CRITICAL)
`pyproject.toml` named the project `creature-lab`, so Hatchling looked for a `creature_lab/`
directory, but the code lived in `creaturelab/`. `uv sync` failed with
*"Unable to determine which files to ship inside the wheel … no directory that matches the
name of your project (creature_lab)."* This blocked the MVP acceptance criterion *"a fresh
clone can install with documented commands."*

**Fix:** renamed `creaturelab/` → `creature_lab/` (matches the project name and
`docs/MVP_PLAN.md §11`) and added an explicit `[tool.hatch.build.targets.wheel]` package list.

### B2 — `creature-lab` console script pointed at a non-existent module ✅ (CRITICAL)
The entry point was `creature-lab = "creature_lab.cli:app"`, but no `cli.py` existed. Every
documented command import-errored.

**Fix:** added a minimal Typer CLI (`creature_lab/cli.py`) exposing `validate` and `version`.

### B3 — The only example creature did not validate ✅
`examples/tripod.json` was `{"name":"tripod"}`. `CreatureSpec` requires `parts`, so it raised
`ValidationError`. Phase 1 requires *"example creatures validate."*

**Fix:** replaced it with the full, valid tripod spec.

### B4 — All three `CLAUDE.md` "Preferred checks" failed ✅
- `uv run pytest` → triggered the build → failed (B1).
- `uv run ruff check .` → `E501` at `creature.py:173` (109 > 100).
- `uv run ruff format --check .` → `creature.py` needed reformatting.

**Fix:** corrected the long line, reformatted, and (B1) made the build succeed.

### B5 — Tests were placeholder/probe junk ✅
`tests/test_placeholder.py` asserted `True`; `tests/test_probe2.py` defined an empty
`class CreatureSpec: pass` that tested nothing and shadowed the real type name. There were zero
real schema/round-trip tests though Phase 1 requires them.

**Fix:** removed the probes; added real schema, round-trip, and CLI tests.

---

## 🕳️ Schema correctness gaps (bug-class) — fixed

These were accepted by the validators but represent authoring/correctness hazards. All verified
by probing the live models, all fixed.

- **G1 — Multiple motors on one joint were accepted** ✅ — now rejected (one motor per joint).
- **G2 — `reward.target_distance` could be set with `task.target is None`** ✅ — now
  cross-validated so a target-based reward requires a target.
- **G3 — Stray dimension fields were silently ignored** ✅ — a `box` with `radius`/`length`,
  or a `sphere`/`box` with the wrong field, now raises instead of being silently dropped.
- **G4 — `FrameState.score` accepted `inf`/`nan`** ✅ — scores must now be finite.
- **G5 — Quaternion convention was undocumented** ✅ — documented as `(w, x, y, z)` on the
  `Quaternion` type and `PartPose`. Note: PyBullet uses `(x, y, z, w)`; the backend adapter
  must convert at the boundary.

---

## 🧹 Structural / DX gaps — fixed

- **G6 — `StrictModel`, `Vector3`, `Quaternion` were duplicated** across all three schema
  files ✅ — consolidated into `creature_lab/schema/base.py`.
- **G7 — No `schema/__init__.py`; models were not re-exported** ✅ — added package init that
  re-exports the public models; `creature_lab/__init__.py` now exposes them too.
- **G8 — No CI** ✅ — added a GitHub Actions workflow running `ruff check`, `ruff format
  --check`, and `pytest`.

---

## ⏳ Larger gaps (unbuilt MVP phases — tracked, not yet built)

Listed here against `docs/MVP_PLAN.md`; later commits closed most of them.

- **G9** ✅ — Backend protocol (`backends/base.py`) and PyBullet adapter
  (`backends/pybullet_backend.py`) added (Phase 3). PyBullet is an optional `sim` extra.
- **G10** ✅ — Sinusoid controller added (`controllers/sinusoid.py`, Phase 2).
- **G11** ✅ — Trace writer/reader added (`runs.py`) with a `run` + `replay` CLI (Phase 2/5).
- **G12** ✅ — Viser browser viewer added (`viewers/viser_viewer.py`): `view` replays a saved
  run and `demo` streams the simulation live (Phase 4), plus GIF/MP4 export
  (`viewers/video_exporter.py` + `render_trace`, `export` command, Phase 5). Replay/export
  render recorded poses without re-running physics.
- **G13** ✅/⏳ — Baseline mutator + hill-climb (`evolve.py`, `evolve` command) added (Phase 6).
  The LLM tool loop and a dedicated `AgentTrace` schema (Phase 7) are still pending.
- **G14** ✅ — Removed the unused `numpy` dependency; `rich` is now used by the CLI.
- **G15** ⏳ — Acyclicity check is recursive (`creature.py`); fine for the MVP, but an iterative
  DFS would avoid Python's recursion limit on very deep creatures.
- **G16** ✅ — Scoring now implements all reward terms. A pure `creature_lab/scoring.py`
  combines `forward_distance`, `target_distance` (progress toward the target), `energy_penalty`
  (integrated squared joint speed), and `fall_penalty` (toppled when the body's up-axis tips
  past 60°); the PyBullet backend feeds it real measurements. New `reach_target.json` and
  `recover_after_damage.json` example tasks exercise these.

---

## 🎨 UI / UX / DX improvements

No viewer exists yet, so today's highest-leverage UX is onboarding/DX:

- **U1** — `validate` is now the first real command and surfaces friendly, Rich-rendered
  errors instead of raw Pydantic dumps. It is the cheapest "clone → run → it works" win.
- **U2** — The headline path now works: `uv sync` succeeds, the valid example validates,
  `run` simulates and saves a trace, `replay` reads it back, and `evolve` hill-climbs and
  prints a Rich lineage table.
- **U3 (future)** — For the Viser viewer, keep the plan's floor grid / target marker / score
  panel / contact markers / motion trail, and add a visible "physics is backend-dependent"
  disclaimer plus a deterministic-seed display to honor the portability promise.

---

## 🔎 End-to-end audit (2026-06-17)

A second pass that ran the whole pipeline and read every module. Findings:

- **G17 ✅ — Example creature was physically degenerate.** Every joint anchor defaulted to
  `(0, 0, 0)`, so all three tripod legs spawned at the exact torso center `(0, 0, 1)` — a pile
  of overlapping parts. Fixed by giving the legs distinct anchors that hang below the torso.
- **G18 ✅ — CI only installed `--extra dev`.** All backend, viewer, and export tests are
  guarded by `importorskip`, so the most complex code (~13 tests) silently skipped in CI;
  only schema/CLI/evolve/runs ran. CI now uses `uv sync --all-extras` so the full suite runs.
- **G19 ✅ — Missing backend tests.** Added a `reset()` test and a `SimBackend` protocol
  conformance test (the protocol is now `@runtime_checkable`).
- **G20 ✅ — Child parts can now be oriented relative to their parent.** Added a
  `rest_orientation` quaternion to `JointSpec` (scalar-first, identity by default, zero
  rejected), applied as the link orientation in the PyBullet backend, so limbs can be angled
  rather than only axis-aligned. Verified by a backend test (a fixed child with a 90° rest
  orientation reports that orientation).
- **G21 ✅ — `demo` no longer depends on the working directory.** Added `creature_lab/library.py`
  with built-in `default_creature()` / `default_task()`; `creature-lab demo` uses them when no
  paths are given, so it works from an installed package (verified from a foreign CWD).
- **G22 ✅ — `render_trace` rounds dimensions up to even** so MP4 (libx264) stays valid.
- **G23 ✅ — Step count is FP-robust.** `TaskSpec.step_count()` uses rounding (min 1) instead
  of truncating `duration / timestep`, so float error can no longer silently drop the final
  step; the CLI and tests use it.
- **G24 ✅ — Contacts were defined but never reported (and never drawn).** `FrameState.contacts`
  / `ContactSpec` existed in the schema (and the plan's viewer wishlist), but the PyBullet
  backend always left `contacts` empty. The backend now reports ground contacts each step
  (part id, world position, normal, clamped normal force) via `getContactPoints`, and the Viser
  viewer draws them as a pooled set of red markers shown/hidden per frame. Backend and viewer
  tests cover both ends.
- **G25 ✅ — No full-pipeline coverage.** Added `tests/test_end_to_end.py`: scenario tests that
  drive the CLI through complete pipelines (`run → replay → export`, every example task, live
  `demo`, `evolve → export`, and `ask --offline`) and assert the on-disk artifacts — exercising
  the real backend, trace I/O, viewer, and exporter together. To make the interactive viewer
  testable, `demo` gained `--no-hold` (stream one pass, save, exit), also useful for headless/CI.
- **G26 ✅ — Phase 7 (LLM tool loop) built.** Added the agent layer: validated tools
  (`agents/tools.py` — `set_motor`, `set_joint_limit`, `resize_limb`, each returning a
  re-validated `CreatureSpec`), a provider-agnostic `design_loop` (`agents/loop.py`), an
  `AgentTrace` schema, a no-provider `RandomToolPolicy` (`agents/baseline.py`), and a
  LiteLLM-backed `LLMPolicy` behind the optional `llm` extra (`agents/llm.py`, imported lazily;
  prompt building/parsing in `agents/prompts.py` is unit-tested without network). The `ask`
  command runs the loop and saves `agent.json`; `--offline` makes it runnable and e2e-testable
  with no API key.

- **P0a ✅ — Reproducible, self-describing runs.** `save_run` now also writes `task.json`
  (`load_run` reads all three back). `EpisodeTrace` carries an optional `TraceMeta`
  (`schema/trace.py`): schema/lab versions, PyBullet backend version, timestep, seed, canonical
  `creature_hash`/`task_hash` (new `hashing.spec_hash`), and a per-component `score_summary`
  (surfaced from the backend via `score_summary()` / `scoring.score_components`).
- **P0b ✅ — Pre-simulation cross-validation.** New `validation.validate_episode_inputs` raises
  `EpisodeInputError` on hard mistakes (e.g. `damage_event.part_id` not on the creature) and
  returns warnings for soft issues (unused target, large timestep, no objective, motor amplitude
  exceeding a joint limit). Every `run`/`demo`/`evolve`/`ask` runs it first; `validate --task`
  exposes it as a no-sim pre-flight.
- **P1a ✅ — Normalized physical-math fields.** `JointSpec.axis` and `rest_orientation` are
  normalized to unit length on load (degenerate/zero values still rejected). Motor-amplitude vs
  joint-limit is reported as a pre-sim warning (kept soft so aggressive motors stay usable).
- **P1b ✅ — Viewer fidelity.** The Viser viewer renders cylinders with the native
  `add_cylinder` and capsules as true rounded-end meshes via `trimesh.creation.capsule` +
  `add_mesh_trimesh` (matching the PyBullet export); `view` auto-loads `task.json` for the target
  marker.

Verified clean after the fixes: `ruff check`, `ruff format --check`, and `pytest` (119 tests,
including end-to-end scenarios) all green, and the full CLI loop
(`validate → run → replay → export → evolve → ask → demo`) works.
