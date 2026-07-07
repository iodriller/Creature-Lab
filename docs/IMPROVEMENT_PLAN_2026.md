# Creature Lab — Improvement Plan (2026 H2)

**Date:** 2026-07-07
**Premise:** The MVP and the eight-phase plan in [`docs/archive/IMPROVEMENT_PLAN.md`](archive/IMPROVEMENT_PLAN.md)
are complete. The repo has schemas, PyBullet + MuJoCo backends, Viser replay + debug
overlays, diagnosis, a curated zoo, four evolution strategies, an offline/online `ask`
loop, URDF/MJCF bridges, and **223 passing tests**. This plan does **not** re-propose any
of that. It answers a different question: *given a working lab, what raises the quality of
what it produces and reports — without turning Creature Lab into Agentarium?*

The user's two explicit asks drive the priority order:

1. **Improve "that report."** The run report today is Markdown text only
   ([`creature_lab/reports.py`](../creature_lab/reports.py); `report latest`). The zoo
   gallery emits Markdown cards + GIFs, not an integrated visual artifact. This is the
   single most visible output of the whole loop and the biggest quality lever. **Phase R.**
2. **Maybe more features** — grounded in what comparable projects do and in Creature
   Lab's specific niche. **Phases 1–5.**

---

## 1. Keep Creature Lab ≠ Agentarium

These two repos are neighbours, not competitors, and the plan is built to keep them
distinct. Stating the boundary explicitly so no phase blurs it:

| Axis | **Creature Lab** | **Agentarium** |
| --- | --- | --- |
| Primary actor | A **person** (or a local search loop) designing one creature | **LLM agents** picking tools to build things |
| Unit of work | `CreatureSpec` → `EpisodeTrace` — one morphology, deeply | An **attempt** in a scored challenge, replayed in a Studio |
| Interface | **Python-first CLI**, JSON specs, Viser viewer | **Web app** (React/Phaser Studio), backend server, `/api` + `/ws` |
| Physics | 3D articulated rigid bodies (PyBullet / MuJoCo) | 2D isometric world (Pymunk2D), PyBullet3D planned |
| Depth vs breadth | **Depth** on one creature: scaffold → diagnose → evolve → export | **Breadth**: many agents, challenges, worlds, multi-agent attribution |
| LLM role | Optional design *editor* (`ask`), offline by default | Central: agents *are* the users |
| Output | Portable JSON + traces + reports + URDF/MJCF | Scored, replayable, shareable Studio runs |

**The one-line identity to protect:** *Creature Lab is the smallest tool that takes "I want
a creature that walks" from zero to a valid spec, a running simulation, a plain-language
failure diagnosis, a co-evolved body+controller, and an exportable result — without writing
URDF or code.*

**Hard guard rails (carried forward from the archived plan, still binding):** no web
dashboard/server, no multi-agent arena, no Studio, no leaderboard service, no
natural-language *challenge generation*, no real-time LLM torque control. Anything on that
list is Agentarium's job. Where a phase below flirts with a boundary, the "Boundary check"
note says how it stays on the Creature Lab side.

---

## 2. Where Creature Lab sits in the 2026 landscape

Findings from a scan of comparable open projects, and the gap each leaves that Creature Lab
already fills or should fill:

| Project | What it is | Gap Creature Lab targets |
| --- | --- | --- |
| **Evolution Gym / EvoGym** ([repo](https://github.com/EvolutionGym/evogym), [paper](https://arxiv.org/pdf/2201.09863)) | 2D **voxel soft-body** co-design benchmark, 32 tasks | Voxel-only, no articulated joints/humanoids, no plain-language diagnosis, no export bridge |
| **Revolve2** ([repo](https://github.com/ci-group/revolve2), [docs](https://ci-group.github.io/revolve2/)) | Research library for modular-robot EA over a physics abstraction | Heavy research stack; not a "clone → creature moves in one command" tool; no built-in diagnosis/report |
| **MuJoCo Menagerie / Playground** | Curated fixed models + RL example envs | Fixed assets — no authoring/evolution loop, no failure explanation |
| **Gymnasium-Robotics** | Fixed RL benchmark envs | No morphology editing, no diagnosis, no evolution |
| **RoboMorph** ([paper](https://arxiv.org/abs/2407.08626), [site](https://robomorph.github.io/)) | LLM-as-generative-operator evolving morphologies, terrain-specialized | Research prototype; validates the *idea* Creature Lab can offer as a first-class, offline-first, reproducible loop |
| **Rollout Cards / Open RL Benchmark** ([Rollout Cards](https://arxiv.org/pdf/2605.12131), [ORLB](https://arxiv.org/html/2402.03046v1)) | Reproducibility standards / tracked-experiment reporting | Confirms the direction for Phase R: a self-contained, reproducible **run card**, not just a metrics dump |

**Read-out:** Creature Lab's defensible niche is *articulated-creature authoring with
built-in explanation and a portable output contract*. The competitors are either fixed
libraries, voxel-only, or heavy research frameworks. The two highest-leverage moves are
therefore (a) make the **output** (report) best-in-class and (b) deepen the parts of the
loop no competitor has — diagnosis, terrain robustness, and quality-diversity — while
staying tiny.

---

## Phase R — The report, upgraded (top priority) ✅

**Status (2026-07-07):** R1–R4 shipped. `creature_lab/reports_html.py` adds
`report_to_html`, `comparison_to_html`, and the zoo `gallery_index_html`/`gallery_card_html`
renderers; `reports.py` gained `build_report_bundle`, `build_comparison`, and a
`reproducibility` block (also rendered into the Markdown report). CLI: `report --html`,
`compare --html`, and `gallery build --zoo` now also emits `index.html`. All output is
verified to embed no external URLs. 11 new tests (`tests/test_reports_html.py` +
extensions to `tests/test_productization.py`); full suite green (252 passing), ruff clean.

**Why first:** the report is what a user keeps, shares, and judges the tool by. Today it is
`report_to_markdown` — a flat text dump with no visuals, no comparison, no reproducibility
block, and no shareable single file. Everything needed to make it excellent (traces, scores,
diagnosis, overlays math, GIF/plot export) *already exists* — it just isn't composed.

### R1 — Self-contained HTML run card
- New `creature_lab/reports_html.py`: `report_to_html(report, *, embed_media=True) -> str`.
- One file, no external requests: inline CSS, inline SVG sparklines for the metric series
  already produced by [`viewers/overlays.py`](../creature_lab/viewers/overlays.py)
  (`metric_series`, `center_of_mass_trail`, `root_path`), and an optional GIF embedded as a
  `data:` URI via the existing `render_trace` + `write_animation` path.
- Sections: header (creature/task/backend/score), **score breakdown bar**, signal
  sparklines (CoM height, forward displacement, joint energy), **root-path plot** (top-down
  SVG), diagnosis with severity coloring, warnings, improvement lineage, reproducibility
  block (see R3), artifact list.
- CLI: `report latest --html report.html` (extend the existing `report` command; keep
  Markdown as default so nothing breaks).
- **Boundary check:** static file written to disk, opened by the user's own browser — no
  server, no framework. Uses the same `data:`-URI, no-network discipline as an offline doc.

### R2 — Comparison / before-after report
- `report compare runs/<a> runs/<b> --html diff.html` (or extend the existing `compare`
  command). Side-by-side score deltas, overlaid root-path plots, and a per-signal delta
  table — the natural artifact after an `evolve` or `ask` run ("it went from 0.24 → 0.38,
  here's what changed and where the body moved differently").
- Reuse `viewers/overlays.compare_traces` math; no new physics.

### R3 — Reproducibility block ("run card" discipline)
- Every report (Markdown + HTML) grows a **Reproducibility** section from data already in
  `TraceMeta`: schema/lab versions, backend + backend version, seed, timestep, canonical
  `creature_hash` / `task_hash`, and the exact **command to reproduce** the run.
- Inspired by Rollout Cards / Open RL Benchmark: a score means nothing without the record
  behind it. This also strengthens the "every episode is a trace" promise.

### R4 — Zoo scorecard + gallery, integrated
- Extend `gallery build --zoo` to emit a single `index.html` (currently `index.md`) that
  embeds each creature's card, GIF, and **baseline-vs-latest** score, so `bench --zoo`
  output and the gallery become one shareable page.
- Add regression coloring: green/red vs the committed baseline in `zoo/*/baselines/`.

**Acceptance criteria (Phase R)**
- `report latest --html out.html` writes one file that opens offline with no network fetches
  (grep the output for `http://`/`https://` in `src`/`href` → none except doc links).
- HTML report shows the score-breakdown bar, at least three signal sparklines, and the
  root-path plot; falls back gracefully to "no media" when the `export` extra is absent.
- `report compare a b --html` renders both runs and a signed delta table.
- Reproducibility block prints a runnable command; the hashes match `inspect`.
- New tests cover: HTML contains required sections, no external URLs, renders with and
  without a GIF, and comparison delta math. `ruff` + `pytest` green.

---

## Phase 1 — Terrain library (physical depth, not new surface) ✅

**Status (2026-07-07):** Shipped. `TerrainSpec` gained `slope`/`steps`/`gaps`/`rough` types;
`creature_lab/terrain.py` generates a deterministic, seeded heightfield shared by both
backends (`heightfield_grid`, `heightfield_range`, `normalized_heightfield_data`,
`flatten_for_heightfield_api`). PyBullet builds a `GEOM_HEIGHTFIELD` body; MuJoCo builds a
`<hfield>` asset and fills `model.hfield_data` at runtime from the same grid. Both engines
turned out to (a) auto-recenter/reindex heightfield data in ways their docs don't state
plainly and (b) share the same axis convention — verified empirically with a raycast probe
(PyBullet) and a free-falling probe body (MuJoCo) before trusting the physics. `gaps`
terrain keeps a solid platform around the origin so a creature always spawns on ground.
Added three zoo tasks (`slope_climb`, `step_over`, `gap_cross`) under `quadruped` with
measured baselines. 32 new tests (`test_terrain.py` + backend/MJCF/zoo additions); full
suite green (284 passing), ruff clean.

**Why:** RoboMorph's headline result is that *terrain* drives morphology — different ground
produces wheeled quads, hexapods, etc. Creature Lab's tasks today are mostly flat-ground.
Adding a small, deterministic terrain vocabulary makes diagnosis, evolution, and the zoo far
more interesting *without* new architecture — terrain is just a `TaskSpec` field the backend
reads.

- Extend `TaskSpec.world`/terrain with a small enum + params: `flat` (default), `slope`,
  `steps`, `gaps`, `rough` (seeded heightfield). Keep it a data field so traces stay
  portable and deterministic (seeded).
- Implement in the PyBullet backend via `createCollisionShape(GEOM_HEIGHTFIELD)` /
  primitive ramps; add a MuJoCo equivalent (`<hfield>`) so the portability contract holds.
- Add 2–3 zoo tasks (`slope_climb`, `step_over`, `gap_cross`) with computed baselines.
- **Boundary check:** terrain is a physical world property of a single task, not a "challenge
  studio." No generation UI; specs stay JSON.

**Acceptance:** each terrain type simulates deterministically in both backends (same seed →
same trace hash within a backend); new zoo tasks validate and have baselines; diagnosis still
fires sensibly. Tests cover terrain construction + determinism.

---

## Phase 2 — Robustness & portability report (leans into the core promise) ✅

**Status (2026-07-07):** Shipped. `creature_lab/robustness.py` (pure, same
callback-injection pattern as `evolve.py`) perturbs part masses and terrain friction under
a seeded RNG and computes trial statistics. CLI: `robustness runs/<id> --trials N` and
`sim2sim runs/<id>` (PyBullet vs. MuJoCo score gap + mean root-position divergence via
`viewers/overlays.root_path`); both support `--save` to write a reportable run, and
`build_report`/`report_to_markdown`/`report_to_html` render an optional Robustness/Sim2Sim
section when present. Running `sim2sim` on the packaged quadruped surfaced a real, large
gap (PyBullet 0.57 vs. MuJoCo ≈0.00 for the same open-loop gait) — exactly the kind of
overfit-to-one-engine result this phase exists to surface, not hide. 20 new tests; full
suite green (296 passing), ruff clean.

**Why:** "Specs, tasks, traces are portable; exact physics is backend-dependent" is Creature
Lab's stated contract, but nothing *measures* it. This is a differentiator no competitor has.

- `robustness runs/<id>` (or `bench --robustness`): re-run a creature under N seeds and/or
  small perturbations (mass ±%, friction ±%, initial pose jitter) and report score
  mean/variance and failure rate — "does this gait actually work, or did it get lucky?"
- `sim2sim runs/<id>`: run the same creature on PyBullet **and** MuJoCo and report the score
  gap + trajectory divergence. Surfaces overfit-to-one-engine gaits.
- Both feed the Phase R HTML report as an optional section.

**Boundary check:** analysis over existing backends; no new engine, no cloud execution.

**Acceptance:** `robustness` produces a seeded score distribution; `sim2sim` runs both
engines (skips cleanly if `mujoco` extra absent) and reports divergence; tests use the `mock`
/ short-episode discipline. Wire results into the report.

---

## Phase 3 — Quality-diversity gallery (make MAP-Elites visible) ✅

**Status (2026-07-07):** Shipped. `evolve --strategy map_elites` now persists each filled
cell's `CreatureSpec` into `archive.json` (previously only score/features were saved — a
gap found while implementing this phase). CLI: `archive show <run>` prints a ranked table,
`--html` renders a red-to-green scored heatmap (`reports_html.archive_to_html`), and
`--html --task <task.json>` additionally renders a replay GIF per cell. `archive export
<run> --cell row,col --out spec.json` pulls any elite out as a standalone, editable
`CreatureSpec` — verified round-trip: exported a real elite from a 60-attempt run and it
validated cleanly with `creature-lab validate`. 8 new tests; full suite green
(301 passing), ruff clean.

**Why:** `evolve --strategy map_elites` already fills a behavior archive (`archive.json`),
but there is no way to *see* the diversity — the most compelling output of QD search is the
grid of "here are 30 different ways this body learned to move."

- `archive show runs/evolve/<id> --html archive.html`: render the MAP-Elites grid as a
  heatmap (score per cell) with a thumbnail GIF per elite cell, reusing `render_trace`.
- Add a CLI `archive export <id> --cell i,j --out creature.json` to pull any elite out as a
  normal spec (feeds back into the design loop).

**Boundary check:** visualization of an existing artifact; static HTML, no dashboard.

**Acceptance:** heatmap renders from `archive.json`; cell export produces a valid
`CreatureSpec`; tests cover grid rendering + export validity.

---

## Phase 4 — LLM design loop, sharpened (offline-first, optional)

**Why:** RoboMorph / Debate2Create show LLMs are effective *generative operators* for
morphology. Creature Lab already has the safe substrate: validated tools
([`agents/tools.py`](../creature_lab/agents/tools.py)) and a provider-agnostic loop. The
improvement is *quality of the loop*, not a new agent product.

- Feed the **diagnosis output** into the `ask` prompt so the LLM (or the offline policy)
  proposes targeted edits ("moving_backward → flip gait phase") instead of blind search.
- Add a `--strategy llm` operator to `evolve` that uses the design loop as a mutation
  operator inside the existing evolutionary scaffolding — offline `RandomToolPolicy` remains
  the default so it runs with no API key and stays testable.
- Save the LLM's rationale per accepted edit into `agent.json` for the report's Improvement
  section.

**Boundary check:** the LLM *edits one creature's JSON through validated tools*, offline by
default. It does not run challenges, drive real-time control, or generate tasks — those are
Agentarium. Keep the `docs/ROADMAP.md` guard rail ("no generic agent orchestration").

**Acceptance:** `ask` prompt includes diagnosis context (verified in the unit-tested prompt
builder, no network); `evolve --strategy llm` runs end-to-end offline; rationale appears in
the report. Tests stay network-free via the mock/offline policy.

---

## Phase 5 — Packaging & trust (make it installable and current)

**Why:** `docs/ROADMAP.md` already flags this and it gates adoption more than any feature.

- Publish wheels to PyPI (`pip install creature-lab`); verify packaged zoo/data works from an
  installed wheel outside the checkout (there's history here — see G21 in the archived
  analysis).
- Refresh onboarding proof each release: regenerate `docs/assets/demo.gif` and the zoo
  gallery (now the Phase R `index.html`).
- Calibrated baselines for **every** packaged task × backend, committed under `zoo/*/baselines/`,
  so `bench`/report regression coloring is trustworthy.
- Versioned docs + a `CHANGELOG.md`.

**Acceptance:** a fresh `pip install` in a clean venv runs `demo --no-hold` and `zoo run`;
CI builds the wheel and runs the smoke path against the installed package.

---

## Sequencing & effort

| Phase | Theme | New commands / outputs | Effort | Depends on |
| --- | --- | --- | --- | --- |
| **R** | Report upgrade (HTML, compare, reproducibility, gallery) | `report --html`, `report compare`, `gallery` HTML | **Medium** | — |
| 1 | Terrain library | terrain `TaskSpec` field, 3 zoo tasks | Medium | — |
| 2 | Robustness / portability report | `robustness`, `sim2sim` | Medium | R (report sink), backends |
| 3 | QD gallery | `archive show`, `archive export` | Small–Med | existing MAP-Elites, R |
| 4 | LLM loop sharpened | `evolve --strategy llm`, diagnosis-in-prompt | Medium | diagnosis, agents |
| 5 | Packaging & trust | PyPI wheel, baselines, changelog | Medium | all |

**Start at Phase R.** It's the user's explicit ask, it's pure composition of existing
capabilities (low risk), and Phases 2–4 all plug their results *into* it — so building the
report first makes every later phase visibly pay off. Each phase is independently shippable
and gated by its own acceptance criteria and a green `ruff` + `pytest`.

---

## What this plan deliberately does **not** add

Same discipline as the archived plan — restated because it's what keeps the two repos apart:

| Tempting item | Why not (who owns it) |
| --- | --- |
| Web dashboard / backend server | Agentarium; Viser + static HTML is enough here |
| Multi-agent arena / Studio | Agentarium's entire reason to exist |
| Leaderboard / cloud runs | Product surface, not a local tool |
| NL *challenge* generation | Agentarium (LLM challenge generation) |
| Real-time LLM torque control | Wrong altitude; too slow/expensive |
| GPU-scale RL training | Isaac Lab's competition, not this niche |
| Soft-body / voxel robots | EvoGym's niche; stay articulated-rigid |

---

## Sources

- Evolution Gym — [repo](https://github.com/EvolutionGym/evogym) ·
  [paper](https://arxiv.org/pdf/2201.09863)
- Revolve2 — [repo](https://github.com/ci-group/revolve2) ·
  [docs](https://ci-group.github.io/revolve2/)
- RoboMorph: Evolving Robot Morphology using LLMs —
  [arXiv](https://arxiv.org/abs/2407.08626) · [site](https://robomorph.github.io/)
- Debate2Create: Robot Co-design via Multi-Agent LLM Debate —
  [arXiv](https://arxiv.org/pdf/2510.25850)
- BodyGen: Efficient Embodiment Co-Design — [arXiv](https://arxiv.org/pdf/2503.00533)
- Rollout Cards: A Reproducibility Standard for Agent Research —
  [arXiv](https://arxiv.org/pdf/2605.12131)
- Open RL Benchmark — [arXiv](https://arxiv.org/html/2402.03046v1)
- robosuite — [site](https://robosuite.ai/)
</content>
</invoke>
