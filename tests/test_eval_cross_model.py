"""Tests for the cross-model evaluation report and metric extraction."""

import json

import pytest

from scripts.eval_cross_model import (
    EvaluationResult,
    citation_metrics,
    markdown_report,
    parse_providers,
    tracked_cost,
)


def test_citation_metrics_count_only_multi_source_confirmation(tmp_path):
    bibliography = tmp_path / "bibliography.json"
    bibliography.write_text(
        json.dumps(
            {
                "citations": [
                    {"verification_status": "multi_source_confirmed"},
                    {"verification_status": "single_source"},
                    {"verification_status": "multi_source_confirmed"},
                    {},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert citation_metrics(bibliography) == (2, 4, 50.0)


def test_citation_metrics_handle_missing_or_empty_files(tmp_path):
    assert citation_metrics(tmp_path / "missing.json") == (0, 0, None)
    empty = tmp_path / "empty.json"
    empty.write_text('{"citations": []}', encoding="utf-8")
    assert citation_metrics(empty) == (0, 0, None)


def test_tracked_cost_is_none_for_unknown_pricing(tmp_path):
    usage = tmp_path / "token_usage.json"
    usage.write_text('{"total_cost_usd": 1.25}', encoding="utf-8")

    assert tracked_cost(usage, "unknown-model") is None
    assert tracked_cost(usage, "gpt-4.1-nano") == 1.25


def test_markdown_report_contains_metrics_and_escaped_error():
    report = markdown_report(
        "A | B",
        [
            EvaluationResult(
                provider="gemini",
                model="gemini-test",
                status="ok",
                verified_citations=3,
                total_citations=4,
                verification_rate=75.0,
                generation_seconds=2.5,
                estimated_cost_usd=0.0123,
            ),
            EvaluationResult(
                provider="openai",
                model="gpt-test",
                status="failed",
                error="RuntimeError: bad | response",
            ),
        ],
    )

    assert "**Topic:** A \\| B" in report
    assert "3/4 | 75.0% | 2.5s | $0.0123 | ok" in report
    assert "bad \\| response" in report


def test_parse_providers_validates_and_preserves_order():
    assert parse_providers("openai, gemini") == ["openai", "gemini"]
    with pytest.raises(Exception, match="unknown provider"):
        parse_providers("gemini,other")
