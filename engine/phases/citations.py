#!/usr/bin/env python3
"""
ABOUTME: Citation management phase — dedupe, scrape, quality filter, claim-level verification
ABOUTME: Existence of a source is settled upstream; this phase decides what reaches the writers

Three separate checks apply to a citation, and they answer different questions:

1. Does the work exist?  Settled upstream in CitationResearcher, by
   multi-source DOI confirmation across Crossref / OpenAlex / Semantic Scholar.
2. Is the record well formed?  CitationQualityFilter (broken URLs, junk
   metadata, no topical keyword overlap).
3. Is the source actually about what it is cited for?  CitationClaimVerifier,
   run below. A real, well-formed, multi-source-confirmed paper can still be
   irrelevant to the paper it was gathered for.
"""

import json
import logging

from .context import DraftContext

logger = logging.getLogger(__name__)


def run_citation_management(ctx: DraftContext) -> None:
    """
    Execute the citation management pipeline (deterministic, no LLM).

    Mutates ctx: citation_database, citation_summary
    """
    from utils.agent_runner import rate_limit_delay
    from utils.citation_database import CitationDatabase, save_citation_database, load_citation_database
    from utils.deduplicate_citations import deduplicate_citations
    from utils.scrape_citation_titles import TitleScraper
    from utils.scrape_citation_metadata import MetadataScraper
    from utils.citation_quality_filter import CitationQualityFilter

    if ctx.verbose:
        print("\n📚 PHASE 2.5: CITATION MANAGEMENT")

    # Create citation database from Scout results
    scout_citations = ctx.scout_result['citations']
    for i, citation in enumerate(scout_citations, start=1):
        citation.id = f"cite_{i:03d}"

    # Map CLI-style values to internal CitationStyle format
    style_map = {"apa": "APA 7th", "ieee": "IEEE", "nalt": "NALT", "chicago": "Chicago", "mla": "MLA"}
    resolved_style = style_map.get(ctx.citation_style, "APA 7th")

    # Import get_language_name from text_utils (shared to avoid circular imports)
    from utils.text_utils import get_language_name

    ctx.citation_database = CitationDatabase(
        citations=scout_citations,
        citation_style=resolved_style,
        draft_language=get_language_name(ctx.language).lower(),
    )

    # Deduplicate citations
    deduplicated_citations, dedup_stats = deduplicate_citations(
        ctx.citation_database.citations,
        strategy='keep_best',
        verbose=ctx.verbose,
    )
    ctx.citation_database.citations = deduplicated_citations

    # Scrape titles and metadata for web sources
    title_scraper = TitleScraper(verbose=False)
    title_scraper.scrape_citations(ctx.citation_database.citations)

    metadata_scraper = MetadataScraper(verbose=False)
    metadata_scraper.scrape_citations(ctx.citation_database.citations)

    # Save citation database to research folder
    citation_db_path = ctx.folders['research'] / "bibliography.json"
    save_citation_database(ctx.citation_database, citation_db_path)

    # Quality filtering.
    #
    # strict_mode was False here, which is an override: the class defaults to
    # True. Lenient mode drops only invalid_url and invalid_metadata and lets
    # every other critical validator issue through into the finished paper.
    # There is no documented reason for the pipeline to be more permissive than
    # the library default, so it now uses the strict default.
    filter_obj = CitationQualityFilter(strict_mode=True)
    filter_obj.filter_database(citation_db_path, citation_db_path, topic=ctx.topic)

    # Reload filtered database
    ctx.citation_database = load_citation_database(citation_db_path)

    # Claim-level verification: is each surviving source actually about the
    # topic it was gathered for? Runs after quality filtering so no LLM call is
    # spent judging a citation that was about to be discarded anyway, and after
    # metadata scraping so abstracts are populated for the judge to read.
    _run_claim_verification(ctx, citation_db_path)

    if ctx.verbose:
        print(f"\u2705 Citations: {len(ctx.citation_database.citations)} unique")

    # MILESTONE: Research Complete - Stream to user
    if ctx.streamer:
        ctx.streamer.stream_research_complete(
            sources_count=len(ctx.citation_database.citations),
            bibliography_path=citation_db_path,
        )

    if ctx.tracker:
        ctx.tracker.update_phase(
            "structure",
            progress_percent=23,
            sources_count=len(ctx.citation_database.citations),
            details={"stage": "research_complete", "milestone": "research_complete"},
        )

    # Build citation summary for writing agents
    ctx.citation_summary = _build_citation_summary(ctx.citation_database)

    rate_limit_delay()


def _run_claim_verification(ctx: DraftContext, citation_db_path) -> None:
    """
    Judge every surviving citation against the paper topic, then act on it.

    Why the topic and not individual sentences: this phase runs before any
    draft exists, so the topic is the only claim available. Sentence-level
    verification needs draft text and lives in
    utils.citation_claim_verifier.run_citation_claim_verification.

    Writes two artifacts into the research folder regardless of outcome:
      citation_claim_verification.md    human-readable report
      citation_claim_verification.json  per-citation verdicts

    A citation judged IRRELEVANT is removed only when the judge's confidence
    clears claim_verification_min_confidence, and never if removing would empty
    the database. Both guards exist because the judge is a language model and a
    wrong removal silently shrinks the bibliography.

    Any failure here is logged and swallowed: a judge outage must not destroy a
    run that already has verified citations.
    """
    from utils.citation_database import save_citation_database
    from utils.citation_claim_verifier import (
        CitationClaimVerifier,
        VERDICT_IRRELEVANT,
        summarize_verdicts,
    )

    validation_cfg = getattr(ctx.config, 'validation', None) if ctx.config else None

    if validation_cfg is not None and not validation_cfg.enable_claim_verification:
        logger.info("Claim-level citation verification disabled (enable_claim_verification=False) — skipping")
        return

    citations = ctx.citation_database.citations if ctx.citation_database else []
    if not citations:
        logger.info("Claim-level citation verification: no citations to check")
        return

    if ctx.model is None:
        # Say which check did not run. Silence here would look identical to a
        # clean pass.
        logger.warning(
            "Claim-level citation verification SKIPPED: no model configured. "
            f"{len(citations)} citations were NOT checked against the topic."
        )
        return

    try:
        verifier = CitationClaimVerifier(
            model=ctx.model,
            citation_database=ctx.citation_database,
            max_pairs=len(citations),
        )
        verdicts = verifier.verify_citations_against_topic(ctx.topic)
    except Exception as e:
        logger.warning(f"Claim-level citation verification failed: {e}")
        logger.warning("Continuing with unverified citation-topic relevance...")
        return

    if not verdicts:
        logger.info("Claim-level citation verification produced no verdicts")
        return

    stats = summarize_verdicts(verdicts)

    # Persist the evidence before acting on it.
    try:
        research_dir = ctx.folders['research']
        (research_dir / "citation_claim_verification.md").write_text(
            verifier.format_report(verdicts), encoding='utf-8'
        )
        (research_dir / "citation_claim_verification.json").write_text(
            json.dumps(
                {'topic': ctx.topic, 'stats': stats, 'verdicts': [v.to_dict() for v in verdicts]},
                indent=2,
                ensure_ascii=False,
            ),
            encoding='utf-8',
        )
    except Exception as e:
        logger.warning(f"Could not write claim verification report: {e}")

    logger.info(
        f"Claim-level citation verification: {stats['total_pairs']} checked, "
        f"{stats['relevant']} relevant, {stats['irrelevant']} irrelevant, "
        f"{stats['uncertain']} uncertain"
    )

    drop_enabled = validation_cfg is None or validation_cfg.claim_verification_drop_irrelevant
    min_confidence = validation_cfg.claim_verification_min_confidence if validation_cfg else 0.7

    if not drop_enabled:
        if ctx.verbose and stats['irrelevant']:
            print(
                f"⚠️  {stats['irrelevant']} citations judged irrelevant to the topic "
                f"(reported only; removal disabled)"
            )
        return

    drop_ids = {
        v.citation_id
        for v in verdicts
        if v.verdict == VERDICT_IRRELEVANT and v.confidence >= min_confidence
    }
    if not drop_ids:
        return

    remaining = [c for c in ctx.citation_database.citations if c.id not in drop_ids]

    if not remaining:
        # Removing everything is far more likely to be a bad judge run than a
        # bibliography that is entirely off-topic. Report it, change nothing.
        logger.warning(
            f"Claim verification would have removed ALL {len(drop_ids)} citations. "
            f"Keeping them and reporting instead; see citation_claim_verification.md."
        )
        return

    for v in verdicts:
        if v.citation_id in drop_ids:
            logger.info(
                f"Removing off-topic citation {v.citation_id} "
                f"(confidence {v.confidence:.2f}): {v.reasoning[:120]}"
            )

    ctx.citation_database.citations = remaining
    save_citation_database(ctx.citation_database, citation_db_path)

    if ctx.verbose:
        print(
            f"🔎 Claim check: removed {len(drop_ids)} citations judged irrelevant "
            f"to the topic (confidence >= {min_confidence:.2f})"
        )


def _build_citation_summary(citation_database) -> str:
    """Build comprehensive citation database string for writing agent prompts."""
    citation_summary = f"\n\n{'='*80}\n## CITATION DATABASE - {len(citation_database.citations)} CITATIONS AVAILABLE\n{'='*80}\n\n"
    citation_summary += "\u26a0\ufe0f  **CRITICAL CITATION RESTRICTION** \u26a0\ufe0f\n\n"
    citation_summary += "You MUST ONLY cite papers from this database. DO NOT:\n"
    citation_summary += "- Cite papers from your training data\n"
    citation_summary += "- Invent or hallucinate citations\n"
    citation_summary += "- Reference papers not listed below\n"
    citation_summary += "- Use author names not in this database\n\n"
    citation_summary += "Citation format: Use {{cite_XXX}} where XXX is the citation ID shown below.\n"
    citation_summary += f"\n{'='*80}\n\n"

    for i, citation in enumerate(citation_database.citations, 1):
        authors_str = ", ".join(citation.authors[:3])
        if len(citation.authors) > 3:
            authors_str += " et al."

        citation_summary += f"{i}. **[{citation.id}]** {authors_str} ({citation.year})\n"
        citation_summary += f"   Title: {citation.title}\n"

        if citation.doi:
            citation_summary += f"   DOI: {citation.doi}\n"
        if citation.journal:
            citation_summary += f"   Journal: {citation.journal}\n"
        if citation.abstract:
            abstract_preview = citation.abstract[:300]
            if len(citation.abstract) > 300:
                abstract_preview += "..."
            citation_summary += f"   Abstract: {abstract_preview}\n"

        citation_summary += f"   Citation format: {{{{{citation.id}}}}}\n\n"

    citation_summary += f"\n{'='*80}\n"
    citation_summary += f"Total citations available: {len(citation_database.citations)}\n"
    citation_summary += "Remember: ONLY cite from this list. No external citations allowed.\n"
    citation_summary += f"{'='*80}\n"

    return citation_summary
