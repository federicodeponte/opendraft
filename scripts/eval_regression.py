#!/usr/bin/env python3
"""Run regression checks for OpenDraft generated drafts.

The script generates drafts for a fixed golden topic set, extracts stable output
metrics, and compares them to a baseline report. It exits non-zero when any
metric degrades by more than the configured threshold.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "engine"

if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


DEFAULT_TOPICS_PATH = REPO_ROOT / "data" / "eval_topics.json"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"
DEFAULT_OUTPUT_ROOT = DEFAULT_REPORTS_DIR / "eval_regression_outputs"
DEFAULT_REPORT_PATH = DEFAULT_REPORTS_DIR / "eval_regression_report.json"
DEFAULT_THRESHOLD = 0.10

METRIC_KEYS = (
    "word_count",
    "unique_citations",
    "verified_citations",
    "verified_citation_rate",
    "structure_quality",
)


@dataclass(frozen=True)
class EvalTopic:
    """A golden evaluation topic."""

    id: str
    topic: str
    academic_level: str = "research_paper"
    language: str = "en"


def slugify(value: str) -> str:
    """Convert a value to a stable filesystem slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", slug).strip("_") or "topic"


def load_topics(path: Path) -> list[EvalTopic]:
    """Load the golden topic set from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")

    topics: list[EvalTopic] = []
    for index, item in enumerate(data, start=1):
        if isinstance(item, str):
            topic = item.strip()
            if not topic:
                raise ValueError(f"Topic #{index} is empty")
            topics.append(EvalTopic(id=f"topic_{index:02d}", topic=topic))
            continue

        if not isinstance(item, dict):
            raise ValueError(f"Topic #{index} must be a string or object")

        topic_text = str(item.get("topic", "")).strip()
        if not topic_text:
            raise ValueError(f"Topic #{index} is missing 'topic'")

        topic_id = str(item.get("id") or slugify(topic_text[:60]))
        topics.append(
            EvalTopic(
                id=slugify(topic_id),
                topic=topic_text,
                academic_level=str(item.get("academic_level", "research_paper")),
                language=str(item.get("language", "en")),
            )
        )

    if len(topics) != 5:
        raise ValueError(f"Expected exactly 5 golden topics, found {len(topics)}")

    return topics


def find_final_markdown(output_dir: Path) -> Path:
    """Find the final exported markdown for a generated draft."""
    exports_dir = output_dir / "exports"
    candidates = [
        path
        for path in exports_dir.glob("*.md")
        if path.name != "INTERMEDIATE_DRAFT.md"
    ]
    if candidates:
        return max(candidates, key=lambda path: path.stat().st_mtime)

    intermediate = exports_dir / "INTERMEDIATE_DRAFT.md"
    if intermediate.exists():
        return intermediate

    draft_files = [
        path
        for path in sorted((output_dir / "drafts").glob("*.md"))
        if path.name != "_combined_for_eval.md"
    ]
    if draft_files:
        combined = output_dir / "drafts" / "_combined_for_eval.md"
        combined.write_text(
            "\n\n".join(path.read_text(encoding="utf-8") for path in draft_files),
            encoding="utf-8",
        )
        return combined

    raise FileNotFoundError(f"No generated markdown found under {output_dir}")


def load_bibliography(output_dir: Path) -> dict[str, Any]:
    """Load bibliography data if the generation produced one."""
    path = output_dir / "research" / "bibliography.json"
    if not path.exists():
        return {"citations": [], "metadata": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def count_words(markdown: str) -> int:
    """Count human-readable words in markdown output."""
    without_code = re.sub(r"```.*?```", " ", markdown, flags=re.DOTALL)
    return len(re.findall(r"\b[\w'-]+\b", without_code))


def structure_quality(markdown: str) -> int:
    """Score basic markdown structure from 0 to 100."""
    score = 0
    headers = re.findall(r"^#{1,3}\s+\S.*$", markdown, flags=re.MULTILINE)
    paragraphs = [part for part in markdown.split("\n\n") if len(part.strip()) > 80]

    score += min(40, len(headers) * 8)
    score += min(40, len(paragraphs) * 4)
    if re.search(r"\b(references|bibliography)\b", markdown, flags=re.IGNORECASE):
        score += 20

    return min(score, 100)


def verified_citation_count(citations: list[dict[str, Any]]) -> int:
    """Count citations with enough metadata to be considered verifiable."""
    verified = 0
    for citation in citations:
        title = str(citation.get("title") or "").strip()
        authors = citation.get("authors") or []
        year = citation.get("year")
        locator = citation.get("doi") or citation.get("url")
        if title and authors and year and locator:
            verified += 1
    return verified


def extract_metrics(output_dir: Path) -> dict[str, float | int]:
    """Extract comparable regression metrics from one generated draft."""
    markdown = find_final_markdown(output_dir).read_text(encoding="utf-8")
    bibliography = load_bibliography(output_dir)
    citations = bibliography.get("citations") or []
    if not isinstance(citations, list):
        citations = []

    citation_refs = set(re.findall(r"\{cite_\d+\}", markdown))
    verified = verified_citation_count(citations)
    total_citations = len(citations)

    return {
        "word_count": count_words(markdown),
        "unique_citations": len(citation_refs) or total_citations,
        "verified_citations": verified,
        "verified_citation_rate": round(verified / total_citations, 4) if total_citations else 0.0,
        "structure_quality": structure_quality(markdown),
    }


def generate_topic(topic: EvalTopic, output_dir: Path) -> None:
    """Generate one draft for an evaluation topic."""
    from draft_generator import generate_draft

    generate_draft(
        topic=topic.topic,
        language=topic.language,
        academic_level=topic.academic_level,
        output_dir=output_dir,
        skip_validation=True,
        verbose=False,
    )


def build_report(topics: list[EvalTopic], output_root: Path, reuse_outputs: bool) -> dict[str, Any]:
    """Generate drafts if needed and build the current regression report."""
    results: dict[str, Any] = {}
    output_root.mkdir(parents=True, exist_ok=True)

    for topic in topics:
        topic_output = output_root / topic.id
        if topic_output.exists() and not reuse_outputs:
            shutil.rmtree(topic_output)
        if not topic_output.exists():
            generate_topic(topic, topic_output)

        results[topic.id] = {
            "topic": topic.topic,
            "academic_level": topic.academic_level,
            "language": topic.language,
            "output_dir": str(topic_output),
            "metrics": extract_metrics(topic_output),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold": DEFAULT_THRESHOLD,
        "topics": results,
    }


def metric_degradation(baseline_value: float, current_value: float) -> float:
    """Return proportional metric degradation, or 0 when not degraded."""
    if baseline_value <= 0:
        return 0.0 if current_value >= baseline_value else 1.0
    return max(0.0, (baseline_value - current_value) / baseline_value)


def compare_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    threshold: float,
) -> list[dict[str, Any]]:
    """Compare current metrics against baseline and return failures."""
    failures: list[dict[str, Any]] = []
    baseline_topics = baseline.get("topics", {})
    current_topics = current.get("topics", {})

    for topic_id, current_topic in current_topics.items():
        baseline_topic = baseline_topics.get(topic_id)
        if not baseline_topic:
            failures.append({"topic_id": topic_id, "error": "missing baseline topic"})
            continue

        baseline_metrics = baseline_topic.get("metrics", {})
        current_metrics = current_topic.get("metrics", {})
        for metric in METRIC_KEYS:
            baseline_value = float(baseline_metrics.get(metric, 0))
            current_value = float(current_metrics.get(metric, 0))
            degradation = metric_degradation(baseline_value, current_value)
            if degradation > threshold:
                failures.append(
                    {
                        "topic_id": topic_id,
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "degradation": round(degradation, 4),
                    }
                )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenDraft regression evaluation")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS_PATH)
    parser.add_argument("--baseline", type=Path, help="Baseline report JSON to compare against")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--reuse-outputs", action="store_true", help="Reuse existing generated drafts")
    parser.add_argument("--write-baseline", action="store_true", help="Write current report without comparing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.baseline and not args.write_baseline:
        print("--baseline is required unless --write-baseline is used", file=sys.stderr)
        return 2

    topics = load_topics(args.topics)
    report = build_report(topics, args.output_root, args.reuse_outputs)
    report["threshold"] = args.threshold

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.write_baseline:
        print(f"Baseline written to {args.output}")
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    failures = compare_reports(baseline, report, args.threshold)
    if failures:
        print("Regression evaluation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"Regression evaluation passed. Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
