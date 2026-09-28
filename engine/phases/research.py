#!/usr/bin/env python3
"""
ABOUTME: Research phase — Scout, Scribe, Signal agents
ABOUTME: Discovers citations, summarizes papers, identifies research gaps
"""

import re
import logging
from pathlib import Path
from typing import List

from .context import DraftContext

logger = logging.getLogger(__name__)


def run_research_phase(ctx: DraftContext) -> None:
    """
    Execute the research phase: Scout -> Scribe -> Signal.

    Mutates ctx: scout_result, scout_output, scribe_output, signal_output
    """
    from utils.agent_runner import run_agent, rate_limit_delay, research_citations_via_api
    from utils.text_utils import smart_truncate

    if ctx.verbose:
        print("\n📚 PHASE 1: RESEARCH")

    if ctx.tracker:
        ctx.tracker.log_activity("🔍 Starting academic research", event_type="search", phase="research")
        ctx.tracker.update_phase("research", progress_percent=5, details={"stage": "starting_research"})
        ctx.tracker.check_cancellation()

    # Prepare research topics
    topic_context = ctx.topic
    if ctx.blurb:
        topic_context = f"{ctx.topic}\n\nFocus/Context: {ctx.blurb}"

    research_topics = [
        f"{ctx.topic} fundamentals and background",
        f"{ctx.topic} current state of research",
        f"{ctx.topic} methodology and approaches",
        f"{ctx.topic} applications and case studies",
        f"{ctx.topic} challenges and limitations",
        f"{ctx.topic} future directions and implications",
    ]
    if ctx.blurb:
        research_topics.insert(0, f"{ctx.topic} - {ctx.blurb}")
    research_topics = list(ctx.user_sources) + research_topics

    # -----------------------------------------------------------------------
    # AGENT: Scout
    # -----------------------------------------------------------------------
    try:
        def progress_callback(message: str, event_type: str) -> None:
            if ctx.tracker:
                ctx.tracker.log_activity(message, event_type=event_type, phase="research")

        min_citations = ctx.word_targets['min_citations']
        deep_research_min = ctx.word_targets['deep_research_min_sources']

        ctx.scout_result = research_citations_via_api(
            model=ctx.model,
            research_topics=research_topics,
            output_path=ctx.folders['research'] / "scout_raw.md",
            target_minimum=min_citations,
            verbose=ctx.verbose,
            use_deep_research=True,
            topic=ctx.topic,
            scope=topic_context + ctx.user_material,
            seed_references=ctx.user_sources,
            min_sources_deep=deep_research_min,
            progress_callback=progress_callback,
        )

        if ctx.verbose:
            print(f"\u2705 Scout: {ctx.scout_result['count']} citations found")

        if ctx.tracker:
            for i, citation in enumerate(ctx.scout_result.get('citations', [])[:10]):
                ctx.tracker.log_source_found(
                    title=citation.title,
                    authors=citation.authors[:3] if citation.authors else None,
                    year=citation.year,
                    source_type=citation.api_source or "paper",
                    doi=getattr(citation, 'doi', None),
                    url=getattr(citation, 'url', None),
                    verified=True,
                )
            if len(ctx.scout_result.get('citations', [])) > 10:
                remaining = len(ctx.scout_result['citations']) - 10
                ctx.tracker.log_activity(f"...and {remaining} more sources", event_type="found", phase="research")
            ctx.tracker.update_research(sources_count=ctx.scout_result['count'], phase_detail="Scout completed")

        ctx.scout_output = (ctx.folders['research'] / "scout_raw.md").read_text(encoding='utf-8')
        from utils.citation_database import Citation
        known = {c.title.casefold() for c in ctx.scout_result["citations"]}
        for source in ctx.user_sources:
            if source.casefold() not in known:
                supplied = Citation(
                    citation_id="", authors=["User supplied"], year=0, title=source,
                    source_type="report", api_source="User supplied",
                )
                supplied.verification_status = "user_supplied"
                supplied.verification_notes = "Provided by user; scholarly metadata not independently confirmed"
                ctx.scout_result["citations"].append(supplied)
        ctx.scout_result["count"] = len(ctx.scout_result["citations"])
        ctx.scout_output += "\n\n## User supplied sources\n" + "\n".join(
            f"- {source}" for source in ctx.user_sources
        ) + ctx.user_material
        (ctx.folders["research"] / "scout_raw.md").write_text(ctx.scout_output, encoding="utf-8")

    except ValueError as e:
        raise ValueError(f"Insufficient citations for draft generation: {str(e)}")

    rate_limit_delay()

    # -----------------------------------------------------------------------
    # AGENT: Scribe
    # -----------------------------------------------------------------------
    if ctx.tracker:
        ctx.tracker.log_activity("📝 Summarizing research findings...", event_type="info", phase="research")

    ctx.scribe_output = run_agent(
        model=ctx.model,
        name="Scribe - Summarize Papers",
        prompt_path="prompts/01_research/scribe.md",
        user_input=f"Summarize these research findings:\n\n{smart_truncate(ctx.scout_output, max_chars=32000, preserve_json=True)}\n\nRequired user sources: {ctx.user_sources}\n{ctx.user_material}",
        save_to=ctx.folders['research'] / "combined_research.md",
        skip_validation=ctx.skip_validation,
        verbose=ctx.verbose,
        token_tracker=ctx.token_tracker,
        token_stage="scribe",
    )

    if ctx.tracker:
        ctx.tracker.log_activity("\u2705 Research summaries complete", event_type="found", phase="research")

    # Split scribe output into individual paper files
    if ctx.tracker:
        ctx.tracker.log_activity("📚 Organizing research papers...", event_type="info", phase="research")

    split_scribe_to_papers(ctx.scribe_output, ctx.folders['papers'], verbose=ctx.verbose)
    extract_all_citations_as_papers(
        scout_output_path=ctx.folders['research'] / "scout_raw.md",
        papers_dir=ctx.folders['papers'],
        verbose=ctx.verbose,
    )

    if ctx.tracker:
        ctx.tracker.log_activity("\u2705 All research papers organized", event_type="found", phase="research")

    rate_limit_delay()

    # -----------------------------------------------------------------------
    # AGENT: Signal
    # -----------------------------------------------------------------------
    if ctx.tracker:
        ctx.tracker.log_activity("🔍 Analyzing research gaps...", event_type="info", phase="research")

    ctx.signal_output = run_agent(
        model=ctx.model,
        name="Signal - Research Gaps",
        prompt_path="prompts/01_research/signal.md",
        user_input=f"Analyze research gaps:\n\n{smart_truncate(ctx.scribe_output, max_chars=32000)}\n{ctx.user_material}",
        save_to=ctx.folders['research'] / "research_gaps.md",
        skip_validation=ctx.skip_validation,
        verbose=ctx.verbose,
        token_tracker=ctx.token_tracker,
        token_stage="signal",
    )

    if ctx.tracker:
        ctx.tracker.log_activity("\u2705 Research gaps identified", event_type="found", phase="research")

    rate_limit_delay()


# ---------------------------------------------------------------------------
# Helper functions (only used by research phase)
# ---------------------------------------------------------------------------

def _slugify(text: str, max_length: int = 30) -> str:
    """Convert text to a safe filename slug."""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '_', slug).strip('_')
    return slug[:max_length]


def split_scribe_to_papers(scribe_output: str, papers_dir: Path, verbose: bool = True) -> List[Path]:
    """
    Split the combined scribe output into individual paper files.

    Parses the scribe markdown to find paper sections and saves each
    as a separate file in papers_dir.

    Returns list of created file paths.
    """
    created_files = []

    paper_pattern = re.compile(
        r'^##\s*(?:Paper\s*)?(\d+)[:.]\s*(.+?)$',
        re.MULTILINE,
    )

    matches = list(paper_pattern.finditer(scribe_output))

    if not matches:
        alt_pattern = re.compile(
            r'^##\s+(.+?)$\n\*\*Authors?:\*\*\s*(.+?)$',
            re.MULTILINE,
        )
        matches = list(alt_pattern.finditer(scribe_output))

        if not matches:
            if verbose:
                print("   \u26a0\ufe0f  Could not split scribe output into papers")
            return created_files

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(scribe_output)

        paper_content = scribe_output[start:end].strip()

        try:
            paper_num = match.group(1) if match.lastindex >= 1 else str(i + 1)
            title = match.group(2) if match.lastindex >= 2 else f"paper_{i+1}"
        except Exception:
            paper_num = str(i + 1)
            title = f"paper_{i+1}"

        author_match = re.search(r'\*\*Authors?:\*\*\s*([^*\n]+)', paper_content)
        year_match = re.search(r'\*\*Year:\*\*\s*(\d{4})', paper_content)

        author = _slugify(author_match.group(1).split(',')[0] if author_match else 'unknown', 15)
        year = year_match.group(1) if year_match else 'na'
        title_slug = _slugify(title, 40)

        filename = f"paper_{int(paper_num):03d}_{author}_{year}_{title_slug}.md"
        file_path = papers_dir / filename

        file_path.write_text(paper_content, encoding='utf-8')
        created_files.append(file_path)

    if verbose and created_files:
        print(f"   \u2705 Split into {len(created_files)} individual paper files")

    return created_files


def extract_all_citations_as_papers(
    scout_output_path: Path,
    papers_dir: Path,
    verbose: bool = True,
) -> List[Path]:
    """
    Extract ALL citations from scout_raw.md as individual paper files.

    This ensures all citations (typically 50+) become accessible paper files
    for Cursor usage, not just the subset analyzed by Scribe (typically 5-10).
    """
    created_files = []

    if not scout_output_path.exists():
        if verbose:
            print("   \u26a0\ufe0f  scout_raw.md not found, skipping citation extraction")
        return created_files

    content = scout_output_path.read_text(encoding='utf-8')

    citation_pattern = r'####\s+\d+\.\s+(.+?)(?=\n####\s+\d+\.|\n---|\Z)'
    matches = list(re.finditer(citation_pattern, content, re.DOTALL))

    if not matches:
        if verbose:
            print("   \u26a0\ufe0f  No citations found in scout_raw.md")
        return created_files

    if verbose:
        print(f"   📚 Extracting {len(matches)} citations as paper files...")

    existing_papers = {f.name for f in papers_dir.glob('paper_*.md')}
    start_idx = len(existing_papers) + 1

    for i, match in enumerate(matches, start=start_idx):
        section = match.group(1).strip()

        title_line = section.split('\n')[0].strip()
        title = re.sub(r'^\*\*|\*\*$', '', title_line).strip()

        author_match = re.search(r'\*\*Authors?\*\*:\s*(.+?)(?:\n|$)', section)
        authors_str = author_match.group(1).strip() if author_match else 'Unknown'
        authors = [a.strip() for a in authors_str.split(',')]

        year_match = re.search(r'\*\*Year\*\*:\s*(\d{4})', section)
        year = year_match.group(1) if year_match else 'na'

        doi_match = re.search(r'\*\*DOI\*\*:\s*(.+?)(?:\n|$)', section)
        doi = doi_match.group(1).strip() if doi_match else None

        url_match = re.search(r'\*\*URL\*\*:\s*(.+?)(?:\n|$)', section)
        url = url_match.group(1).strip() if url_match else None

        abstract_match = re.search(r'\*\*Abstract\*\*:\s*(.+?)(?:\n\n|\n\*\*|\Z)', section, re.DOTALL)
        abstract = abstract_match.group(1).strip() if abstract_match else None

        author = authors[0].split()[0] if authors and authors[0] != 'Unknown' else 'unknown'
        title_slug = _slugify(title, 40)

        filename = f"paper_{i:03d}_{author}_{year}_{title_slug}.md"
        filepath = papers_dir / filename

        if filename in existing_papers:
            continue

        paper_content = f"""# {title}

**Authors:** {', '.join(authors) if authors else 'Unknown'}
**Year:** {year}
**DOI:** {doi or 'N/A'}
**URL:** {url or 'N/A'}

## Abstract

{abstract or 'No abstract available in source'}

## Citation Details

{section[:2000]}  # Truncate if very long

---
*Extracted from citation research database - all {len(matches)} citations available*
"""

        filepath.write_text(paper_content, encoding='utf-8')
        created_files.append(filepath)

    if verbose and created_files:
        print(f"   \u2705 Extracted {len(created_files)} additional citations as papers")
        print(f"   📊 Total papers now: {len(list(papers_dir.glob('paper_*.md')))}")

    return created_files
