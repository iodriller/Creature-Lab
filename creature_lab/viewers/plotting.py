"""Metric plots for a recorded run (matplotlib, the ``viz`` extra)."""

from __future__ import annotations

from pathlib import Path

from creature_lab.schema import CreatureSpec, EpisodeTrace
from creature_lab.viewers.overlays import metric_series


def plot_metric(
    creature: CreatureSpec,
    trace: EpisodeTrace,
    metric: str,
    *,
    out: Path | None = None,
) -> Path | None:
    """Plot a metric over time. Saves a PNG if ``out`` is given, else shows a window.

    Returns the saved path (or ``None`` when shown interactively).
    """
    import matplotlib

    if out is not None:
        matplotlib.use("Agg")  # headless: render straight to a file
    import matplotlib.pyplot as plt

    times, values = metric_series(trace, creature, metric)
    figure, axes = plt.subplots(figsize=(8, 4))
    axes.plot(times, values, color="#2080d0")
    axes.set_xlabel("time (s)")
    axes.set_ylabel(metric)
    axes.set_title(f"{trace.creature_name} — {metric}")
    axes.grid(True, alpha=0.3)
    figure.tight_layout()

    if out is not None:
        figure.savefig(out, dpi=120)
        plt.close(figure)
        return out
    plt.show()
    plt.close(figure)
    return None
