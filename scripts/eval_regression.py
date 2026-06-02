#!/usr/bin/env python3
"""Regression evaluation for OpenDraft golden-topic drafts.

The script can reuse existing draft artifacts for lightweight CI, or generate
fresh drafts when a generation command is supplied.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TOPICS = Path("data/eval_topics.json")
DEFAULT_OUTPUT = Path("reports/regression_current.json")
DEFAULT_DRAFTS_DIR = Path("reports/eval_drafts")
DEFAULT_GENERATE_COMMAND = "opendraft {topic_quoted} --output {output_dir_quoted}"
REGRESSION_METRICS = ("word_count", "verified_citations", "structure_quality")


@dataclass(frozen=True)
class EvalTopic:
    id: str
    topic: str
    level: str = "research_paper"
    blurb: str | None = None


@dataclass
class TopicMetrics:
    topic_id: str
    topic: str
    draft_path: str
    word_count: int
    citation_count: int
    verified_citations: int
    structure_quality: float


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "topic"


def load_topics(path: Path) -> list[EvalTopic]:
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} must contain a non-empty list of topics")

    topics: list[EvalTopic] = []
    for index, item in enumerate(data, start=1):
        if isinstance(item, str):
            topics.append(EvalTopic(id=slugify(item), topic=item))
            continue
        if not isinstance(item, dict) or "topic" not in item:
            raise ValueError(f"Topic #{index} must be a string or object with a 'topic' field")
        topic = str(item["topic"])
        topics.append(
            EvalTopic(
                id=str(item.get("id") or slugify(topic)),
                topic=topic,
                level=str(item.get("level", "research_paper")),
                blurb=item.get("blurb"),
            )
        )
    return topics


def find_draft_file(drafts_dir: Path, topic: EvalTopic) -> Path | None:
    slug = topic.id or slugify(topic.topic)
    candidates = [
        drafts_dir / f"{slug}.md",
        drafts_dir / f"{slug}.txt",
        drafts_dir / slug / "final.md",
        drafts_dir / slug / "draft.md",
        drafts_dir / slug / "paper.md",
        drafts_dir / slug / "output.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    topic_dir = drafts_dir / slug
    if topic_dir.is_dir():
        ranked = sorted(
            topic_dir.rglob("*.md"),
            key=lambda path: (
                not any(token in path.name.lower() for token in ("final", "draft", "paper")),
                len(path.parts),
                path.name,
            ),
        )
        if ranked:
            return ranked[0]

    return None


def run_generation(topic: EvalTopic, drafts_dir: Path, command_template: str) -> None:
    output_dir = drafts_dir / topic.id
    output_dir.mkdir(parents=True, exist_ok=True)
    command = command_template.format(
        topic=topic.topic,
        topic_quoted=shlex.quote(topic.topic),
        topic_id=topic.id,
        output_dir=str(output_dir),
        output_dir_quoted=shlex.quote(str(output_dir)),
        level=topic.level,
        blurb=topic.blurb or "",
        blurb_quoted=shlex.quote(topic.blurb or ""),
    )
    subprocess.run(command, shell=True, check=True)


def extract_reference_block(text: str) -> str:
    match = re.search(r"(?im)^#{1,3}\s+(references|bibliography|works cited)\s*$", text)
    return text[match.start() :] if match else text


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def count_citation_markers(text: str) -> int:
    patterns = [
        r"\{cite_[A-Za-z0-9_:-]+\}",
        r"\[(?:\d+\s*,\s*)*\d+\]",
        r"\([A-Z][A-Za-z-]+(?:\s+et al\.)?,\s*(?:19|20)\d{2}\)",
    ]
    markers: set[str] = set()
    for pattern in patterns:
        markers.update(match.group(0) for match in re.finditer(pattern, text))
    return len(markers)


def count_verified_citations_from_text(text: str) -> int:
    reference_text = extract_reference_block(text)
    identifiers: set[str] = set()
    patterns = [
        r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b",
        r"\barXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?\b",
        r"\b(?:https?://)?(?:doi\.org|dx\.doi\.org)/[^\s)]+",
        r"\b(?:https?://)?(?:openalex\.org|semanticscholar\.org|crossref\.org|pubmed\.ncbi\.nlm\.nih\.gov)/[^\s)]+",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, reference_text, re.I):
            identifier = match.group(0).rstrip(".,;").lower()
            if "doi.org/" in identifier:
                identifier = identifier.split("doi.org/", 1)[1]
            identifiers.add(identifier)
    return len(identifiers)


def count_verified_citations_from_database(draft_path: Path) -> int:
    search_dirs = [draft_path.parent, draft_path.parent.parent]
    for directory in search_dirs:
        db_path = directory / "citation_database.json"
        if not db_path.is_file():
            continue
        try:
            data = json.loads(db_path.read_text())
        except json.JSONDecodeError:
            continue
        citations = data.get("citations", data if isinstance(data, list) else [])
        if not isinstance(citations, list):
            continue
        verified = 0
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            if citation.get("verified") is True or citation.get("doi") or citation.get("url") or citation.get("source_url"):
                verified += 1
        return verified
    return 0


def score_structure_quality(text: str) -> float:
    headings = re.findall(r"(?m)^#{1,3}\s+(.+?)\s*$", text)
    normalized = [heading.lower() for heading in headings]
    expected_sections = (
        "introduction",
        "background",
        "method",
        "analysis",
        "discussion",
        "conclusion",
        "references",
    )

    score = 0.0
    if headings and text.lstrip().startswith("#"):
        score += 15.0

    covered = sum(1 for section in expected_sections if any(section in heading for heading in normalized))
    score += (covered / len(expected_sections)) * 55.0
    score += min(len(headings), 6) / 6 * 15.0

    paragraph_count = len([block for block in re.split(r"\n\s*\n", text.strip()) if len(block.split()) >= 25])
    score += min(paragraph_count, 6) / 6 * 15.0

    return round(min(score, 100.0), 2)


def collect_topic_metrics(topic: EvalTopic, draft_path: Path) -> TopicMetrics:
    text = draft_path.read_text(encoding="utf-8")
    db_verified = count_verified_citations_from_database(draft_path)
    text_verified = count_verified_citations_from_text(text)
    return TopicMetrics(
        topic_id=topic.id,
        topic=topic.topic,
        draft_path=str(draft_path),
        word_count=count_words(text),
        citation_count=count_citation_markers(text),
        verified_citations=max(db_verified, text_verified),
        structure_quality=score_structure_quality(text),
    )


def aggregate(metrics: list[TopicMetrics]) -> dict[str, float]:
    if not metrics:
        return {metric: 0.0 for metric in REGRESSION_METRICS}
    return {
        "word_count": round(sum(item.word_count for item in metrics) / len(metrics), 2),
        "citation_count": round(sum(item.citation_count for item in metrics) / len(metrics), 2),
        "verified_citations": round(sum(item.verified_citations for item in metrics) / len(metrics), 2),
        "structure_quality": round(sum(item.structure_quality for item in metrics) / len(metrics), 2),
    }


def build_report(
    topics: list[EvalTopic],
    drafts_dir: Path,
    generate_command: str | None = None,
) -> dict[str, Any]:
    metrics: list[TopicMetrics] = []
    for topic in topics:
        if generate_command:
            run_generation(topic, drafts_dir, generate_command)
        draft_path = find_draft_file(drafts_dir, topic)
        if draft_path is None:
            raise FileNotFoundError(
                f"No draft found for topic '{topic.id}' in {drafts_dir}. "
                "Provide existing drafts or pass --generate/--generate-command."
            )
        metrics.append(collect_topic_metrics(topic, draft_path))

    return {
        "topics_file_count": len(topics),
        "topics": [asdict(item) for item in metrics],
        "aggregate": aggregate(metrics),
    }


def compare_reports(baseline: dict[str, Any], current: dict[str, Any], max_degradation: float) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []

    baseline_aggregate = baseline.get("aggregate", {})
    current_aggregate = current.get("aggregate", {})
    for metric in REGRESSION_METRICS:
        base_value = float(baseline_aggregate.get(metric, 0))
        current_value = float(current_aggregate.get(metric, 0))
        if base_value <= 0:
            continue
        minimum_allowed = base_value * (1 - max_degradation)
        if current_value < minimum_allowed:
            regressions.append(
                {
                    "scope": "aggregate",
                    "metric": metric,
                    "baseline": base_value,
                    "current": current_value,
                    "minimum_allowed": round(minimum_allowed, 2),
                }
            )

    baseline_by_topic = {item["topic_id"]: item for item in baseline.get("topics", [])}
    for item in current.get("topics", []):
        topic_id = item["topic_id"]
        baseline_item = baseline_by_topic.get(topic_id)
        if not baseline_item:
            continue
        for metric in REGRESSION_METRICS:
            base_value = float(baseline_item.get(metric, 0))
            current_value = float(item.get(metric, 0))
            if base_value <= 0:
                continue
            minimum_allowed = base_value * (1 - max_degradation)
            if current_value < minimum_allowed:
                regressions.append(
                    {
                        "scope": "topic",
                        "topic_id": topic_id,
                        "metric": metric,
                        "baseline": base_value,
                        "current": current_value,
                        "minimum_allowed": round(minimum_allowed, 2),
                    }
                )

    return regressions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenDraft golden-topic regression metrics.")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS, help="Path to eval_topics.json")
    parser.add_argument("--drafts-dir", type=Path, default=DEFAULT_DRAFTS_DIR, help="Directory with generated drafts")
    parser.add_argument("--baseline", type=Path, help="Baseline JSON report to compare against")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Where to write the current report")
    parser.add_argument(
        "--max-degradation",
        type=float,
        default=0.10,
        help="Allowed fractional drop before failing, e.g. 0.10 for 10%%",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate drafts using the default opendraft CLI command before measuring",
    )
    parser.add_argument(
        "--generate-command",
        help=(
            "Shell command template for generation. Available placeholders: "
            "{topic_quoted}, {output_dir_quoted}, {topic_id}, {level}, {blurb_quoted}"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    topics = load_topics(args.topics)
    command = args.generate_command or (DEFAULT_GENERATE_COMMAND if args.generate else None)

    try:
        current = build_report(topics, args.drafts_dir, generate_command=command)
    except Exception as exc:
        print(f"eval_regression: {exc}", file=sys.stderr)
        return 2

    regressions: list[dict[str, Any]] = []
    if args.baseline:
        baseline = json.loads(args.baseline.read_text())
        regressions = compare_reports(baseline, current, args.max_degradation)

    current["passed"] = not regressions
    current["regressions"] = regressions
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(current, indent=2) + "\n")

    print(f"Wrote regression report: {args.output}")
    print(f"Aggregate metrics: {current['aggregate']}")
    if regressions:
        print(f"Regression check failed: {len(regressions)} metric(s) degraded", file=sys.stderr)
        return 1
    print("Regression check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
