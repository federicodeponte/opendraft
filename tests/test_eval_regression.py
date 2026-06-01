#!/usr/bin/env python3
"""Tests for the regression evaluation script."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from eval_regression import (  # noqa: E402
    compare_reports,
    extract_metrics,
    load_topics,
    metric_degradation,
)


def test_load_topics_requires_five_topics(tmp_path):
    topics_path = tmp_path / "topics.json"
    topics_path.write_text(
        json.dumps([{"id": f"topic_{i}", "topic": f"Topic {i}"} for i in range(5)]),
        encoding="utf-8",
    )

    topics = load_topics(topics_path)

    assert len(topics) == 5
    assert topics[0].academic_level == "research_paper"


def test_extract_metrics_from_generated_output(tmp_path):
    output_dir = tmp_path / "output"
    exports_dir = output_dir / "exports"
    research_dir = output_dir / "research"
    exports_dir.mkdir(parents=True)
    research_dir.mkdir(parents=True)

    (exports_dir / "sample.md").write_text(
        "# Introduction\n\n"
        "This is a paragraph with a citation {cite_001}.\n\n"
        "## Methods\n\n"
        "This is another long paragraph that gives the structure scorer enough text.\n\n"
        "## References\n\n"
        "Reference list.",
        encoding="utf-8",
    )
    (research_dir / "bibliography.json").write_text(
        json.dumps(
            {
                "citations": [
                    {
                        "id": "cite_001",
                        "authors": ["Doe, Jane"],
                        "year": 2024,
                        "title": "Example Paper",
                        "doi": "10.1000/example",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    metrics = extract_metrics(output_dir)

    assert metrics["word_count"] > 0
    assert metrics["unique_citations"] == 1
    assert metrics["verified_citations"] == 1
    assert metrics["verified_citation_rate"] == 1.0


def test_metric_degradation_handles_zero_baseline():
    assert metric_degradation(0, 0) == 0
    assert metric_degradation(0, 1) == 0
    assert metric_degradation(0, -1) == 1


def test_compare_reports_flags_degradation():
    baseline = {
        "topics": {
            "topic": {
                "metrics": {
                    "word_count": 100,
                    "unique_citations": 10,
                    "verified_citations": 10,
                    "verified_citation_rate": 1.0,
                    "structure_quality": 100,
                }
            }
        }
    }
    current = {
        "topics": {
            "topic": {
                "metrics": {
                    "word_count": 80,
                    "unique_citations": 10,
                    "verified_citations": 10,
                    "verified_citation_rate": 1.0,
                    "structure_quality": 100,
                }
            }
        }
    }

    failures = compare_reports(baseline, current, threshold=0.10)

    assert failures == [
        {
            "topic_id": "topic",
            "metric": "word_count",
            "baseline": 100.0,
            "current": 80.0,
            "degradation": 0.2,
        }
    ]
