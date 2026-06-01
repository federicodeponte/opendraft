#!/usr/bin/env python3
"""
ABOUTME: Cross-model evaluation harness for OpenDraft
ABOUTME: Compares output quality across LLM providers using the full pipeline

Implements EVALUATION.md §5 — Cross-Model Consistency.

Metrics collected per provider run:
  - Citation verification rate  (via CitationValidator.validate_database)
  - Cost per draft              (via TokenTracker, written to token_usage.json)
  - Generation time             (wall-clock seconds around generate_draft())

Usage:
    # Run all configured providers (skip those without API keys)
    python scripts/eval_cross_model.py --topic "Transformer Architecture"

    # Run specific providers only
    python scripts/eval_cross_model.py --topic "Transformer Architecture" --providers gemini,openai

    # Save report to a custom path
    python scripts/eval_cross_model.py --topic "AI Safety" --output reports/ai_safety_eval.md

Output:
    reports/cross_model_comparison.md   (Markdown table + per-provider details)
"""

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path bootstrap — makes "from draft_generator import ..." work regardless of
# where the script is invoked from.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"

for p in [str(REPO_ROOT), str(ENGINE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Provider → (AI_PROVIDER env value, default model env var, display name)
# ---------------------------------------------------------------------------
PROVIDER_META: Dict[str, Dict] = {
    "gemini": {
        "env_value": "gemini",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-3-pro-preview",
        "api_key_env": "GOOGLE_API_KEY",
        "display": "Google Gemini",
    },
    "openai": {
        "env_value": "openai",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4.1-nano",
        "api_key_env": "OPENAI_API_KEY",
        "display": "OpenAI",
    },
    "claude": {
        "env_value": "claude",
        "model_env": "ANTHROPIC_MODEL",
        "default_model": "claude-sonnet-4-5",
        "api_key_env": "ANTHROPIC_API_KEY",
        "display": "Anthropic Claude",
    },
}

ALL_PROVIDERS = list(PROVIDER_META.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_config_singleton() -> None:
    """
    Force the config singleton to reload from the current environment.

    config.py caches _config as a module-level global. When we switch
    AI_PROVIDER between iterations we must bust that cache so get_config()
    picks up the new value.
    """
    try:
        import config as cfg_module  # engine/config.py
        cfg_module._config = None
    except Exception:
        pass


def _find_output_dir(base_output: Path) -> Optional[Path]:
    """
    Return the most-recently-modified subdirectory inside base_output.

    generate_draft() writes to config.paths.output_dir / "generated_draft" by
    default, but we pass an explicit per-provider output_dir so this just
    returns that directory if it exists.
    """
    if base_output.exists() and base_output.is_dir():
        return base_output
    return None


def _compute_citation_rate(stats: Dict) -> Tuple[float, int, int]:
    """
    Derive citation verification rate from validate_database() stats dict.

    validate_database() returns:
        total_citations, total_issues, critical_issues, warnings,
        invalid_dois, invalid_authors, invalid_urls, invalid_metadata

    A citation is considered "invalid" only when it has at least one CRITICAL
    issue (e.g. invalid DOI, bad metadata). Warnings are soft flags.

    Returns (rate_pct, valid_count, total_count).
    """
    total = stats.get("total_citations", 0)
    if total == 0:
        return 0.0, 0, 0

    # Citations with at least one critical issue — treat as invalid.
    # We can't know exactly how many *citations* have critical issues from the
    # aggregate count alone (one citation may have multiple issues), so we use
    # a conservative estimate: assume each unique citation_id with a critical
    # issue is counted once. The stats dict gives us the raw critical issue
    # count as a lower bound; we cap at total.
    critical = min(stats.get("critical_issues", 0), total)
    valid = total - critical
    rate = (valid / total) * 100.0
    return round(rate, 1), valid, total


def _load_token_data(output_dir: Path) -> Optional[Dict]:
    """
    Load token_usage.json from the draft output root.

    draft_generator._finalize() writes:
        ctx.folders['root'] / "token_usage.json"
    which is the same as output_dir/token_usage.json.
    """
    token_path = output_dir / "token_usage.json"
    if not token_path.exists():
        return None
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _check_api_key(provider: str) -> bool:
    """Return True if the provider's API key env var is set and non-empty."""
    key_env = PROVIDER_META[provider]["api_key_env"]
    return bool(os.environ.get(key_env, "").strip())


# ---------------------------------------------------------------------------
# Core evaluation function
# ---------------------------------------------------------------------------

def evaluate_provider(
    provider: str,
    topic: str,
    academic_level: str = "research_paper",
    verbose: bool = True,
) -> Dict:
    """
    Run generate_draft() for one provider and collect all evaluation metrics.

    Returns a result dict with keys:
        provider, display_name, model_name,
        status,           # 'ok' | 'skipped' | 'error'
        error_message,    # filled when status == 'error'
        generation_time,  # seconds (float)
        citation_rate,    # percent (float, 0–100)
        valid_citations,  # int
        total_citations,  # int
        cost_usd,         # float
        output_dir,       # Path or None
    """
    meta = PROVIDER_META[provider]
    display = meta["display"]
    default_model = meta["default_model"]
    model_name = os.environ.get(meta["model_env"], default_model)

    result: Dict = {
        "provider": provider,
        "display_name": display,
        "model_name": model_name,
        "status": "ok",
        "error_message": None,
        "generation_time": 0.0,
        "citation_rate": 0.0,
        "valid_citations": 0,
        "total_citations": 0,
        "cost_usd": 0.0,
        "output_dir": None,
    }

    # ------------------------------------------------------------------
    # 1. Check API key availability
    # ------------------------------------------------------------------
    if not _check_api_key(provider):
        result["status"] = "skipped"
        result["error_message"] = (
            f"{meta['api_key_env']} not set — provider skipped."
        )
        if verbose:
            print(f"\n⏭  [{display}] Skipping — {result['error_message']}")
        return result

    if verbose:
        print(f"\n{'='*70}")
        print(f"🚀  Evaluating provider: {display} ({model_name})")
        print(f"{'='*70}")

    # ------------------------------------------------------------------
    # 2. Switch AI_PROVIDER env var and bust config singleton
    # ------------------------------------------------------------------
    os.environ["AI_PROVIDER"] = meta["env_value"]
    _reset_config_singleton()

    # ------------------------------------------------------------------
    # 3. Determine a per-provider output directory so runs don't clobber
    # ------------------------------------------------------------------
    slug = topic.lower().replace(" ", "_")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = REPO_ROOT / "engine" / "tests" / "outputs" / f"eval_{provider}_{slug}_{ts}"
    result["output_dir"] = output_dir

    # ------------------------------------------------------------------
    # 4. Import generate_draft (done inside the function so the sys.path
    #    bootstrap is already in place)
    # ------------------------------------------------------------------
    try:
        # Force reimport to pick up env changes if already imported
        if "draft_generator" in sys.modules:
            importlib.reload(sys.modules["draft_generator"])
        from draft_generator import generate_draft
    except ImportError as exc:
        result["status"] = "error"
        result["error_message"] = f"Could not import draft_generator: {exc}"
        if verbose:
            print(f"❌  [{display}] Import error: {exc}")
        return result

    # ------------------------------------------------------------------
    # 5. Generate draft and time it
    # ------------------------------------------------------------------
    start = time.time()
    try:
        generate_draft(
            topic=topic,
            academic_level=academic_level,
            output_dir=output_dir,
            verbose=verbose,
        )
        result["generation_time"] = round(time.time() - start, 1)
        if verbose:
            print(f"\n✅  [{display}] Draft generated in {result['generation_time']}s")

    except Exception as exc:
        result["generation_time"] = round(time.time() - start, 1)
        result["status"] = "error"
        result["error_message"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        if verbose:
            print(f"\n❌  [{display}] Generation failed: {result['error_message']}")
            traceback.print_exc()
        # Still try to collect partial metrics if output was written
        if not output_dir.exists():
            return result

    # ------------------------------------------------------------------
    # 6. Locate bibliography.json for citation validation
    # ------------------------------------------------------------------
    bibliography_path = output_dir / "research" / "bibliography.json"

    if not bibliography_path.exists():
        if verbose:
            print(f"⚠   [{display}] bibliography.json not found at {bibliography_path}")
    else:
        try:
            from utils.citation_validator import CitationValidator
            validator = CitationValidator(timeout=15)
            if verbose:
                print(f"\n🔍  [{display}] Validating citations...")
            issues, stats = validator.validate_database(bibliography_path)
            rate, valid, total = _compute_citation_rate(stats)
            result["citation_rate"] = rate
            result["valid_citations"] = valid
            result["total_citations"] = total
            if verbose:
                print(
                    f"📊  [{display}] Citation rate: {rate}% "
                    f"({valid}/{total} valid, "
                    f"{stats.get('critical_issues', 0)} critical issues, "
                    f"{stats.get('warnings', 0)} warnings)"
                )
        except Exception as exc:
            if verbose:
                print(f"⚠   [{display}] Citation validation failed: {exc}")

    # ------------------------------------------------------------------
    # 7. Read cost from token_usage.json
    # ------------------------------------------------------------------
    token_data = _load_token_data(output_dir)
    if token_data:
        result["cost_usd"] = token_data.get("total_cost_usd", 0.0)
        if verbose:
            print(f"💰  [{display}] Cost: ${result['cost_usd']:.4f}")
    else:
        if verbose:
            print(f"⚠   [{display}] token_usage.json not found — cost will show as $0.0000")

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

STATUS_EMOJI = {"ok": "✅", "skipped": "⏭", "error": "❌"}


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


def build_markdown_report(
    results: List[Dict],
    topic: str,
    academic_level: str,
    run_timestamp: str,
) -> str:
    """Render the collected results as a Markdown document."""
    lines: List[str] = []

    lines.append("# Cross-Model Evaluation")
    lines.append("")
    lines.append(
        "> Automatically generated by `scripts/eval_cross_model.py`  "
    )
    lines.append(f"> **Topic:** {topic}  ")
    lines.append(f"> **Academic level:** {academic_level}  ")
    lines.append(f"> **Run timestamp:** {run_timestamp}  ")
    lines.append(
        "> Evaluation method: EVALUATION.md §5 — Cross-Model Consistency"
    )
    lines.append("")

    # ---------- Summary table ----------
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Provider | Model | Citation Rate | Valid / Total | Cost (USD) | Generation Time | Status |"
    )
    lines.append(
        "|----------|-------|:-------------:|:-------------:|:----------:|:---------------:|:------:|"
    )

    for r in results:
        emoji = STATUS_EMOJI.get(r["status"], "❓")
        if r["status"] == "ok":
            cite_rate = f"{r['citation_rate']:.1f}%"
            cite_counts = f"{r['valid_citations']}/{r['total_citations']}"
            cost = f"${r['cost_usd']:.4f}"
            gen_time = _fmt_time(r["generation_time"])
        elif r["status"] == "skipped":
            cite_rate = cite_counts = cost = gen_time = "—"
        else:  # error
            cite_rate = f"{r['citation_rate']:.1f}%"
            cite_counts = f"{r['valid_citations']}/{r['total_citations']}"
            cost = f"${r['cost_usd']:.4f}"
            gen_time = _fmt_time(r["generation_time"])

        lines.append(
            f"| {r['display_name']} | `{r['model_name']}` "
            f"| {cite_rate} | {cite_counts} | {cost} | {gen_time} | {emoji} {r['status']} |"
        )

    lines.append("")

    # ---------- Per-provider details ----------
    lines.append("## Per-Provider Details")
    lines.append("")

    for r in results:
        emoji = STATUS_EMOJI.get(r["status"], "❓")
        lines.append(f"### {emoji} {r['display_name']}")
        lines.append("")
        lines.append(f"- **Model:** `{r['model_name']}`")
        lines.append(f"- **Status:** {r['status']}")

        if r["status"] == "skipped":
            lines.append(f"- **Reason:** {r['error_message']}")
        else:
            lines.append(
                f"- **Citation verification rate:** {r['citation_rate']:.1f}% "
                f"({r['valid_citations']} valid out of {r['total_citations']})"
            )
            lines.append(f"- **Cost:** ${r['cost_usd']:.6f} USD")
            lines.append(
                f"- **Generation time:** {_fmt_time(r['generation_time'])} "
                f"({r['generation_time']:.1f}s)"
            )
            if r["output_dir"]:
                lines.append(f"- **Output dir:** `{r['output_dir']}`")
            if r["status"] == "error":
                lines.append(f"- **Error:** {r['error_message']}")

        lines.append("")

    # ---------- Methodology note ----------
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "Each provider is evaluated by running OpenDraft's full "
        "`generate_draft()` pipeline end-to-end:"
    )
    lines.append("")
    lines.append(
        "```\n"
        "Provider (AI_PROVIDER env)\n"
        "    ↓\n"
        "generate_draft(topic, academic_level)\n"
        "    ↓\n"
        "research/bibliography.json  →  CitationValidator.validate_database()\n"
        "token_usage.json            →  total_cost_usd\n"
        "wall-clock timer            →  generation_time\n"
        "```"
    )
    lines.append("")
    lines.append(
        "**Citation rate** = `(total_citations − critical_issues) / total_citations × 100`.  "
    )
    lines.append(
        "Critical issues include invalid DOIs (verified via CrossRef), invalid metadata, "
        "and broken URLs (HTTP 4xx/5xx)."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cross-model evaluation harness for OpenDraft. "
            "Generates a draft with each provider and reports "
            "citation rate, cost, and generation time."
        )
    )
    parser.add_argument(
        "--topic",
        default="Transformer Architecture",
        help="Research topic to generate (default: 'Transformer Architecture')",
    )
    parser.add_argument(
        "--academic-level",
        default="research_paper",
        choices=["research_paper", "bachelor", "master", "phd"],
        help="Academic level for the draft (default: research_paper)",
    )
    parser.add_argument(
        "--providers",
        default=",".join(ALL_PROVIDERS),
        help=(
            "Comma-separated list of providers to evaluate. "
            f"Available: {', '.join(ALL_PROVIDERS)}  "
            "(default: all)"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "reports" / "cross_model_comparison.md"),
        help="Path for the Markdown report (default: reports/cross_model_comparison.md)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-provider progress output",
    )

    args = parser.parse_args()

    providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]
    unknown = [p for p in providers if p not in PROVIDER_META]
    if unknown:
        print(f"❌  Unknown provider(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"    Valid options: {', '.join(ALL_PROVIDERS)}", file=sys.stderr)
        return 1

    verbose = not args.quiet
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*70}")
    print("OpenDraft — Cross-Model Evaluation Harness")
    print(f"{'='*70}")
    print(f"Topic          : {args.topic}")
    print(f"Academic level : {args.academic_level}")
    print(f"Providers      : {', '.join(providers)}")
    print(f"Report output  : {args.output}")
    print(f"{'='*70}\n")

    results: List[Dict] = []

    for provider in providers:
        result = evaluate_provider(
            provider=provider,
            topic=args.topic,
            academic_level=args.academic_level,
            verbose=verbose,
        )
        results.append(result)

    # ------------------------------------------------------------------
    # Build and write the Markdown report
    # ------------------------------------------------------------------
    report_md = build_markdown_report(
        results=results,
        topic=args.topic,
        academic_level=args.academic_level,
        run_timestamp=run_timestamp,
    )

    report_path = Path(args.output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")

    print(f"\n{'='*70}")
    print("Evaluation complete!")
    print(f"{'='*70}")

    # Print inline summary table
    print(f"\n{'Provider':<20} {'Model':<28} {'Citation Rate':>14} {'Cost':>10} {'Time':>10} {'Status'}")
    print("-" * 90)
    for r in results:
        if r["status"] == "ok":
            row = (
                f"{r['display_name']:<20} {r['model_name']:<28} "
                f"{r['citation_rate']:>13.1f}% "
                f"${r['cost_usd']:>9.4f} "
                f"{_fmt_time(r['generation_time']):>10} "
                f"✅"
            )
        elif r["status"] == "skipped":
            row = f"{r['display_name']:<20} {r['model_name']:<28} {'—':>14} {'—':>10} {'—':>10} ⏭  skipped"
        else:
            row = (
                f"{r['display_name']:<20} {r['model_name']:<28} "
                f"{r['citation_rate']:>13.1f}% "
                f"${r['cost_usd']:>9.4f} "
                f"{_fmt_time(r['generation_time']):>10} "
                f"❌ error"
            )
        print(row)

    print(f"\n📄  Report written to: {report_path}")

    # Exit non-zero if all providers errored
    ok_count = sum(1 for r in results if r["status"] == "ok")
    if ok_count == 0 and results:
        print("\n⚠   No providers completed successfully.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())