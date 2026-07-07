"""Tests for the self-contained HTML run/comparison/gallery reports (Phase R)."""

from __future__ import annotations

import pytest

from creature_lab.reports import build_comparison, build_report
from creature_lab.reports_html import (
    comparison_to_html,
    gallery_card_html,
    gallery_index_html,
    report_to_html,
)
from creature_lab.runs import save_run
from creature_lab.schema import CreatureSpec, EpisodeTrace, TaskSpec


def _creature() -> CreatureSpec:
    return CreatureSpec.model_validate(
        {
            "name": "test_bot",
            "parts": [{"id": "torso", "shape": "box", "size": [0.4, 0.2, 0.1], "mass": 1.0}],
        }
    )


def _task() -> TaskSpec:
    return TaskSpec.model_validate({"name": "crawl_forward", "duration": 1.0})


def _trace(run_id: str, score: float, dx: float) -> EpisodeTrace:
    return EpisodeTrace.model_validate(
        {
            "run_id": run_id,
            "creature_name": "test_bot",
            "task_name": "crawl_forward",
            "backend": "pybullet",
            "score": score,
            "frames": [
                {"t": 0.0, "parts": {"torso": {"position": [0, 0, 0]}}, "score": 0.0},
                {"t": 1.0, "parts": {"torso": {"position": [dx, 0, 0]}}, "score": score},
            ],
        }
    )


def _report_and_run_dir(tmp_path, run_id: str, score: float, dx: float):
    runs_dir = tmp_path / "runs"
    run_dir = save_run(_creature(), _trace(run_id, score, dx), runs_dir=runs_dir, task=_task())
    return build_report(run_dir), run_dir


def test_report_to_html_has_no_external_urls_and_key_sections(tmp_path):
    report, run_dir = _report_and_run_dir(tmp_path, "run1", 1.0, 1.0)
    trace = EpisodeTrace.model_validate_json((run_dir / "trace.json").read_text())

    page = report_to_html(report, trace, _creature(), embed_media=False)

    assert "http://" not in page
    assert "https://" not in page
    assert "Score breakdown" in page
    assert "Reproducibility" in page
    assert page.count("<svg") >= 3  # 3 signal sparklines + the root-path plot


def test_report_to_html_degrades_gracefully_without_a_creature(tmp_path):
    report, run_dir = _report_and_run_dir(tmp_path, "run1", 1.0, 1.0)
    trace = EpisodeTrace.model_validate_json((run_dir / "trace.json").read_text())

    page = report_to_html(report, trace, None, embed_media=False)

    assert "root path not rendered" in page


def test_report_to_html_can_embed_a_gif(tmp_path):
    pytest.importorskip("pybullet")
    pytest.importorskip("imageio")
    report, run_dir = _report_and_run_dir(tmp_path, "run1", 1.0, 1.0)
    trace = EpisodeTrace.model_validate_json((run_dir / "trace.json").read_text())

    page = report_to_html(report, trace, _creature(), embed_media=True)

    assert "data:image/gif;base64," in page


def test_build_comparison_computes_signed_deltas(tmp_path):
    report_a, _ = _report_and_run_dir(tmp_path / "a", "run_a", 0.5, 0.5)
    report_b, _ = _report_and_run_dir(tmp_path / "b", "run_b", 1.5, 1.5)

    comparison = build_comparison(report_a, report_b)

    assert comparison["score_delta"] == pytest.approx(1.0)
    assert comparison["signals"]["forward_displacement"]["delta"] == pytest.approx(1.0)


def test_comparison_to_html_overlays_paths_and_has_no_external_urls(tmp_path):
    report_a, run_dir_a = _report_and_run_dir(tmp_path / "a", "run_a", 0.5, 0.5)
    report_b, run_dir_b = _report_and_run_dir(tmp_path / "b", "run_b", 1.5, 1.5)
    comparison = build_comparison(report_a, report_b)
    trace_a = EpisodeTrace.model_validate_json((run_dir_a / "trace.json").read_text())
    trace_b = EpisodeTrace.model_validate_json((run_dir_b / "trace.json").read_text())

    page = comparison_to_html(
        report_a,
        report_b,
        comparison,
        creature_a=_creature(),
        trace_a=trace_a,
        creature_b=_creature(),
        trace_b=trace_b,
    )

    assert "http://" not in page
    assert "https://" not in page
    assert "Signal deltas" in page
    assert "1.0000" in page


def test_comparison_to_html_degrades_without_creatures():
    report_a = {"run_id": "run_a", "score": 0.5}
    report_b = {"run_id": "run_b", "score": 1.5}
    comparison = build_comparison(
        {**report_a, "summary": {"forward_displacement": 0.5}},
        {**report_b, "summary": {"forward_displacement": 1.5}},
    )

    page = comparison_to_html(report_a, report_b, comparison)

    assert "No creature.json available" in page


def test_gallery_card_html_shows_baseline_delta():
    card = gallery_card_html(
        "quadruped", "crawl_forward", {"best_score": 0.5}, 0.6, "quadruped.gif", "a note"
    )

    assert "quadruped.gif" in card
    assert "0.6000" in card
    assert "0.5000" in card
    assert "a note" in card


def test_gallery_card_html_without_baseline_or_media():
    card = gallery_card_html("worm", "crawl_forward", None, None, None, "a note")

    assert "worm" in card
    assert "<img" not in card


def test_gallery_index_html_wraps_cards():
    page = gallery_index_html(["<div>card-a</div>", "<div>card-b</div>"])

    assert "card-a" in page and "card-b" in page
    assert "Creature Zoo Gallery" in page
