#!/usr/bin/env python3
"""Cross-model evaluation harness — compare draft quality across LLM providers.

Usage:
    python scripts/eval_cross_model.py \\
        --providers gemini,openai,claude \\
        --topic "Quantum computing for drug discovery" \\
        --output reports/

Outputs a markdown comparison table to stdout and saves detailed JSON to --output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Ensure engine is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

# Default topics if --topic is not given
DEFAULT_TOPICS = [
    "Quantum computing for drug discovery: current state and future potential",
    "The impact of microplastics on marine ecosystems and human health",
    "Explainable AI in healthcare: bridging the gap between accuracy and interpretability",
]

# Provider → env var that must be set
PROVIDER_KEY_MAP: dict[str, str] = {
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


@dataclass
class ProviderResult:
    provider: str
    model: str
    topic: str
    duration_seconds: float
    word_count: int = 0
    citation_count: int = 0
    verified_citations: int = 0
    status: str = "ok"
    error: str | None = None
    output_path: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cross-model evaluation harness for OpenDraft"
    )
    parser.add_argument(
        "--providers",
        default="gemini",
        help="Comma-separated list of providers (gemini,openai,claude). Default: gemini",
    )
    parser.add_argument(
        "--topic",
        help="Single topic to evaluate. If omitted, runs DEFAULT_TOPICS[0].",
    )
    parser.add_argument(
        "--output",
        default="reports",
        help="Output directory for JSON results. Default: reports/",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print progress during generation",
    )
    return parser.parse_args()


def check_api_keys(providers: list[str]) -> list[str]:
    """Return list of providers that have the required API key set."""
    available = []
    for provider in providers:
        key = PROVIDER_KEY_MAP.get(provider)
        if key and os.environ.get(key):
            available.append(provider)
        else:
            print(f"  ⚠  {provider}: missing {key}, skipping")
    return available


def extract_citations(text: str) -> list[str]:
    """Extract citation markers from draft text (DOI URLs, [N] patterns, etc.)."""
    citations = set()
    # DOI URLs
    for match in re.finditer(r"https?://doi\.org/\S+", text):
        citations.add(match.group().rstrip(".,;:)]}"))
    # Markdown links
    for match in re.finditer(r"\[([^\]]+)\]\(https?://[^)]+\)", text):
        citations.add(match.group(0))
    # [N] style
    for match in re.finditer(r"\[(\d+)\]", text):
        citations.add(match.group(0))
    return sorted(citations)


def count_words(text: str) -> int:
    """Approximate word count."""
    return len(re.findall(r"\b\w+\b", text))


def verify_citations(citations: list[str]) -> int:
    """Heuristic: count how many citations look valid (have a DOI or URL)."""
    verified = 0
    for c in citations:
        if "doi.org" in c or "http" in c or "arxiv" in c:
            verified += 1
    return verified


def run_provider(
    provider: str, topic: str, output_dir: Path, verbose: bool
) -> ProviderResult:
    """Run a single provider and return metrics."""
    model_name = os.environ.get(
        f"{provider.upper()}_MODEL",
        {
            "gemini": "gemini-3-flash-preview",
            "openai": "gpt-4.1-nano",
            "claude": "claude-sonnet-4-20250514",
        }.get(provider, "unknown"),
    )

    result = ProviderResult(
        provider=provider, model=model_name, topic=topic
    )

    # Set provider
    os.environ["AI_PROVIDER"] = provider

    start = time.perf_counter()
    try:
        from engine.draft_generator import generate_draft

        md_file, _ = generate_draft(
            topic=topic,
            language="en",
            academic_level="master",
            verbose=verbose,
            skip_validation=True,
        )
        result.duration_seconds = time.perf_counter() - start
        result.output_path = str(md_file)

        if md_file and md_file.exists():
            text = md_file.read_text(encoding="utf-8")
            result.word_count = count_words(text)
            citations = extract_citations(text)
            result.citation_count = len(citations)
            result.verified_citations = verify_citations(citations)

    except Exception as exc:
        result.duration_seconds = time.perf_counter() - start
        result.status = "error"
        result.error = str(exc)

    return result


def print_comparison_table(results: list[ProviderResult]) -> None:
    """Print a markdown comparison table."""
    print("\n\n## Cross-Model Comparison\n")
    print("| Provider | Model | Topic | Duration | Words | Citations | Verified | Rate |")
    print("|----------|-------|-------|----------|-------|-----------|----------|------|")
    for r in results:
        if r.status == "ok":
            rate = (
                f"{r.verified_citations / r.citation_count * 100:.0f}%"
                if r.citation_count > 0
                else "N/A"
            )
            print(
                f"| {r.provider} | {r.model} | {r.topic[:50]}… | "
                f"{r.duration_seconds:.1f}s | {r.word_count} | "
                f"{r.citation_count} | {r.verified_citations} | {rate} |"
            )
        else:
            print(
                f"| {r.provider} | {r.model} | {r.topic[:50]}… | "
                f"❌ ERROR: {r.error or 'unknown'} |"
            )
    print()


def save_report(results: list[ProviderResult], output_dir: Path) -> Path:
    """Save detailed JSON report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "cross_model_report.json"
    data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [asdict(r) for r in results],
    }
    report_path.write_text(json.dumps(data, indent=2, default=str))
    return report_path


def main() -> None:
    args = parse_args()
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    topic = args.topic or DEFAULT_TOPICS[0]
    output_dir = Path(args.output)

    print(f"🔬 Cross-Model Evaluation Harness\n")
    print(f"   Topic:     {topic}")
    print(f"   Providers: {', '.join(providers)}")
    print()

    # Check which providers are available
    available = check_api_keys(providers)
    if not available:
        print("❌ No providers have API keys configured. Set at least one of:")
        for provider in providers:
            key = PROVIDER_KEY_MAP.get(provider, "?")
            print(f"   {key}=your_key_here")
        sys.exit(1)

    print(f"   Available: {', '.join(available)}\n")

    results: list[ProviderResult] = []
    for provider in available:
        if args.verbose:
            print(f"▶  Running {provider}...")
        result = run_provider(provider, topic, output_dir, args.verbose)
        results.append(result)
        if result.status == "ok":
            print(
                f"   ✅ {provider} done — {result.duration_seconds:.1f}s, "
                f"{result.word_count} words, {result.citation_count} citations"
            )
        else:
            print(f"   ❌ {provider} failed: {result.error}")
        print()

    # Output
    print_comparison_table(results)
    report_path = save_report(results, output_dir)
    print(f"📄 Detailed report saved to {report_path}")


if __name__ == "__main__":
    main()
