"""Tests for debug-overlay analysis series, plotting, and the viewer overlays."""

import pytest

from creature_lab.schema import CreatureSpec, EpisodeTrace
from creature_lab.viewers.overlays import (
    center_of_mass_trail,
    joint_energy_series,
    metric_series,
    root_path,
)

_CREATURE = CreatureSpec.model_validate(
    {
        "name": "pair",
        "parts": [
            {"id": "a", "shape": "box", "size": [1, 1, 1], "mass": 3.0},
            {"id": "b", "shape": "sphere", "radius": 0.5, "mass": 1.0},
        ],
        "joints": [{"id": "j", "parent": "a", "child": "b", "type": "fixed"}],
    }
)


def _trace() -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": "r",
            "creature_name": "pair",
            "task_name": "t",
            "backend": "x",
            "score": 1.0,
            "frames": [
                {
                    "t": 0.0,
                    "parts": {"a": {"position": [0, 0, 0]}, "b": {"position": [4, 0, 2]}},
                    "joint_angles": {"j": 0.0},
                    "score": 0.0,
                },
                {
                    "t": 0.1,
                    "parts": {"a": {"position": [0, 0, 0]}, "b": {"position": [4, 0, 2]}},
                    "joint_angles": {"j": 0.5},
                    "score": 1.0,
                },
            ],
        }
    )


def test_center_of_mass_is_mass_weighted():
    com = center_of_mass_trail(_CREATURE, _trace())
    # x = (3*0 + 1*4)/4 = 1.0 ; z = (3*0 + 1*2)/4 = 0.5
    assert com[0] == pytest.approx((1.0, 0.0, 0.5))


def test_root_path_follows_the_root_part():
    path = root_path(_CREATURE, _trace())  # 'a' is the root (not a joint child)
    assert path == [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]


def test_joint_energy_series_is_squared_delta():
    assert joint_energy_series(_trace()) == [0.0, pytest.approx(0.25)]


def test_metric_series_known_metrics():
    times, values = metric_series(_trace(), _CREATURE, "score")
    assert times == [0.0, 0.1]
    assert values == [0.0, 1.0]


def test_metric_series_unknown_raises():
    with pytest.raises(ValueError, match="unknown metric"):
        metric_series(_trace(), _CREATURE, "bogus")


def test_plot_metric_saves_png(tmp_path):
    pytest.importorskip("matplotlib")
    from creature_lab.viewers.plotting import plot_metric

    out = tmp_path / "energy.png"
    result = plot_metric(_CREATURE, _trace(), "joint_energy", out=out)
    assert result == out
    assert out.exists() and out.stat().st_size > 0


def test_debug_overlays_render_headless():
    viser = pytest.importorskip("viser")
    from creature_lab.viewers.viser_viewer import add_debug_overlays, build_scene

    server = viser.ViserServer(port=8133, verbose=False)
    try:
        build_scene(server, _CREATURE, task=None, max_contacts=1)
        add_debug_overlays(server, _CREATURE, _trace())  # must not raise
    finally:
        server.stop()


def test_compare_traces_runs_headless():
    pytest.importorskip("viser")
    from creature_lab.viewers.viser_viewer import compare_traces

    # hold=False returns after one pass; high fps keeps it fast.
    compare_traces(
        _CREATURE, _trace(), _CREATURE, _trace(), gap=1.0, fps=1000.0, port=8134, hold=False
    )
