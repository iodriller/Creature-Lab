# Known Issues

Latent gaps and deliberate limitations found during code review, tracked here so they
aren't lost and don't need re-discovering. Update this table in the same change that
fixes or knowingly accepts an item — see [`CHANGELOG.md`](../CHANGELOG.md) for what has
already shipped.

| Item | Area | Status | Notes |
| --- | --- | --- | --- |
| Diagnosis is not terrain-aware | `diagnosis.py` | Open (low priority) | `com_height_std` and the upright/fall check are calibrated for flat ground. A creature climbing a steep or long `slope`/`steps` terrain will show rising/falling CoM height and could false-flag `com_instability` even when the gait is healthy — the signal doesn't currently subtract the terrain height profile at the root's (x, y). Not observed at today's zoo task magnitudes (`slope_angle<=0.15`, `step_height<=0.05`); worth fixing before adding steeper terrain tasks. |
| Non-flat terrain has a finite 6.4 m extent | `terrain.py`, `validation.py` | Partially closed | The heightfield grid is `DEFAULT_ROWS x DEFAULT_COLS x DEFAULT_CELL_SIZE` = 64×64×0.1 m, centered at the origin; a creature can walk off the edge with no ground beyond it. `validate_episode_inputs` now warns when a **target** lies outside that extent on non-flat terrain (a concrete, checkable case). It cannot warn for target-less locomotion tasks (e.g. `crawl_forward`-style) since there's no way to predict expected travel distance from the spec alone — that part stays open. |
| Terrain grid assumes `rows == cols` | `terrain.py` | Closed | `flatten_for_heightfield_api`'s row/column convention was verified empirically (a PyBullet raycast probe, a MuJoCo free-falling probe body) only for a **square** grid. `terrain.py` now asserts `DEFAULT_ROWS == DEFAULT_COLS` at import time, so changing the constants to a non-square shape fails loudly instead of silently swapping which world axis the terrain varies along. |
| CI does not build or install-test the wheel | `.github/workflows/ci.yml` | Closed | CI now builds the wheel, installs it into a fresh venv, and runs `doctor` + `zoo run` against the installed package (not the checkout) on every push/PR — the same check Phase 5 ran by hand. |

## Deliberate, accepted limitations (not bugs)

These are documented design choices, not gaps to close:

- **Exact physics is backend-dependent.** PyBullet and MuJoCo simulate the same
  `CreatureSpec`/`TaskSpec` with different solvers/contact models; scores and trajectories
  can differ substantially for the same open-loop gait (see `sim2sim`, and the packaged
  `baselines/<task>.mujoco.json` vs. `baselines/<task>.json` pairs). This is the stated
  portability contract, not something to eliminate.
- **`gaps` terrain uses a deep pit (`-10.0 m`), not a true hole.** Neither backend's
  heightfield primitive supports an actual discontinuity in the ground; a very deep pit is
  a good-enough stand-in for "impassable" at creature scale.
