# Known Issues

Latent gaps and deliberate limitations found during code review, tracked here so they
aren't lost and don't need re-discovering. Update this table in the same change that
fixes or knowingly accepts an item — see [`CHANGELOG.md`](../CHANGELOG.md) for what has
already shipped.

| Item | Area | Status | Notes |
| --- | --- | --- | --- |
| Diagnosis is not terrain-aware | `diagnosis.py` | Open (low priority) | `com_height_std` and the upright/fall check are calibrated for flat ground. A creature climbing a steep or long `slope`/`steps` terrain will show rising/falling CoM height and could false-flag `com_instability` even when the gait is healthy — the signal doesn't currently subtract the terrain height profile at the root's (x, y). Not observed at today's zoo task magnitudes (`slope_angle<=0.15`, `step_height<=0.05`); worth fixing before adding steeper terrain tasks. |
| Non-flat terrain has a finite 6.4 m extent | `terrain.py` | Open (low priority) | The heightfield grid is `DEFAULT_ROWS x DEFAULT_COLS x DEFAULT_CELL_SIZE` = 64×64×0.1 m, centered at the origin. A task whose creature can travel past ~±3.2 m on non-flat terrain walks off the edge of the generated ground with no warning (PyBullet/MuJoCo heightfields have no ground beyond the grid). None of the packaged zoo tasks travel that far, so it hasn't been hit in practice. If longer non-flat tasks are added, either raise `DEFAULT_ROWS`/`DEFAULT_COLS` or add a `validate_episode_inputs` warning when a task's expected travel could exceed the extent. |
| Terrain grid assumes `rows == cols` | `terrain.py` | Open (low priority) | `flatten_for_heightfield_api`'s row/column convention was verified empirically against both backends using a **square** grid (`DEFAULT_ROWS == DEFAULT_COLS == 64`). The transpose logic (`heightfield_grid`'s row = +x axis) has not been re-verified for a non-square grid, where a naive transpose could silently swap which world axis the terrain varies along. Not a live bug — no code path currently calls `heightfield_grid`/`normalized_heightfield_data` with `rows != cols` — but a future caller that does needs to re-run the raycast/probe-body verification from the Phase 1 implementation (see `CHANGELOG.md`) before trusting the result. |
| CI does not build or install-test the wheel | `.github/workflows/ci.yml` | Open (low-medium priority) | Phase 5 verified "packaged data works from an installed wheel outside the checkout" by hand (`uv build`, install into a clean venv, run `zoo run` from a foreign directory). That check is not automated, so a future change that breaks packaging (e.g. a new data directory not picked up by hatch, or a wheel that omits a `zoo/*/baselines/*.json` file) could regress silently. Add a CI step that builds the wheel, installs it into a fresh venv, and runs a smoke command (`zoo run` or `doctor`) against the installed package, not the checkout. |

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
