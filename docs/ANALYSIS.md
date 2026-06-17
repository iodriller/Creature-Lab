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
- **G16** ⏳ — Scoring only implements `reward.forward_distance`; `target_distance`,
  `energy_penalty`, and `fall_penalty` are accepted by the schema but not yet computed by the
  PyBullet backend.

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
- **G20 ⏳ — No way to orient a child part relative to its parent.** `JointSpec` has `anchor`
  and `axis` but no child rest-orientation, so limbs can only be axis-aligned (capsules always
  point along the parent's local Z). Proper splayed/angled legs need a `rest_orientation`
  field on `JointSpec` (scalar-first quaternion), applied as the link orientation in the
  backend. This is the main thing standing between the current "stool" and a real walker — the
  recommended next enhancement.
- **G21 ⏳ — `demo` defaults are CWD-relative and `examples/` is not packaged.** `creature-lab
  demo` only works from a repo checkout; a pip/uvx install has no `examples/`. Consider
  bundling a built-in default creature or shipping `examples/` as package data.
- **G22 ⏳ — `export` MP4 with odd width/height fails in ffmpeg (libx264).** Defaults
  (640×480) are even, but a user can pass odd values; round dimensions up to even (or document).
- **G23 ⏳ — Several scheduling/robustness niceties.** `int(duration / timestep)` silently
  drops a partial final step; `TaskSpec` does not warn when `timestep` doesn't divide
  `duration`. Low priority.

Verified clean after the fixes: `ruff check`, `ruff format --check`, and `pytest` (59 tests)
all green, and the full CLI loop (`validate → run → replay → export → evolve → demo`) works.
