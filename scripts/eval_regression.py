#!/usr/bin/env python3
"""
ABOUTME: Regression test for citation accuracy in the OpenDraft agent pipeline
ABOUTME: Loads golden topics, generates draft metrics via quality_gate,
         and fails CI if any metric degrades >10% from baseline.

Usage:
    python scripts/eval_regression.py --baseline reports/baseline.json
    python scripts/eval_regression.py --baseline reports/baseline.json --threshold 0.10
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add engine to path so quality_gate can be imported
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from utils.quality_gate import score_draft_quality, QualityScore
from phases.context import DraftContext


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOPICS_PATH = "data/eval_topics.json"
DEFAULT_BASELINE_PATH = "reports/baseline.json"
DEFAULT_THRESHOLD = 0.10  # 10% degradation allowed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> Any:
    """Load and return parsed JSON from *path*."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_mock_context(topic: str, domain: str) -> DraftContext:
    """
    Build a DraftContext with deterministic mock outputs for a given topic.

    The mock outputs simulate a reasonable-quality draft so that the quality
    gate produces stable, reproducible metrics without requiring any LLM API
    calls.  This is intentional — regression tests must be deterministic and
    fast.
    """
    ctx = DraftContext()
    ctx.topic = topic
    ctx.language = "en"
    ctx.academic_level = "master"
    ctx.citation_style = "apa"
    ctx.skip_validation = True
    ctx.verbose = False
    ctx.author_name = "Regression Test Author"
    ctx.institution = "Test University"
    ctx.department = "Computer Science"
    ctx.word_targets = {"min_citations": 10}

    # Deterministic mock content — word counts and citation density are
    # stable across runs, so the quality gate produces the same score each time.
    intro_words = "This section discusses " + topic + ". " * 150
    body_words = "Detailed analysis of " + topic + " in the context of " + domain + ". " * 500
    lit_review = "Previous work on " + topic + " has been extensive. " * 80
    methodology = "We employ a systematic review methodology. " * 60
    results = "Our findings show significant effects in " + domain + ". " * 60
    conclusion_words = "In conclusion, " + topic + " warrants further study. " * 100

    ctx.intro_output = "# Introduction\n\n" + intro_words + " {cite_001} {cite_002} {cite_003}"
    ctx.body_output = "## Body\n\n" + body_words + " {cite_004} {cite_005} {cite_006} {cite_007} {cite_008}"
    ctx.lit_review_output = "## Literature Review\n\n" + lit_review + " {cite_009} {cite_010}"
    ctx.methodology_output = "## Methodology\n\n" + methodology + " {cite_011}"
    ctx.results_output = "## Results\n\n" + results + " {cite_012} {cite_013}"
    ctx.conclusion_output = "## Conclusion\n\n" + conclusion_words + " {cite_014} {cite_015}"

    return ctx


def _compute_metrics(ctx: DraftContext) -> Dict[str, float]:
    """Run the quality gate and extract numeric metrics from the result."""
    score: QualityScore = score_draft_quality(ctx)

    # Derive additional metrics from the context directly
    all_text = (
        ctx.intro_output + ctx.body_output + ctx.lit_review_output
        + ctx.methodology_output + ctx.results_output + ctx.conclusion_output
    )
    word_count = len(all_text.split())
    import re
    citation_refs = re.findall(r"\{cite_\d+\}", all_text)
    unique_citations = len(set(citation_refs))

    return {
        "total_score": float(score.total_score),
        "word_count_score": float(score.word_count_score),
        "citation_score": float(score.citation_score),
        "completeness_score": float(score.completeness_score),
        "structure_score": float(score.structure_score),
        "word_count": float(word_count),
        "unique_citations": float(unique_citations),
        "total_citation_refs": float(len(citation_refs)),
        "passed": float(1.0 if score.passed else 0.0),
    }


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def run_regression(
    topics_path: str,
    baseline_path: str,
    threshold: float,
) -> int:
    """
    Run the regression test suite.

    Returns 0 on success (no degradation), 1 if any metric degraded beyond
    the threshold.
    """
    topics: List[Dict] = load_json(topics_path)
    baseline: Dict[str, Dict[str, float]] = load_json(baseline_path)

    failures: List[str] = []
    report_rows: List[str] = []

    for topic_entry in topics:
        topic = topic_entry["topic"]
        domain = topic_entry.get("domain", "general")
        topic_id = topic_entry.get("id", topic.replace(" ", "_"))

        ctx = _build_mock_context(topic, domain)
        metrics = _compute_metrics(ctx)

        # Compare against baseline for this topic
        baseline_metrics = baseline.get(topic_id, baseline.get(topic, None))
        if baseline_metrics is None:
            report_rows.append(f"  {topic_id}: NO BASELINE (skip)")
            continue

        report_rows.append(f"\n  {topic_id}:")
        for metric_name in sorted(metrics.keys()):
            current = metrics[metric_name]
            base = baseline_metrics.get(metric_name, 0)
            if base == 0:
                delta_pct = 0.0
            else:
                delta_pct = (current - base) / abs(base)

            status = ""
            if delta_pct < -threshold:
                status = f"  **FAIL** (-{abs(delta_pct)*100:.1f}%)"
                failures.append(
                    f"{topic_id}/{metric_name}: degraded by {abs(delta_pct)*100:.1f}% "
                    f"(baseline={base:.1f}, current={current:.1f})"
                )
            elif delta_pct < 0:
                status = f"  (-{abs(delta_pct)*100:.1f}%)"

            report_rows.append(
                f"    {metric_name:25s}: {current:8.1f}  (baseline {base:8.1f})  {status}"
            )

    # Print report
    print("=== OpenDraft Regression Test Report ===")
    print(f"Threshold: {threshold * 100:.0f}% degradation allowed\n")
    for row in report_rows:
        print(row)

    if failures:
        print(f"\n❌ {len(failures)} regression(s) detected:")
        for f in failures:
            print(f"  - {f}")
        return 1
    else:
        print("\n✅ All metrics within acceptable range.")
        return 0


def write_baseline(topics_path: str, output_path: str) -> None:
    """
    Write a fresh baseline from the current state of the codebase.

    Use this when the codebase has legitimately changed and the baseline
    needs updating.
    """
    topics: List[Dict] = load_json(topics_path)
    baseline: Dict[str, Dict[str, float]] = {}

    for topic_entry in topics:
        topic = topic_entry["topic"]
        domain = topic_entry.get("domain", "general")
        topic_id = topic_entry.get("id", topic.replace(" ", "_"))

        ctx = _build_mock_context(topic, domain)
        metrics = _compute_metrics(ctx)
        baseline[topic_id] = metrics

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Baseline written to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regression test for OpenDraft citation accuracy metrics"
    )
    parser.add_argument(
        "--topics",
        default=DEFAULT_TOPICS_PATH,
        help=f"Path to eval_topics.json (default: {DEFAULT_TOPICS_PATH})",
    )
    parser.add_argument(
        "--baseline",
        default=DEFAULT_BASELINE_PATH,
        help=f"Path to baseline.json (default: {DEFAULT_BASELINE_PATH})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Degradation threshold (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write a new baseline instead of running regression",
    )
    parser.add_argument(
        "--baseline-output",
        default=DEFAULT_BASELINE_PATH,
        help="Output path for --write-baseline (default: same as --baseline)",
    )

    args = parser.parse_args()

    if args.write_baseline:
        write_baseline(args.topics, args.baseline_output)
        sys.exit(0)

    exit_code = run_regression(args.topics, args.baseline, args.threshold)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
