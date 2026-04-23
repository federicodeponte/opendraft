#!/usr/bin/env python3
"""
ABOUTME: Revision module for OpenDraft V1
ABOUTME: Allows revising existing drafts with specific instructions using the active provider

Ported from V3 with simplifications for V1's lighter architecture.
"""

import re
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

from config import get_config
from utils.export_professional import export_pdf, export_docx
from utils.retry import get_gemini_circuit_breaker
from utils.llm_client import build_model_client

logger = logging.getLogger(__name__)


def _is_safe_file(path: Path, base_folder: Path) -> bool:
    """Check if file is safe (not a symlink escaping the folder)."""
    try:
        resolved = path.resolve()
        base_resolved = base_folder.resolve()
        return str(resolved).startswith(str(base_resolved))
    except (OSError, ValueError):
        return False


def find_draft_in_folder(folder: Path) -> Optional[Path]:
    """Find the main draft markdown file in an output folder."""
    folder = folder.resolve()

    # Check exports/ subfolder first (standard location)
    exports_dir = folder / "exports"
    if exports_dir.exists():
        md_files = [f for f in exports_dir.glob("*.md") if _is_safe_file(f, folder)]

        # Filter out intermediate/temp files and hidden files
        export_files = [f for f in md_files if not any(
            x in f.name.lower() for x in ['intermediate', 'abstract', 'temp', '_generated']
        ) and not f.name.startswith(('_', '.')) and not f.is_symlink()]

        if export_files:
            # Prefer final_draft.md if it exists
            for f in export_files:
                if 'final_draft' in f.name.lower():
                    return f
            # Otherwise return the largest export file
            return max(export_files, key=lambda p: p.stat().st_size)

        # Fallback to any MD file (excluding numbered/hidden files)
        non_numbered = [f for f in md_files
                        if not f.name[0].isdigit()
                        and not f.name.startswith(('.', '_'))
                        and not f.is_symlink()]
        if non_numbered:
            return max(non_numbered, key=lambda p: p.stat().st_size)

    # Check drafts/ subfolder
    drafts_dir = folder / "drafts"
    if drafts_dir.exists():
        md_files = [f for f in drafts_dir.glob("*.md")
                    if _is_safe_file(f, folder) and not f.is_symlink()
                    and not f.name.startswith(('.', '_'))]
        if md_files:
            return max(md_files, key=lambda p: p.stat().st_size)

    # Fallback to root folder
    for name in ["final_draft.md", "draft.md"]:
        candidate = folder / name
        if candidate.exists() and _is_safe_file(candidate, folder) and not candidate.is_symlink():
            return candidate

    # Last resort: largest MD in root (excluding hidden/symlinks)
    md_files = [f for f in folder.glob("*.md")
                if _is_safe_file(f, folder) and not f.is_symlink()
                and not f.name.startswith(('.', '_'))]
    if md_files:
        return max(md_files, key=lambda p: p.stat().st_size)

    return None


def call_llm_revise(draft: str, instructions: str, model: str | None = None, max_retries: int = 3) -> str:
    """
    Call the active provider to revise a draft based on instructions.

    Args:
        draft: The current draft text
        instructions: Revision instructions from user
        model: Optional model override
        max_retries: Maximum retry attempts on transient errors

    Returns:
        Revised draft text
    """
    config = get_config()
    client = build_model_client(model_override=model)
    circuit_breaker = get_gemini_circuit_breaker()

    prompt = f"""You are an academic writing expert. Revise the following draft based on the user's instructions.

## REVISION INSTRUCTIONS
{instructions}

## IMPORTANT RULES
1. Return the COMPLETE revised draft, not just the changed parts
2. Maintain the same overall structure unless instructed otherwise
3. Preserve all citations ({{cite_XXX}} references and (Author, Year) citations)
4. Keep the academic tone and formatting
5. Do NOT add commentary or explanations - just return the revised draft

## CURRENT DRAFT
{draft}

## YOUR TASK
Return the complete revised draft below:
"""

    logger.info(f"Calling {model or 'active provider model'} for revision...")

    # Retry loop with circuit breaker
    last_error = None
    for attempt in range(max_retries):
        if not circuit_breaker.allow_request():
            logger.warning("Circuit breaker open, waiting...")
            time.sleep(60)
            continue

        try:
            response = client.generate_content(
                prompt,
            )
            circuit_breaker.record_success()
            revised = response.text.strip()
            break
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            # Check if transient error
            transient_patterns = ['rate limit', '429', 'timeout', 'connection', 'overloaded', 'capacity']
            is_transient = any(p in error_str for p in transient_patterns)

            if is_transient and attempt < max_retries - 1:
                circuit_breaker.record_failure(e)
                wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                logger.warning(f"Transient error, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                circuit_breaker.record_failure(e)
                raise
    else:
        raise last_error or Exception("Max retries exceeded")

    revised = response.text.strip()

    # Clean up any markdown code blocks if Gemini wrapped the response
    if revised.startswith("```markdown"):
        revised = revised[len("```markdown"):].strip()
    if revised.startswith("```"):
        revised = revised[3:].strip()
    if revised.endswith("```"):
        revised = revised[:-3].strip()

    return revised


# Backward-compatible alias while runtime shifts away from Gemini-only naming.
call_gemini_revise = call_llm_revise


def _get_next_version(folder: Path, base_name: str) -> str:
    """Find the next available version suffix (v2, v3, v4, ...)."""
    version = 2
    while True:
        suffix = f"v{version}"
        if not (folder / f"{base_name}_{suffix}.md").exists():
            return suffix
        version += 1
        if version > 99:  # Safety limit
            return f"v{version}"


def score_draft_simple(text: str) -> Dict[str, Any]:
    """
    Simple quality scoring for revisions (V1 simplified version).

    Returns dict with overall_score (0-100) and component scores.
    Uses proportional scoring so small improvements are visible.
    """
    # Word count (30 points) - tiered scoring for sensitivity at all lengths
    # 0-100 words: 0-5 points (0.05 per word)
    # 100-500 words: 5-15 points
    # 500-1500 words: 15-25 points
    # 1500-3000 words: 25-30 points
    word_count = len(text.split())
    if word_count <= 100:
        word_score = int(word_count * 0.05)
    elif word_count <= 500:
        word_score = 5 + int((word_count - 100) / 400 * 10)
    elif word_count <= 1500:
        word_score = 15 + int((word_count - 500) / 1000 * 10)
    else:
        word_score = min(30, 25 + int((word_count - 1500) / 1500 * 5))

    # Citations (25 points) - detect both {cite_X} and (Author, Year) formats
    cite_format = len(re.findall(r'\{cite_\d+\}', text))
    # Match various parenthetical citation formats:
    # (Smith, 2020), (Smith & Jones, 2020), (Smith et al., 2020)
    parenthetical = len(re.findall(
        r'\([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+|\s+et\s+al\.?)?,?\s*\d{4}\)',
        text
    ))
    citations = cite_format + parenthetical
    # Proportional: 1 citation = ~1.67 points, caps at 15 citations
    citation_score = min(25, int((citations / 15) * 25))

    # Structure (25 points) - headers, proportional
    headers = len(re.findall(r'^#{1,3}\s+.+$', text, re.MULTILINE))
    # Proportional: 1 header = ~4.2 points, caps at 6 headers
    structure_score = min(25, int((headers / 6) * 25))

    # Completeness (20 points) - key sections
    sections_found = 0
    for keyword in ['introduction', 'literature', 'methodology', 'results', 'conclusion', 'discussion']:
        if keyword.lower() in text.lower():
            sections_found += 1
    completeness_score = min(20, sections_found * 4)

    score = word_score + citation_score + structure_score + completeness_score

    return {
        'overall_score': min(100, score),
        'word_count': word_count,
        'word_score': word_score,
        'citations': citations,
        'citation_score': citation_score,
        'headers': headers,
        'structure_score': structure_score,
        'sections_found': sections_found,
        'completeness_score': completeness_score,
    }


def revise_draft(
    target: Path,
    instructions: str,
    version_suffix: str = None,
    model: str = "gemini-3-flash-preview",
) -> Dict[str, Any]:
    """
    Revise an existing draft based on instructions.

    Args:
        target: Path to output folder or draft file
        instructions: Revision instructions
        version_suffix: Suffix for output files (auto-detect if None)
        model: Gemini model to use

    Returns:
        Dict with paths to revised outputs and quality scores
    """
    # Resolve target
    if target.is_file():
        draft_path = target
        output_dir = target.parent
    elif target.is_dir():
        draft_path = find_draft_in_folder(target)
        if not draft_path:
            raise FileNotFoundError(f"No draft found in {target}")
        # Use exports/ subfolder if it exists
        output_dir = target / "exports" if (target / "exports").exists() else target
    else:
        raise FileNotFoundError(f"Target not found: {target}")

    logger.info(f"Revising: {draft_path}")

    # Read current draft
    draft_text = draft_path.read_text(encoding='utf-8')

    # Score before
    score_before = score_draft_simple(draft_text)
    logger.info(f"Quality before: {score_before['overall_score']}/100")

    # Call Gemini for revision
    revised_text = call_gemini_revise(draft_text, instructions, model=model)

    # Score after
    score_after = score_draft_simple(revised_text)
    logger.info(f"Quality after: {score_after['overall_score']}/100")

    # Determine output filenames
    base_name = draft_path.stem
    # Remove existing version suffix if present
    base_name = re.sub(r'_v\d+$', '', base_name)

    # Auto-detect next version if not specified
    if version_suffix is None:
        version_suffix = _get_next_version(output_dir, base_name)

    md_name = f"{base_name}_{version_suffix}.md"
    pdf_name = f"{base_name}_{version_suffix}.pdf"
    docx_name = f"{base_name}_{version_suffix}.docx"

    md_path = output_dir / md_name
    pdf_path = output_dir / pdf_name
    docx_path = output_dir / docx_name

    # Save revised markdown
    md_path.write_text(revised_text, encoding='utf-8')
    logger.info(f"Saved: {md_path}")

    # Export PDF
    title = base_name.replace("_", " ").title()
    if export_pdf(md_path, pdf_path):
        logger.info(f"Exported: {pdf_path}")
    else:
        logger.warning("PDF export failed")
        pdf_path = None

    # Export DOCX
    if export_docx(md_path, docx_path):
        logger.info(f"Exported: {docx_path}")
    else:
        logger.warning("DOCX export failed")
        docx_path = None

    # Calculate delta
    delta = score_after['overall_score'] - score_before['overall_score']

    return {
        'md_path': md_path,
        'pdf_path': pdf_path,
        'docx_path': docx_path,
        'score_before': score_before['overall_score'],
        'score_after': score_after['overall_score'],
        'delta': delta,
        'word_count': len(revised_text.split()),
        'word_count_before': score_before['word_count'],
        'citations_before': score_before['citations'],
        'citations_after': score_after['citations'],
    }
