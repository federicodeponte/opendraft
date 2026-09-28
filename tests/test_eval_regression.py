import json
from pathlib import Path

from scripts.eval_regression import (
    EvalTopic,
    build_report,
    compare_reports,
    count_verified_citations_from_text,
    load_topics,
    main,
    score_structure_quality,
)


SAMPLE_DRAFT = """# Citation Integrity in AI Writing

## Introduction

This paper studies source-grounded writing and citation verification in AI-assisted
research workflows. It introduces a repeatable benchmark for citation integrity
and discusses why generated drafts need automated regression checks.

## Background

Prior work shows that language models can produce fluent claims with unsupported
references. OpenDraft mitigates this by validating sources against scholarly
databases and by keeping source metadata attached to generated sections.

## Method

We evaluate drafts with fixed golden topics, a word-count target, citation
coverage, and a structure score. The evaluation includes references such as
Smith (2024) and {cite_001}.

## Analysis

The benchmark compares the current draft set against a previous baseline.
Metric drops greater than ten percent should fail CI because they indicate
potentially meaningful regressions in source quality or structure.

## Discussion

Regression checks are especially useful for prompts and agent orchestration
because changes can alter output quality without changing unit-test behavior.

## Conclusion

Golden-topic evaluation gives maintainers a stable signal for release quality.

## References

Smith, J. (2024). Citation verification for generated drafts.
https://doi.org/10.1234/example.doi
"""


def test_load_topics_accepts_objects_and_strings(tmp_path: Path) -> None:
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps([{"id": "one", "topic": "Topic One"}, "Topic Two"]))

    topics = load_topics(topics_file)

    assert [topic.id for topic in topics] == ["one", "topic-two"]
    assert topics[0].topic == "Topic One"


def test_metrics_extract_verified_citations_and_structure() -> None:
    assert count_verified_citations_from_text(SAMPLE_DRAFT) == 1
    assert score_structure_quality(SAMPLE_DRAFT) >= 80


def test_build_report_from_existing_drafts(tmp_path: Path) -> None:
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    (drafts_dir / "citation-integrity.md").write_text(SAMPLE_DRAFT)

    report = build_report([EvalTopic(id="citation-integrity", topic="Citation integrity")], drafts_dir)

    assert report["aggregate"]["word_count"] > 100
    assert report["aggregate"]["verified_citations"] == 1
    assert report["topics"][0]["draft_path"].endswith("citation-integrity.md")


def test_compare_reports_fails_on_metric_degradation() -> None:
    baseline = {
        "aggregate": {"word_count": 1000, "verified_citations": 10, "structure_quality": 90},
        "topics": [
            {"topic_id": "one", "word_count": 1000, "verified_citations": 10, "structure_quality": 90}
        ],
    }
    current = {
        "aggregate": {"word_count": 800, "verified_citations": 10, "structure_quality": 90},
        "topics": [
            {"topic_id": "one", "word_count": 1000, "verified_citations": 8, "structure_quality": 90}
        ],
    }

    regressions = compare_reports(baseline, current, max_degradation=0.10)

    assert {item["metric"] for item in regressions} == {"word_count", "verified_citations"}


def test_main_writes_report(tmp_path: Path) -> None:
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps([{"id": "citation-integrity", "topic": "Citation integrity"}]))
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    (drafts_dir / "citation-integrity.md").write_text(SAMPLE_DRAFT)
    output = tmp_path / "report.json"

    exit_code = main(["--topics", str(topics_file), "--drafts-dir", str(drafts_dir), "--output", str(output)])

    assert exit_code == 0
    data = json.loads(output.read_text())
    assert data["passed"] is True
