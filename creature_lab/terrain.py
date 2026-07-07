"""Deterministic terrain heightfields shared across simulator backends.

Backend-agnostic grid generation so PyBullet and MuJoCo build the *same* ground
shape from the same ``TaskSpec`` — the portability contract extends to terrain,
not just creatures. Row index maps to the +x (forward) axis, column to +y.
"""

from __future__ import annotations

import math
import random

from creature_lab.schema.task import TerrainSpec, TerrainType

#: Default heightfield resolution/extent (rows/cols of cells, each cell_size meters).
DEFAULT_ROWS = 64
DEFAULT_COLS = 64
DEFAULT_CELL_SIZE = 0.1


def is_flat(terrain: TerrainSpec) -> bool:
    """Whether this terrain is the simple infinite ground plane (no heightfield needed)."""
    return terrain.type == TerrainType.PLANE


def describe_terrain(terrain: TerrainSpec) -> str:
    """One-line human-readable summary, e.g. for `inspect` and run reports."""
    friction = f"friction={terrain.friction:g}"
    if terrain.type == TerrainType.PLANE:
        return f"plane ({friction})"
    if terrain.type == TerrainType.SLOPE:
        return f"slope (angle={terrain.slope_angle:g} rad, {friction})"
    if terrain.type == TerrainType.STEPS:
        return (
            f"steps (height={terrain.step_height:g}m, length={terrain.step_length:g}m, {friction})"
        )
    if terrain.type == TerrainType.GAPS:
        return f"gaps (width={terrain.gap_width:g}m, period={terrain.gap_period:g}m, {friction})"
    if terrain.type == TerrainType.ROUGH:
        return f"rough (roughness={terrain.roughness:g}m, seed={terrain.seed}, {friction})"
    raise ValueError(f"unknown terrain type {terrain.type!r}")  # pragma: no cover


def heightfield_grid(
    terrain: TerrainSpec,
    *,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    cell_size: float = DEFAULT_CELL_SIZE,
) -> list[list[float]]:
    """A deterministic ``rows`` x ``cols`` grid of heights (m), centered at the origin.

    Only called for non-``plane`` terrain. Every terrain type is a pure function of
    ``terrain`` (plus grid resolution), so the same call on any backend produces the
    same shape.
    """
    x0 = -(rows * cell_size) / 2
    grid = [[0.0] * cols for _ in range(rows)]

    if terrain.type == TerrainType.SLOPE:
        for r in range(rows):
            height = (x0 + r * cell_size) * math.tan(terrain.slope_angle)
            grid[r] = [height] * cols
        return grid

    if terrain.type == TerrainType.STEPS:
        for r in range(rows):
            x = x0 + r * cell_size
            height = math.floor(x / terrain.step_length) * terrain.step_height
            grid[r] = [height] * cols
        return grid

    if terrain.type == TerrainType.GAPS:
        # A solid platform around the origin guarantees a creature always spawns on
        # ground, regardless of where the gap period happens to land on x=0.
        start_platform = 1.0
        for r in range(rows):
            x = x0 + r * cell_size
            in_gap = abs(x) >= start_platform and (x % terrain.gap_period) < terrain.gap_width
            grid[r] = [-10.0 if in_gap else 0.0] * cols
        return grid

    if terrain.type == TerrainType.ROUGH:
        rng = random.Random(terrain.seed)
        raw = [
            [rng.uniform(-terrain.roughness, terrain.roughness) for _ in range(cols)]
            for _ in range(rows)
        ]
        for r in range(rows):
            for c in range(cols):
                # 3x3 box blur keeps the surface driveable instead of jagged per-cell noise.
                neighbors = [
                    raw[max(0, min(rows - 1, r + dr))][max(0, min(cols - 1, c + dc))]
                    for dr in (-1, 0, 1)
                    for dc in (-1, 0, 1)
                ]
                grid[r][c] = sum(neighbors) / len(neighbors)
        return grid

    raise ValueError(f"terrain type {terrain.type!r} does not use a heightfield")


def flatten_for_heightfield_api(grid: list[list[float]]) -> list[float]:
    """Flatten ``heightfield_grid()`` for PyBullet's/MuJoCo's heightfield APIs.

    Both engines lay out their flat height array with the *second* grid axis
    (our column / +y) varying slowest and the *first* (our row / +x) fastest —
    verified empirically against both backends with a raycast/probe-body test, since
    neither engine's docs state the convention plainly. Passing a naive row-major
    flatten instead silently swaps which world axis the terrain shape varies along.
    """
    rows, cols = len(grid), len(grid[0])
    return [grid[r][c] for c in range(cols) for r in range(rows)]


def height_at(
    terrain: TerrainSpec,
    x: float,
    y: float,
    *,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    cell_size: float = DEFAULT_CELL_SIZE,
) -> float:
    """Nearest-cell terrain height (m) at world position ``(x, y)``; ``0.0`` if flat.

    For visual overlays (e.g. drawing a point on the ground) — not precise enough for
    physics, which is why the backends use the full grid instead.
    """
    if is_flat(terrain):
        return 0.0
    grid = heightfield_grid(terrain, rows=rows, cols=cols, cell_size=cell_size)
    x0 = -(rows * cell_size) / 2
    y0 = -(cols * cell_size) / 2
    r = min(max(round((x - x0) / cell_size), 0), rows - 1)
    c = min(max(round((y - y0) / cell_size), 0), cols - 1)
    return grid[r][c]


def heightfield_range(
    terrain: TerrainSpec,
    *,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    cell_size: float = DEFAULT_CELL_SIZE,
) -> tuple[float, float]:
    """``(min, max)`` height of the grid — backends use this to size/position it."""
    grid = heightfield_grid(terrain, rows=rows, cols=cols, cell_size=cell_size)
    flat = [value for row in grid for value in row]
    return min(flat), max(flat)


def normalized_heightfield_data(
    terrain: TerrainSpec,
    *,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    cell_size: float = DEFAULT_CELL_SIZE,
) -> list[float]:
    """Heights rescaled to ``[0, 1]`` and flattened for MuJoCo's ``hfield_data``."""
    grid = heightfield_grid(terrain, rows=rows, cols=cols, cell_size=cell_size)
    flat = [value for row in grid for value in row]
    lo, hi = min(flat), max(flat)
    span = max(hi - lo, 1e-6)
    return [(value - lo) / span for value in flatten_for_heightfield_api(grid)]
