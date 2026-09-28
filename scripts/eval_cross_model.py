#!/usr/bin/env python3
"""Run one OpenDraft topic across LLM providers and compare core metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))


PROVIDER_DEFAULTS = {
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-4.1-nano",
    "anthropic": "claude-sonnet-4-5",
}
MODEL_ENV_VARS = {
    "gemini": "GEMINI_MODEL",
    "openai": "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
}


@dataclass
class EvaluationResult:
    provider: str
    model: str
    status: str
    verified_citations: int = 0
    total_citations: int = 0
    verification_rate: Optional[float] = None
    generation_seconds: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    output_directory: Optional[str] = None
    error: Optional[str] = None


@contextmanager
def temporary_environment(updates: Dict[str, str]) -> Iterator[None]:
    """Apply environment variables for one run and restore the caller's state."""
    previous = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def citation_metrics(bibliography_path: Path) -> tuple[int, int, Optional[float]]:
    """Return multi-source-confirmed, total, and percentage from a bibliography."""
    if not bibliography_path.exists():
        return 0, 0, None
    data = json.loads(bibliography_path.read_text(encoding="utf-8"))
    citations = data.get("citations", [])
    verified = sum(
        citation.get("verification_status") == "multi_source_confirmed"
        for citation in citations
    )
    total = len(citations)
    rate = (verified / total * 100.0) if total else None
    return verified, total, rate


def tracked_cost(token_usage_path: Path, model: str) -> Optional[float]:
    """Read tracked cost, returning None when pricing for the model is unknown."""
    if not token_usage_path.exists():
        return None

    from utils.model_config import get_model_pricing

    if get_model_pricing(model) is None:
        return None
    data = json.loads(token_usage_path.read_text(encoding="utf-8"))
    value = data.get("total_cost_usd")
    return float(value) if value is not None else None


def run_provider(
    *,
    provider: str,
    model: str,
    topic: str,
    output_root: Path,
    academic_level: str,
    output_type: str,
    language: str,
) -> EvaluationResult:
    """Run the pipeline once and collect metrics without hiding provider failures."""
    provider_dir = output_root / provider
    env_updates = {
        "AI_PROVIDER": provider,
        MODEL_ENV_VARS[provider]: model,
    }
    started = time.perf_counter()

    try:
        with temporary_environment(env_updates):
            # Config is intentionally lazy and process-global. Reset it between
            # providers so every run reads the environment above independently.
            import config

            config._config = None
            from draft_generator import generate_draft

            generate_draft(
                topic=topic,
                language=language,
                academic_level=academic_level,
                output_dir=provider_dir,
                output_type=output_type,
                skip_validation=True,
                verbose=False,
            )
            config._config = None

        elapsed = time.perf_counter() - started
        verified, total, rate = citation_metrics(
            provider_dir / "research" / "bibliography.json"
        )
        return EvaluationResult(
            provider=provider,
            model=model,
            status="ok",
            verified_citations=verified,
            total_citations=total,
            verification_rate=rate,
            generation_seconds=elapsed,
            estimated_cost_usd=tracked_cost(provider_dir / "token_usage.json", model),
            output_directory=str(provider_dir),
        )
    except Exception as exc:
        try:
            import config

            config._config = None
        except ImportError:
            pass
        return EvaluationResult(
            provider=provider,
            model=model,
            status="failed",
            generation_seconds=time.perf_counter() - started,
            output_directory=str(provider_dir),
            error=f"{type(exc).__name__}: {exc}",
        )


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_report(topic: str, results: Iterable[EvaluationResult]) -> str:
    """Render the comparison requested by issue #35."""
    lines = [
        "# Cross-model evaluation",
        "",
        f"**Topic:** {_cell(topic)}",
        "",
        "| Provider | Model | Verified citations | Verification rate | Time | "
        "Estimated cost | Status |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    result_list = list(results)
    for result in result_list:
        rate = (
            "—"
            if result.verification_rate is None
            else f"{result.verification_rate:.1f}%"
        )
        duration = (
            "—"
            if result.generation_seconds is None
            else f"{result.generation_seconds:.1f}s"
        )
        cost = (
            "—"
            if result.estimated_cost_usd is None
            else f"${result.estimated_cost_usd:.4f}"
        )
        status = (
            result.status if not result.error else f"{result.status}: {result.error}"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(result.provider),
                    _cell(result.model),
                    f"{result.verified_citations}/{result.total_citations}",
                    rate,
                    duration,
                    cost,
                    _cell(status),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Verification rate is the share of retained bibliography entries with "
            "`verification_status=multi_source_confirmed`.",
            "Estimated cost comes from OpenDraft's tracked token usage and configured "
            "model pricing; "
            "an em dash means pricing or usage was unavailable.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_providers(value: str) -> List[str]:
    providers = [
        provider.strip().lower() for provider in value.split(",") if provider.strip()
    ]
    unknown = sorted(set(providers) - set(PROVIDER_DEFAULTS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown provider(s): {', '.join(unknown)}")
    if not providers:
        raise argparse.ArgumentTypeError("at least one provider is required")
    return providers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare an OpenDraft topic across Gemini, OpenAI, and Anthropic."
    )
    parser.add_argument(
        "--topic", required=True, help="Topic passed unchanged to every provider"
    )
    parser.add_argument(
        "--providers",
        type=parse_providers,
        default=parse_providers("gemini,openai,anthropic"),
        help="Comma-separated providers (default: gemini,openai,anthropic)",
    )
    parser.add_argument("--gemini-model", default=PROVIDER_DEFAULTS["gemini"])
    parser.add_argument("--openai-model", default=PROVIDER_DEFAULTS["openai"])
    parser.add_argument("--anthropic-model", default=PROVIDER_DEFAULTS["anthropic"])
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--academic-level",
        default="research_paper",
        choices=["research_paper", "bachelor", "master", "phd"],
    )
    parser.add_argument("--output-type", default="full", choices=["full", "expose"])
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Report directory (default: reports/cross_model_<UTC timestamp>)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = args.output_dir or REPO_ROOT / "reports" / f"cross_model_{timestamp}"
    output_root.mkdir(parents=True, exist_ok=True)

    models = {
        "gemini": args.gemini_model,
        "openai": args.openai_model,
        "anthropic": args.anthropic_model,
    }
    results = [
        run_provider(
            provider=provider,
            model=models[provider],
            topic=args.topic,
            output_root=output_root,
            academic_level=args.academic_level,
            output_type=args.output_type,
            language=args.language,
        )
        for provider in args.providers
    ]

    report = markdown_report(args.topic, results)
    (output_root / "comparison.md").write_text(report, encoding="utf-8")
    (output_root / "results.json").write_text(
        json.dumps(
            {
                "topic": args.topic,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "results": [asdict(result) for result in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report)
    print(f"Report written to {output_root / 'comparison.md'}")
    return 1 if any(result.status != "ok" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
