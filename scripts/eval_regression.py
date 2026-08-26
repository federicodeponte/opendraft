#!/usr/bin/env python3
"""
Regression test for citation accuracy and draft quality across releases.

Usage:
  python scripts/eval_regression.py              # compare against baseline, fail if degraded
  python scripts/eval_regression.py --update     # run evals and write new baseline
  python scripts/eval_regression.py --topic-idx 0  # run only one topic (0-based)
"""

import sys
import re
import json
import argparse
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any

logging.basicConfig(level=logging.WARNING)

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
BASELINE_PATH = DATA_DIR / "eval_baseline.json"
TOPICS_PATH = DATA_DIR / "eval_topics.json"
DEGRADATION_THRESHOLD = 0.10  # 10%

# Add engine to path
sys.path.insert(0, str(REPO_ROOT / "opendraft" / "engine"))


def compute_metrics(md_path: Path) -> Dict[str, float]:
    """Extract quality metrics from a final markdown draft."""
    text = md_path.read_text(encoding="utf-8")

    word_count = len(text.split())

    # Count markdown headers (##, ###) as a proxy for structure depth
    headers = re.findall(r"^#{1,3}\s+.+$", text, re.MULTILINE)
    structure_score = len(headers)

    # Count reference/citation entries in the References section.
    # APA entries typically start at column 0 with an author surname.
    # IEEE entries start with [N]. We count non-empty lines inside the last
    # section whose heading contains "reference" (case-insensitive).
    ref_section_match = re.search(
        r"^#{1,3}\s+.*references.*$(.+?)(?:^#{1,3}\s|\Z)",
        text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    citation_count = 0
    if ref_section_match:
        ref_block = ref_section_match.group(1)
        # Each entry is a non-empty line that doesn't start with whitespace only
        citation_lines = [
            ln for ln in ref_block.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        # Heuristic: group consecutive non-empty lines into one entry (hanging-indent style)
        # A new entry starts when the line is flush-left (no leading spaces).
        entry_count = sum(
            1 for ln in citation_lines if not ln.startswith(" ") and not ln.startswith("\t")
        )
        citation_count = max(entry_count, 1) if citation_lines else 0

    return {
        "word_count": float(word_count),
        "citation_count": float(citation_count),
        "structure_score": float(structure_score),
    }


def generate_and_measure(topic: str, academic_level: str, citation_style: str) -> Dict[str, float]:
    """Run the full pipeline for one topic and return metrics."""
    from draft_generator import generate_draft

    with tempfile.TemporaryDirectory(prefix="eval_") as tmp:
        output_dir = Path(tmp) / "out"
        output_dir.mkdir()

        generate_draft(
            topic=topic,
            academic_level=academic_level,
            citation_style=citation_style,
            output_dir=output_dir,
            skip_validation=True,
            verbose=False,
        )

        # Locate the final markdown in exports/
        md_files = list((output_dir / "exports").glob("*.md"))
        md_files = [f for f in md_files if "INTERMEDIATE" not in f.name]
        if not md_files:
            raise FileNotFoundError(f"No final markdown found in {output_dir / 'exports'}")

        # Pick the most recently modified one
        md_path = max(md_files, key=lambda p: p.stat().st_mtime)
        return compute_metrics(md_path)


def check_regression(
    current: Dict[str, float],
    baseline: Dict[str, float],
    topic: str,
) -> list[str]:
    """Return a list of failure messages (empty means pass)."""
    failures = []
    for metric, base_val in baseline.items():
        curr_val = current.get(metric, 0.0)
        if base_val == 0:
            continue
        degradation = (base_val - curr_val) / base_val
        if degradation > DEGRADATION_THRESHOLD:
            failures.append(
                f"  [{topic[:50]}] {metric}: {curr_val:.1f} vs baseline {base_val:.1f} "
                f"({degradation * 100:.1f}% degradation)"
            )
    return failures


def main():
    parser = argparse.ArgumentParser(description="Citation accuracy regression eval")
    parser.add_argument("--update", action="store_true", help="Write new baseline instead of comparing")
    parser.add_argument("--topic-idx", type=int, default=None, help="Run only this topic index")
    args = parser.parse_args()

    topics = json.loads(TOPICS_PATH.read_text())
    if args.topic_idx is not None:
        topics = [topics[args.topic_idx]]

    results: Dict[str, Dict[str, float]] = {}
    for entry in topics:
        topic = entry["topic"]
        print(f"\nEvaluating: {topic[:70]}")
        metrics = generate_and_measure(topic, entry["academic_level"], entry["citation_style"])
        results[topic] = metrics
        print(f"  word_count={metrics['word_count']:.0f}  "
              f"citations={metrics['citation_count']:.0f}  "
              f"headers={metrics['structure_score']:.0f}")

    if args.update:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(results, indent=2))
        print(f"\nBaseline written to {BASELINE_PATH}")
        return

    if not BASELINE_PATH.exists():
        print(
            f"\nNo baseline found at {BASELINE_PATH}.\n"
            "Run with --update to create one.",
            file=sys.stderr,
        )
        sys.exit(1)

    baseline = json.loads(BASELINE_PATH.read_text())
    all_failures = []
    for topic, metrics in results.items():
        if topic not in baseline:
            print(f"  WARNING: topic not in baseline, skipping: {topic[:60]}")
            continue
        failures = check_regression(metrics, baseline[topic], topic)
        all_failures.extend(failures)

    if all_failures:
        print("\nREGRESSION DETECTED: the following metrics degraded >10%:\n")
        for msg in all_failures:
            print(msg)
        sys.exit(1)
    else:
        print("\nAll metrics within acceptable range. Regression check passed.")


if __name__ == "__main__":
    main()
