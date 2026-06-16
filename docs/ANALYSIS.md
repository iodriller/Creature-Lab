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

Expected for a bootstrap repo, listed here against `docs/MVP_PLAN.md`:

- **G9** — No backend protocol or PyBullet adapter (Phase 3).
- **G10** — No controllers / sinusoid target generation (Phase 2).
- **G11** — No trace writer/reader (Phase 2).
- **G12** — No Viser live viewer (Phase 4); no replay/export (Phase 5).
- **G13** — No baseline mutator (Phase 6); no LLM tool loop or `AgentTrace` schema (Phase 7).
- **G14** — `numpy`/`rich` are declared dependencies but not yet used.
- **G15** — Acyclicity check is recursive (`creature.py`); fine for the MVP, but an iterative
  DFS would avoid Python's recursion limit on very deep creatures.

---

## 🎨 UI / UX / DX improvements

No viewer exists yet, so today's highest-leverage UX is onboarding/DX:

- **U1** — `validate` is now the first real command and surfaces friendly, Rich-rendered
  errors instead of raw Pydantic dumps. It is the cheapest "clone → run → it works" win.
- **U2** — The headline path now works: `uv sync` succeeds, the valid example validates, and
  `uv run creature-lab validate examples/tripod.json` prints a readable result.
- **U3 (future)** — For the Viser viewer, keep the plan's floor grid / target marker / score
  panel / contact markers / motion trail, and add a visible "physics is backend-dependent"
  disclaimer plus a deterministic-seed display to honor the portability promise.
