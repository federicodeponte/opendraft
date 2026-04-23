#!/usr/bin/env python3
"""
ABOUTME: Generate 5-bullet TL;DR summaries from academic papers
ABOUTME: Standalone module for quick paper summarization

Usage:
    python -m engine.tldr paper.pdf
    python -m engine.tldr paper.pdf -o summary.md
"""

import os
import re
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from utils.document_reader import read_document, get_document_info

logger = logging.getLogger(__name__)

TLDR_PROMPT = (Path(__file__).parent / "prompts" / "tldr.md").read_text()


def generate_tldr(
    document_path: Path,
    model_name: str | None = None,
    max_chars: int = 100000,
) -> str:
    """
    Generate a 5-bullet TL;DR from a document.

    Args:
        document_path: Path to PDF, markdown, or text file
        model_name: Model name to use for the active provider
        max_chars: Max characters to read from document

    Returns:
        TL;DR as markdown string with 5 bullets
    """
    document_path = Path(document_path)
    content = read_document(document_path, max_chars=max_chars)

    # Setup provider client
    from utils.llm_client import build_model_client

    model = build_model_client(model_override=model_name)

    # Build prompt
    prompt = f"""{TLDR_PROMPT}

---
DOCUMENT: {document_path.name}
---

{content}

---

IMPORTANT: Follow this EXACT format:

### Research Context
**Authors**: [Extract lead author et al. from document]
**Source**: [Journal/conference name, year]
**Method**: [One sentence describing study type, sample size, approach]

### Key Findings
- **[Thesis]**: [Main argument, max 15 words]
- **[Finding]**: [Key result, max 15 words]
- **[Finding]**: [Key result, max 15 words]
- **[Implication]**: [Significance, max 15 words]
- **[Limitation]**: [Caveat, max 15 words]

The Research Context block is REQUIRED. Extract author names and methodology from the document.
"""

    # Generate
    response = model.generate_content(prompt)
    tldr = _extract_tldr(response.text)

    return tldr


def _extract_tldr(output: str) -> str:
    """Extract and format the TL;DR with Research Context."""
    lines = output.strip().split("\n")

    result_lines = []
    in_context = False
    in_findings = False
    bullets = []

    for line in lines:
        line_stripped = line.strip()

        # Detect sections
        if "Research Context" in line_stripped or "**Authors**" in line_stripped:
            in_context = True
            in_findings = False
        elif "Key Findings" in line_stripped or "Findings" in line_stripped:
            in_context = False
            in_findings = True

        # Collect Research Context lines
        if in_context and line_stripped:
            if line_stripped.startswith("**") or line_stripped.startswith("###"):
                result_lines.append(line_stripped)

        # Collect bullet points
        if line_stripped.startswith("- **") or line_stripped.startswith("* **"):
            bullets.append(line_stripped)

    # Build output
    output_parts = ["## TL;DR\n"]

    # Add Research Context if found
    context_lines = [l for l in result_lines if l.startswith("**")]
    if context_lines:
        output_parts.append("### Research Context\n")
        output_parts.extend([l + "\n" for l in context_lines])
        output_parts.append("\n### Key Findings\n")

    # Add bullets
    if bullets:
        output_parts.extend([b + "\n" for b in bullets[:5]])
    else:
        # Fallback
        output_parts.append(output.strip())

    return "".join(output_parts).strip()


def main():
    parser = argparse.ArgumentParser(
        description="Generate 5-bullet TL;DR for any paper"
    )
    parser.add_argument("document", help="Path to document (PDF, MD, or TXT)")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (defaults to the active provider's selected model)"
    )

    args = parser.parse_args()
    try:
        from opendraft.cli import apply_saved_runtime_config
    except ImportError:
        from cli import apply_saved_runtime_config
    apply_saved_runtime_config()
    document_path = Path(args.document)

    if not document_path.exists():
        print(f"Error: File not found: {document_path}")
        sys.exit(1)

    print(f"Document: {document_path.name}")

    try:
        info = get_document_info(document_path)
        print(f"Words: {info['word_count']:,}")
    except Exception:
        pass

    print("\nGenerating TL;DR...")

    tldr = generate_tldr(document_path, model_name=args.model)

    print(f"\n{tldr}")

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(tldr, encoding="utf-8")
        print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
