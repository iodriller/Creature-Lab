"""Tests for the deterministic, backend-shared terrain heightfields (Phase 1)."""

from __future__ import annotations

import pytest

from creature_lab.schema.task import TerrainSpec
from creature_lab.terrain import (
    describe_terrain,
    flatten_for_heightfield_api,
    height_at,
    heightfield_grid,
    heightfield_range,
    is_flat,
    normalized_heightfield_data,
)


def test_is_flat_only_for_plane():
    assert is_flat(TerrainSpec())
    assert not is_flat(TerrainSpec(type="slope"))


def test_plane_terrain_has_no_heightfield():
    with pytest.raises(ValueError):
        heightfield_grid(TerrainSpec())


def test_heightfield_grid_is_deterministic():
    terrain = TerrainSpec(type="rough", roughness=0.05, seed=3)
    assert heightfield_grid(terrain, rows=8, cols=8) == heightfield_grid(terrain, rows=8, cols=8)


def test_rough_terrain_different_seeds_differ():
    a = heightfield_grid(TerrainSpec(type="rough", seed=1), rows=8, cols=8)
    b = heightfield_grid(TerrainSpec(type="rough", seed=2), rows=8, cols=8)
    assert a != b


def test_slope_increases_along_forward_axis():
    grid = heightfield_grid(TerrainSpec(type="slope", slope_angle=0.2), rows=8, cols=4)
    assert grid[-1][0] > grid[0][0]


def test_steps_form_a_staircase():
    terrain = TerrainSpec(type="steps", step_height=0.1, step_length=1.0)
    heights = [row[0] for row in heightfield_grid(terrain, rows=40, cols=2, cell_size=0.1)]
    assert len(set(heights)) > 1
    assert heights == sorted(heights)  # monotonically rising along +x


def test_gaps_have_a_solid_start_platform():
    terrain = TerrainSpec(type="gaps", gap_width=0.5, gap_period=1.0)
    grid = heightfield_grid(terrain, rows=64, cols=2, cell_size=0.1)
    mid = len(grid) // 2  # x ~= 0
    assert grid[mid][0] == 0.0


def test_gaps_produce_a_deep_pit_further_out():
    terrain = TerrainSpec(type="gaps", gap_width=0.5, gap_period=1.0)
    grid = heightfield_grid(terrain, rows=64, cols=2, cell_size=0.1)
    assert any(value < -1.0 for row in grid for value in row)


def test_gap_width_must_be_less_than_gap_period():
    with pytest.raises(ValueError):
        TerrainSpec(type="gaps", gap_width=1.0, gap_period=1.0)


def test_heightfield_range_matches_grid_extremes():
    terrain = TerrainSpec(type="steps", step_height=0.1, step_length=1.0)
    grid = heightfield_grid(terrain, rows=16, cols=4)
    flat = [v for row in grid for v in row]
    assert heightfield_range(terrain, rows=16, cols=4) == (min(flat), max(flat))


def test_normalized_heightfield_data_is_flattened_and_in_unit_range():
    terrain = TerrainSpec(type="rough", roughness=0.1, seed=5)
    data = normalized_heightfield_data(terrain, rows=16, cols=16)
    assert len(data) == 16 * 16
    assert all(0.0 <= v <= 1.0 for v in data)


def test_flatten_for_heightfield_api_varies_row_index_fastest():
    grid = [[r * 10 + c for c in range(3)] for r in range(2)]  # rows=2, cols=3

    flat = flatten_for_heightfield_api(grid)

    assert flat == [grid[r][c] for c in range(3) for r in range(2)]
    assert flat[0] == grid[0][0]
    assert flat[1] == grid[1][0]  # the next element steps along rows, not columns


def test_normalized_heightfield_data_is_constant_for_a_degenerate_grid():
    # A zero-angle slope is all-zero everywhere; must not divide by zero.
    terrain = TerrainSpec(type="slope", slope_angle=0.0)
    data = normalized_heightfield_data(terrain, rows=4, cols=4)
    assert data == [0.0] * 16


def test_height_at_is_zero_for_flat_terrain():
    assert height_at(TerrainSpec(), 3.0, -2.0) == 0.0


def test_height_at_matches_slope_formula():
    import math

    terrain = TerrainSpec(type="slope", slope_angle=0.3)
    # Nearest-cell lookup, so allow one cell's worth of tolerance (default cell_size=0.1).
    assert height_at(terrain, 2.0, 0.0) == pytest.approx(2.0 * math.tan(0.3), abs=0.05)


def test_height_at_clamps_out_of_range_coordinates():
    terrain = TerrainSpec(type="slope", slope_angle=0.2)
    # Far outside the 6.4m grid extent; must clamp to an edge cell, not raise or wrap.
    far = height_at(terrain, 1000.0, 1000.0)
    edge = height_at(terrain, 3.15, 0.0)
    assert far == edge


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "plane"},
        {"type": "slope", "slope_angle": 0.2},
        {"type": "steps", "step_height": 0.05, "step_length": 0.4},
        {"type": "gaps", "gap_width": 0.2, "gap_period": 1.0},
        {"type": "rough", "roughness": 0.03, "seed": 2},
    ],
)
def test_describe_terrain_mentions_the_type_and_friction(kwargs):
    terrain = TerrainSpec(**kwargs, friction=0.7)
    description = describe_terrain(terrain)
    assert kwargs["type"] in description
    assert "friction=0.7" in description
