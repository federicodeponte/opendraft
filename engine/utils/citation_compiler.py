#!/usr/bin/env python3
"""
ABOUTME: Citation compiler for deterministic citation ID replacement and missing citation research
ABOUTME: Replaces {cite_001} with formatted citations, researches {cite_MISSING:topic} placeholders, generates reference lists
"""

import re
import logging
from typing import Any, Dict, List, Tuple, Set, Optional
from pathlib import Path

from utils.citation_database import Citation, CitationDatabase, CitationStyle
from utils.api_citations import CitationResearcher

logger = logging.getLogger(__name__)


class CitationCompiler:
    """Deterministic citation compiler with automatic missing citation research."""

    def __init__(self, database: CitationDatabase, model: Optional[Any] = None, complexity_threshold: float = 0.7):
        """
        Initialize compiler with citation database.

        Args:
            database: CitationDatabase with all available citations
            model: Optional Gemini model for researching missing citations (used as LLM fallback)
            complexity_threshold: Threshold for identifying "complex" sections (0-1 scale, default: 0.7)
        """
        self.database = database
        self.citation_lookup = {c.id: c for c in database.citations}
        self.style = database.citation_style
        self.model = model
        self.research_enabled = model is not None
        self.complexity_threshold = complexity_threshold

        # NALT footnote state
        self._nalt_footnote_counter = 0
        self._nalt_footnote_definitions: List[str] = []

        # Initialize API-backed citation researcher.
        # Discovery: Crossref / OpenAlex / Semantic Scholar / Gemini Grounded.
        # Confirmation: multi-source by DOI, on by default (see CitationResearcher).
        # Semantic Scholar can be disabled via env var if rate limited (403 errors)
        import os
        enable_semantic_scholar = os.environ.get('ENABLE_SEMANTIC_SCHOLAR', 'true').lower() != 'false'

        self.researcher = CitationResearcher(
            gemini_model=model,
            enable_crossref=True,
            enable_semantic_scholar=enable_semantic_scholar,
            enable_gemini_grounded=True,  # Enable Gemini Grounded for web sources
            # Was True. A {cite_MISSING:topic} placeholder is filled in mid-
            # compilation and lands directly in the finished paper, so an
            # LLM-asserted citation here would reach the reader unchecked.
            # Left at the class default (off; explicit opt-in only).
            enable_llm_fallback=False,
            verbose=False  # Will be overridden by method verbose parameter
        )

    def _research_missing_citation(self, topic: str, verbose: bool = True) -> Optional[Citation]:
        """
        Research a missing citation using API-backed fallback chain.

        Uses intelligent fallback: Crossref → Semantic Scholar → Gemini LLM
        Success rate: 95%+ (vs 40% LLM-only)

        Args:
            topic: Topic or description to research
            verbose: Whether to print progress

        Returns:
            Citation object if found, None otherwise
        """
        if not self.research_enabled:
            if verbose:
                print(f"  ⚠️  Research disabled - no model provided")
            return None

        # Set verbose mode on researcher
        self.researcher.verbose = verbose

        # Delegate to CitationResearcher (handles caching internally)
        result = self.researcher.research_citation(topic)

        # Handle both list and single citation (orchestrator now returns list)
        if isinstance(result, list):
            citation = result[0] if result else None
        else:
            citation = result

        if citation:
            # Generate next citation ID
            existing_ids = list(self.citation_lookup.keys())
            if existing_ids:
                # Get max number from cite_XXX
                max_num = max(int(cid.replace("cite_", "")) for cid in existing_ids if cid.startswith("cite_"))
                next_id = f"cite_{max_num + 1:03d}"
            else:
                next_id = "cite_001"

            # Update citation ID
            citation.id = next_id

            # Add to database and lookup
            self.database.citations.append(citation)
            self.citation_lookup[citation.id] = citation

            return citation
        else:
            return None

    def compile_citations(self, text: str, research_missing: bool = True, verbose: bool = True) -> Tuple[str, List[str], List[str]]:
        """
        Replace citation IDs with formatted citations and research missing citations.

        Args:
            text: Text containing {cite_001} and/or {cite_MISSING:topic} patterns
            research_missing: Whether to research {cite_MISSING:topic} placeholders
            verbose: Whether to print progress

        Returns:
            tuple: (formatted_text, list_of_missing_ids, list_of_researched_topics)
        """
        missing_ids: List[str] = []
        researched_topics: List[str] = []

        # Reset NALT footnote state for each compilation
        if self.style == "NALT":
            self._nalt_footnote_counter = 0
            self._nalt_footnote_definitions = []

        # Step 1: Find and research all {cite_MISSING:topic} placeholders
        if research_missing:
            missing_pattern = r'\{cite_MISSING:([^}]+)\}'
            missing_matches = re.findall(missing_pattern, text)

            if missing_matches and verbose:
                unique_topics = list(dict.fromkeys(missing_matches))  # Preserve order, remove duplicates
                print(f"\n🔍 Found {len(missing_matches)} missing citation placeholders ({len(unique_topics)} unique topics)")
                print(f"📚 Researching citations with Scout agent...")

            # Research each unique topic
            unique_topics = list(dict.fromkeys(missing_matches))
            for i, topic in enumerate(unique_topics, 1):
                if verbose:
                    print(f"\n[{i}/{len(unique_topics)}]", end=" ")

                citation = self._research_missing_citation(topic.strip(), verbose=verbose)
                if citation:
                    researched_topics.append(topic.strip())
                    # Create a mapping for this topic to citation ID
                    # We'll replace {cite_MISSING:topic} with {cite_XXX} first
                    text = text.replace(f"{{cite_MISSING:{topic}}}", f"{{{citation.id}}}")

            if verbose and researched_topics:
                print(f"\n✅ Successfully researched {len(researched_topics)}/{len(unique_topics)} citations")

        # Step 2: Replace all {cite_XXX} patterns (including newly created ones from research)
        def replace_citation(match: re.Match) -> str:
            """Replace single citation ID with formatted citation."""
            cite_id = match.group(0).strip('{}')  # Extract cite_001 from {cite_001}

            if cite_id not in self.citation_lookup:
                missing_ids.append(cite_id)
                return f"[MISSING: {cite_id}]"

            citation = self.citation_lookup[cite_id]
            return self.format_in_text_citation(citation)

        # Replace all {cite_XXX} patterns
        citation_pattern = r'\{cite_\d{3}\}'
        formatted_text = re.sub(citation_pattern, replace_citation, text)

        # Step 3: Handle any remaining {cite_MISSING:topic} that couldn't be researched
        remaining_missing_pattern = r'\{cite_MISSING:([^}]+)\}'
        remaining_matches = re.findall(remaining_missing_pattern, formatted_text)
        if remaining_matches:
            # Replace with [MISSING: topic] markers
            for topic in remaining_matches:
                formatted_text = formatted_text.replace(f"{{cite_MISSING:{topic}}}", f"[MISSING: {topic.strip()}]")
                if topic.strip() not in missing_ids:
                    missing_ids.append(f"TOPIC:{topic.strip()}")

        # Step 4: Append NALT footnote definitions
        if self.style == "NALT" and self._nalt_footnote_definitions:
            formatted_text += "\n\n" + "\n\n".join(self._nalt_footnote_definitions)

        return formatted_text, missing_ids, researched_topics

    def format_in_text_citation(self, citation: Citation) -> str:
        """
        Format in-text citation based on style.

        Args:
            citation: Citation to format

        Returns:
            str: Formatted in-text citation (e.g., "(Smith et al., 2023)")
        """
        if self.style == "APA 7th":
            return self._format_apa_in_text(citation)
        elif self.style == "IEEE":
            return self._format_ieee_in_text(citation)
        elif self.style == "NALT":
            return self._format_nalt_in_text(citation)
        elif self.style == "Chicago":
            return self._format_chicago_in_text(citation)
        elif self.style == "MLA":
            return self._format_mla_in_text(citation)
        else:
            raise NotImplementedError(
                f"Citation style '{self.style}' is not yet implemented. "
                f"Supported styles: 'APA 7th', 'IEEE', 'NALT', 'Chicago', 'MLA'. "
                f"See docs/CITATION_STYLES_ROADMAP.md for planned styles."
            )

    def _format_apa_in_text(self, citation: Citation) -> str:
        """Format in-text citation in APA 7th style."""
        authors = citation.authors
        year = citation.year

        if len(authors) == 1:
            return f"({authors[0]}, {year})"
        elif len(authors) == 2:
            return f"({authors[0]} & {authors[1]}, {year})"
        else:
            # 3+ authors use et al.
            return f"({authors[0]} et al., {year})"

    def _format_ieee_in_text(self, citation: Citation) -> str:
        """Format in-text citation in IEEE style (numbered)."""
        # For Phase 1, we'll use citation number from ID
        # cite_001 -> [1], cite_002 -> [2]
        number = citation.id.replace("cite_", "")
        return f"[{int(number)}]"

    def _format_chicago_in_text(self, citation: Citation) -> str:
        """Format in-text citation in Chicago Author-Date style."""
        authors = citation.authors
        year = citation.year

        if len(authors) == 1:
            return f"({authors[0]} {year})"
        elif len(authors) == 2:
            return f"({authors[0]} and {authors[1]} {year})"
        else:
            return f"({authors[0]} et al. {year})"

    def _format_mla_in_text(self, citation: Citation) -> str:
        """Format in-text citation in MLA 9th Edition style."""
        authors = citation.authors

        if len(authors) == 1:
            return f"({authors[0]})"
        elif len(authors) == 2:
            return f"({authors[0]} and {authors[1]})"
        else:
            return f"({authors[0]} et al.)"

    def _format_nalt_in_text(self, citation: Citation) -> str:
        """Format in-text citation as NALT footnote marker [^N]."""
        self._nalt_footnote_counter += 1
        n = self._nalt_footnote_counter
        footnote_text = self._format_nalt_footnote(citation)
        self._nalt_footnote_definitions.append(f"[^{n}]: {footnote_text}")
        return f"[^{n}]"

    def _format_nalt_footnote(self, citation: Citation) -> str:
        """Format NALT footnote text based on source type."""
        source_type = citation.source_type

        if source_type == "case":
            return self._format_nalt_case(citation)
        elif source_type == "statute":
            return self._format_nalt_statute(citation)
        elif source_type == "constitution":
            return self._format_nalt_constitution(citation)
        elif source_type == "treaty":
            return self._format_nalt_treaty(citation)
        elif source_type == "journal":
            return self._format_nalt_journal(citation)
        elif source_type == "book":
            return self._format_nalt_book(citation)
        elif source_type == "website":
            return self._format_nalt_website(citation)
        else:
            # Fallback: book-like format
            return self._format_nalt_book(citation)

    def _format_nalt_case(self, citation: Citation) -> str:
        """Format case citation: *Parties* [Year] Report (Court)"""
        parties = citation.parties or citation.title
        year = citation.year
        law_report = citation.law_report or ""
        court = citation.court or ""

        ref = f"*{parties}* [{year}]"
        if law_report:
            ref += f" {law_report}"
        if court:
            ref += f" ({court})"
        return ref

    def _format_nalt_statute(self, citation: Citation) -> str:
        """Format statute citation: Title Year, section"""
        title = citation.title
        year = citation.year
        section = citation.section or ""

        ref = f"{title} {year}"
        if section:
            ref += f", {section}"
        return ref

    def _format_nalt_constitution(self, citation: Citation) -> str:
        """Format constitution citation: Title Year, section"""
        title = citation.title
        year = citation.year
        section = citation.section or ""

        ref = f"{title} {year}"
        if section:
            ref += f", {section}"
        return ref

    def _format_nalt_treaty(self, citation: Citation) -> str:
        """Format treaty citation: Title (Year of adoption), section"""
        title = citation.title
        year = citation.year
        section = citation.section or ""

        ref = f"{title} ({year})"
        if section:
            ref += f", {section}"
        return ref

    def _format_nalt_journal(self, citation: Citation) -> str:
        """Format journal: Author, 'Title' [Year] (Vol)(Issue) *Journal*, Pages"""
        author_str = self._format_nalt_authors_footnote(citation.authors)
        title = citation.title
        year = citation.year
        journal = citation.journal or ""
        volume = citation.volume
        issue = citation.issue
        pages = citation.pages or ""

        ref = f"{author_str}, '{title}' [{year}]"
        if volume:
            ref += f" ({volume})"
        if issue:
            ref += f"({issue})"
        if journal:
            ref += f" *{journal}*"
        if pages:
            ref += f", {pages}"
        return ref

    def _format_nalt_book(self, citation: Citation) -> str:
        """Format book: Author, *Title* (Publisher Year)"""
        author_str = self._format_nalt_authors_footnote(citation.authors)
        title = citation.title
        publisher = citation.publisher or ""
        year = citation.year

        if publisher:
            ref = f"{author_str}, *{title}* ({publisher} {year})"
        else:
            ref = f"{author_str}, *{title}* ({year})"
        return ref

    def _format_nalt_website(self, citation: Citation) -> str:
        """Format website: Author, 'Title' <URL> accessed Date"""
        author_str = self._format_nalt_authors_footnote(citation.authors)
        title = citation.title
        url = citation.url or ""
        access_date = citation.access_date or ""

        ref = f"{author_str}, '{title}'"
        if url:
            ref += f" <{url}>"
        if access_date:
            ref += f" accessed {access_date}"
        return ref

    def _format_nalt_authors_footnote(self, authors: List[str]) -> str:
        """
        Format authors for NALT footnotes: first name precedes surname.

        Since we only have surname data, we use as-is.
        1-3 authors: listed with 'and' before last.
        4+: first author 'and others'.
        """
        if not authors:
            return ""
        if len(authors) == 1:
            return authors[0]
        elif len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"
        elif len(authors) == 3:
            return f"{authors[0]}, {authors[1]} and {authors[2]}"
        else:
            return f"{authors[0]} and others"

    def _format_nalt_authors_bibliography(self, authors: List[str]) -> str:
        """
        Format authors for NALT bibliography: surname first.

        Since we only have surname data, we use as-is.
        1-3 authors: listed with 'and' before last.
        4+: first author 'and others'.
        """
        if not authors:
            return ""
        if len(authors) == 1:
            return authors[0]
        elif len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"
        elif len(authors) == 3:
            return f"{authors[0]}, {authors[1]} and {authors[2]}"
        else:
            return f"{authors[0]} and others"

    def _format_nalt_bibliography_entry(self, citation: Citation) -> str:
        """Format a single NALT bibliography entry (surname-first author order)."""
        source_type = citation.source_type

        if source_type == "case":
            parties = citation.parties or citation.title
            year = citation.year
            law_report = citation.law_report or ""
            court = citation.court or ""
            ref = f"*{parties}* [{year}]"
            if law_report:
                ref += f" {law_report}"
            if court:
                ref += f" ({court})"
            return ref

        elif source_type == "statute":
            ref = f"{citation.title} {citation.year}"
            if citation.section:
                ref += f", {citation.section}"
            return ref

        elif source_type == "constitution":
            ref = f"{citation.title} {citation.year}"
            if citation.section:
                ref += f", {citation.section}"
            return ref

        elif source_type == "treaty":
            ref = f"{citation.title} ({citation.year})"
            if citation.section:
                ref += f", {citation.section}"
            return ref

        elif source_type == "journal":
            author_str = self._format_nalt_authors_bibliography(citation.authors)
            journal = citation.journal or ""
            volume = citation.volume
            issue = citation.issue
            pages = citation.pages or ""
            ref = f"{author_str}, '{citation.title}' [{citation.year}]"
            if volume:
                ref += f" ({volume})"
            if issue:
                ref += f"({issue})"
            if journal:
                ref += f" *{journal}*"
            if pages:
                ref += f", {pages}"
            return ref

        elif source_type == "website":
            author_str = self._format_nalt_authors_bibliography(citation.authors)
            url = citation.url or ""
            access_date = citation.access_date or ""
            ref = f"{author_str}, '{citation.title}'"
            if url:
                ref += f" <{url}>"
            if access_date:
                ref += f" accessed {access_date}"
            return ref

        else:
            # Default: book-like
            author_str = self._format_nalt_authors_bibliography(citation.authors)
            publisher = citation.publisher or ""
            if publisher:
                return f"{author_str}, *{citation.title}* ({publisher} {citation.year})"
            else:
                return f"{author_str}, *{citation.title}* ({citation.year})"

    def generate_reference_list(self, text: str) -> str:
        """
        Generate reference list from citations used in text.

        Removes placeholder headers and detects content-full sections.
        Prevents dual headers (German placeholder + English actual citations).

        Args:
            text: Text with formatted citations (to determine which were used)

        Returns:
            str: Formatted reference list (header added if section doesn't exist or is placeholder)
        """
        # Find all cited IDs in original format
        cited_ids = self._extract_cited_ids(text)

        # Get citations for cited IDs only
        cited_citations = [
            self.citation_lookup[cid]
            for cid in sorted(cited_ids)
            if cid in self.citation_lookup
        ]

        # Determine header name based on style
        ref_header = "Bibliography" if self.style == "NALT" else "References"

        if not cited_citations:
            # Check if placeholder exists - if so, don't add another header
            if self._has_placeholder_references(text):
                return "\n(No citations found)\n"
            elif f"## {ref_header}" not in text and "## References" not in text:
                return f"## {ref_header}\n\n(No citations found)\n"
            else:
                return "\n(No citations found)\n"

        # Sort alphabetically by first author (APA, NALT, Chicago, MLA)
        if self.style in ("APA 7th", "NALT", "Chicago", "MLA"):
            cited_citations.sort(key=lambda c: c.authors[0].lower() if c.authors else "")

        # Format references (without header initially)
        references = []

        for citation in cited_citations:
            if self.style == "APA 7th":
                ref = self._format_apa_reference(citation)
            elif self.style == "IEEE":
                ref = self._format_ieee_reference(citation)
            elif self.style == "NALT":
                ref = self._format_nalt_bibliography_entry(citation)
            elif self.style == "Chicago":
                ref = self._format_chicago_reference(citation)
            elif self.style == "MLA":
                ref = self._format_mla_reference(citation)
            else:
                raise NotImplementedError(
                    f"Citation style '{self.style}' is not yet implemented. "
                    f"Supported styles: 'APA 7th', 'IEEE', 'NALT', 'Chicago', 'MLA'. "
                    f"See docs/CITATION_STYLES_ROADMAP.md for planned styles."
                )

            references.append(ref)

        references_content = "\n\n".join(references)

        # Check if section already has CONTENT-FULL references (not just placeholder)
        has_content_full_refs = self._has_content_full_references(text)

        if has_content_full_refs:
            # References already exist with actual citations - don't duplicate
            logger.warning(
                "References section already exists with content - skipping generation. "
                "This may indicate the text was already compiled."
            )
            return ""
        else:
            # Either no References/Bibliography section, or only placeholder exists
            # Add full section with header
            return f"\n\n## {ref_header}\n\n{references_content}"

    def _extract_cited_ids(self, text: str) -> Set[str]:
        """Extract all citation IDs mentioned in text."""
        # Find both {cite_XXX} and formatted citations
        # For now, look for {cite_XXX} patterns
        pattern = r'\{cite_\d{3}\}'
        matches = re.findall(pattern, text)
        return {match.strip('{}') for match in matches}

    def _has_placeholder_references(self, text: str) -> bool:
        """
        Check if text has placeholder References section (no actual citations).

        Args:
            text: Text to check

        Returns:
            bool: True if placeholder detected, False otherwise
        """
        # Pattern for References header followed by placeholder text
        placeholder_patterns = [
            r'##\s+(?:References|Literaturverzeichnis|Bibliograf[íi]a|Références)\s*\n+\s*\[(?:Wird automatisch generiert|To be completed|A generar|À compléter)\]',
            r'##\s+(?:References|Literaturverzeichnis|Bibliograf[íi]a|Références)\s*\n+\s*\((?:No citations|Keine Zitate|Sin citas)\)',
        ]

        return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in placeholder_patterns)

    def _has_content_full_references(self, text: str) -> bool:
        """
        Check if text has References section with actual citations (not placeholder).

        Detects content by looking for DOI URLs, year patterns, and citation formatting.

        Args:
            text: Text to check

        Returns:
            bool: True if section has real content, False if placeholder/empty
        """
        # Universal References header patterns (all languages)
        references_patterns = [
            r'##\s+References\s*\n+(.*?)(?=\n##|\Z)',
            r'##\s+Bibliography\s*\n+(.*?)(?=\n##|\Z)',
            r'##\s+Literaturverzeichnis\s*\n+(.*?)(?=\n##|\Z)',
            r'##\s+Referenzen\s*\n+(.*?)(?=\n##|\Z)',
            r'##\s+Bibliograf[íi]a\s*\n+(.*?)(?=\n##|\Z)',
            r'##\s+Références\s*\n+(.*?)(?=\n##|\Z)',
        ]

        for pattern in references_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section_content = match.group(1).strip()

                # Check for placeholder indicators
                placeholder_indicators = [
                    r'\[(?:Wird automatisch generiert|To be completed|A generar|À compléter)\]',
                    r'^\s*$',  # Empty
                    r'^\(No citations',
                ]

                is_placeholder = any(
                    re.search(ind, section_content, re.IGNORECASE)
                    for ind in placeholder_indicators
                )

                if is_placeholder:
                    return False  # Placeholder, not content-full

                # Check for actual citation indicators
                citation_indicators = [
                    r'https?://doi\.org/',  # DOI URLs
                    r'\(\d{4}\)',  # Year in parentheses
                    r'et al\.',  # Author formatting
                    r'&',  # Author separators in APA
                    r'\*\w+\*',  # Italics (journal/book titles)
                ]

                has_citations = any(
                    re.search(ind, section_content)
                    for ind in citation_indicators
                )

                return has_citations  # Has actual citations

        # No References section found
        return False

    def _format_apa_reference(self, citation: Citation) -> str:
        """Format full reference in APA 7th style."""
        authors = citation.authors
        year = citation.year
        title = citation.title

        # Format authors (APA 7th: for 21+ authors, show first 19...last author)
        # For practical purposes, limit to 7 authors (6 + et al.)
        MAX_AUTHORS = 7
        if len(authors) == 1:
            author_str = f"{authors[0]}."
        elif len(authors) == 2:
            author_str = f"{authors[0]}, & {authors[1]}."
        elif len(authors) <= MAX_AUTHORS:
            author_str = ", ".join(authors[:-1]) + f", & {authors[-1]}."
        else:
            # More than 7 authors: show first 6, then "... & last author"
            author_str = ", ".join(authors[:6]) + f", ... & {authors[-1]}."

        # Format based on source type
        source_type = citation.source_type

        if source_type == 'journal':
            journal = citation.journal or ""
            volume = citation.volume
            issue = citation.issue
            pages = citation.pages or ""
            doi = citation.doi or ""
            url = citation.url or ""

            ref = f"{author_str} ({year}). {title}. *{journal}*"
            if volume:
                ref += f", *{volume}*"
            if issue:
                ref += f"({issue})"
            if pages:
                ref += f", {pages}"
            if doi:
                ref += f". https://doi.org/{doi}"
            elif url:
                ref += f". {url}"
            ref += "."

        elif source_type == 'book':
            publisher = citation.publisher or ""
            doi = citation.doi or ""
            url = citation.url or ""

            ref = f"{author_str} ({year}). *{title}*."
            if publisher:  # Only add publisher if it exists
                ref = f"{author_str} ({year}). *{title}*. {publisher}."
            # Add DOI/URL for books
            if doi:
                ref += f" https://doi.org/{doi}"
            elif url:
                ref += f" {url}"

        elif source_type in ['report', 'website']:
            url = citation.url or ""
            doi = citation.doi or ""
            publisher = citation.publisher or ""

            ref = f"{author_str} ({year}). *{title}*"
            if publisher:
                ref += f". {publisher}"
            ref += "."
            # Prefer DOI over URL
            if doi:
                ref += f" https://doi.org/{doi}"
            elif url:
                ref += f" {url}"

        elif source_type == 'conference':
            publisher = citation.publisher or ""
            pages = citation.pages or ""
            doi = citation.doi or ""
            url = citation.url or ""

            ref = f"{author_str} ({year}). {title}."
            if publisher:  # Only add publisher if it exists
                ref += f" {publisher}."
            if pages:  # Only add pages if it exists
                ref += f" (pp. {pages})."
            # Add DOI/URL for conference papers
            if doi:
                ref += f" https://doi.org/{doi}"
            elif url:
                ref += f" {url}"

        else:
            # Fallback - still add DOI/URL if available
            doi = citation.doi or ""
            url = citation.url or ""

            ref = f"{author_str} ({year}). {title}."
            if doi:
                ref += f" https://doi.org/{doi}"
            elif url:
                ref += f" {url}"

        return ref

    def _format_ieee_reference(self, citation: Citation) -> str:
        """Format full reference in IEEE style."""
        authors = citation.authors
        year = citation.year
        title = citation.title

        # Format authors (initials first in IEEE)
        if len(authors) <= 3:
            author_str = ", ".join([f"{a}." for a in authors])
        else:
            author_str = f"{authors[0]}. et al."

        # Format based on source type
        source_type = citation.source_type

        if source_type == 'journal':
            journal = citation.journal or ""
            volume = citation.volume or ""
            pages = citation.pages or ""

            ref = f"[{citation.id.replace('cite_', '')}] {author_str}, \"{title},\" *{journal}*"
            if volume:
                ref += f", vol. {volume}"
            if pages:
                ref += f", pp. {pages}"
            ref += f", {year}."

        else:
            ref = f"[{citation.id.replace('cite_', '')}] {author_str}, \"{title},\" {year}."

        return ref

    def _format_chicago_reference(self, citation: Citation) -> str:
        """Format full reference in Chicago Author-Date style."""
        authors = citation.authors
        year = citation.year
        title = citation.title

        # Chicago format: Last, First, and First Last.
        if len(authors) == 1:
            author_str = f"{authors[0]}."
        elif len(authors) == 2:
            author_str = f"{authors[0]} and {authors[1]}."
        elif len(authors) <= 7:
            author_str = ", ".join(authors[:-1]) + f", and {authors[-1]}."
        else:
            author_str = ", ".join(authors[:7]) + ", et al."

        source_type = citation.source_type

        if source_type == 'journal':
            journal = citation.journal or ""
            volume = citation.volume
            issue = citation.issue
            pages = citation.pages or ""
            doi = citation.doi or ""
            url = citation.url or ""

            # Chicago journal: Author. Year. "Title." Journal Volume, no. Issue: Pages. DOI/URL.
            ref = f"{author_str} {year}. \"{title}.\" *{journal}*"
            if volume:
                ref += f" {volume}"
            if issue:
                ref += f", no. {issue}"
            if pages:
                ref += f": {pages}"
            ref += "."
            if doi:
                ref += f" https://doi.org/{doi}."
            elif url:
                ref += f" {url}."

        elif source_type == 'book':
            publisher = citation.publisher or ""
            doi = citation.doi or ""
            url = citation.url or ""

            ref = f"{author_str} {year}. *{title}*."
            if publisher:
                ref += f" {publisher}."
            if doi:
                ref += f" https://doi.org/{doi}."
            elif url:
                ref += f" {url}."

        elif source_type == 'conference':
            publisher = citation.publisher or ""
            pages = citation.pages or ""

            ref = f"{author_str} {year}. \"{title}.\""
            if publisher:
                ref += f" In {publisher}."
            if pages:
                ref += f" {pages}."

        else:
            doi = citation.doi or ""
            url = citation.url or ""
            ref = f"{author_str} {year}. \"{title}.\""
            if doi:
                ref += f" https://doi.org/{doi}."
            elif url:
                ref += f" {url}."

        return ref

    def _format_mla_reference(self, citation: Citation) -> str:
        """Format full reference in MLA 9th Edition style."""
        authors = citation.authors
        year = citation.year
        title = citation.title

        # MLA format: Last, First, et al.
        if len(authors) == 1:
            author_str = f"{authors[0]}."
        elif len(authors) == 2:
            author_str = f"{authors[0]} and {authors[1]}."
        else:
            author_str = f"{authors[0]}, et al."

        source_type = citation.source_type

        if source_type == 'journal':
            journal = citation.journal or ""
            volume = citation.volume
            issue = citation.issue
            pages = citation.pages or ""
            doi = citation.doi or ""
            url = citation.url or ""

            # MLA journal: Author. "Title." Journal, vol. V, no. I, Year, pp. Pages. DOI/URL.
            ref = f"{author_str} \"{title}.\" *{journal}*"
            if volume:
                ref += f", vol. {volume}"
            if issue:
                ref += f", no. {issue}"
            ref += f", {year}"
            if pages:
                ref += f", pp. {pages}"
            ref += "."
            if doi:
                ref += f" https://doi.org/{doi}."
            elif url:
                ref += f" {url}."

        elif source_type == 'book':
            publisher = citation.publisher or ""
            doi = citation.doi or ""
            url = citation.url or ""

            ref = f"{author_str} *{title}*."
            if publisher:
                ref += f" {publisher}, {year}."
            else:
                ref += f" {year}."
            if doi:
                ref += f" https://doi.org/{doi}."
            elif url:
                ref += f" {url}."

        elif source_type in ['report', 'website']:
            url = citation.url or ""
            publisher = citation.publisher or ""

            ref = f"{author_str} \"{title}.\""
            if publisher:
                ref += f" {publisher},"
            ref += f" {year}."
            if url:
                ref += f" {url}."

        else:
            doi = citation.doi or ""
            url = citation.url or ""
            ref = f"{author_str} \"{title}.\" {year}."
            if doi:
                ref += f" https://doi.org/{doi}."
            elif url:
                ref += f" {url}."

        return ref

    def validate_compilation(self, original: str, compiled: str) -> Dict[str, Any]:
        """
        Validate that compilation completed successfully.

        Args:
            original: Original text with citation IDs
            compiled: Compiled text with formatted citations

        Returns:
            dict: Validation results with success status and issues
        """
        issues = []

        # Check for remaining citation IDs (should be none)
        remaining_ids = re.findall(r'\{cite_\d{3}\}', compiled)
        if remaining_ids:
            issues.append(f"Found {len(remaining_ids)} un-replaced citation IDs: {remaining_ids[:5]}")

        # Check for MISSING markers
        missing_markers = re.findall(r'\[MISSING: cite_\d{3}\]', compiled)
        if missing_markers:
            issues.append(f"Found {len(missing_markers)} missing citations: {missing_markers}")

        # Extract citation IDs from original
        original_ids = set(re.findall(r'cite_\d{3}', original))

        # Check all IDs were processed
        unprocessed = original_ids - {m.replace('[MISSING: ', '').replace(']', '') for m in missing_markers}

        return {
            'success': len(issues) == 0,
            'issues': issues,
            'total_citations': len(original_ids),
            'successfully_compiled': len(original_ids) - len(missing_markers),
            'missing_citations': len(missing_markers),
        }

    def generate_coverage_report(self, draft: str) -> Dict[str, Any]:
        """
        Analyze citation coverage in draft.

        Args:
            draft: Text with citation IDs

        Returns:
            dict with coverage statistics and unused citations
        """
        # Find all citation IDs used in draft
        cited_ids = self._extract_cited_ids(draft)

        # Get all available citations
        all_citation_ids = set(self.citation_lookup.keys())

        # Calculate unused
        unused_ids = all_citation_ids - cited_ids
        unused_citations = [
            self.citation_lookup[cid]
            for cid in sorted(unused_ids)
        ]

        # Calculate statistics
        total = len(all_citation_ids)
        used = len(cited_ids)
        coverage = (used / total * 100) if total > 0 else 0

        return {
            'total_citations_available': total,
            'citations_used': used,
            'citations_unused': len(unused_ids),
            'coverage_percentage': coverage,
            'unused_citations': unused_citations,
            'cited_ids': cited_ids,
        }

    def analyze_section_complexity(self, section_text: str) -> Dict[str, Any]:
        """
        Analyze complexity of a draft section to determine research depth needs.

        Used for hybrid deep research approach: complex sections get deep research,
        routine sections get standard citation research.

        Complexity Factors:
        1. Technical term density (specialized vocabulary)
        2. Citation density (research-heavy sections)
        3. Section length (longer = more complex)
        4. Academic keywords (theory, methodology, analysis, etc.)

        Args:
            section_text: Text of the section to analyze

        Returns:
            Dict with keys:
                - complexity_score: float (0-1 scale, higher = more complex)
                - is_complex: bool (score >= threshold)
                - factors: Dict[str, float] - Individual factor scores
                - recommendation: str - "deep_research" or "standard_research"
        """
        # Extract metrics
        words = section_text.split()
        word_count = len(words)
        sentences = section_text.split('.')
        sentence_count = max(1, len([s for s in sentences if s.strip()]))

        # Factor 1: Technical term density (presence of academic/technical terms)
        technical_terms = [
            'methodology', 'framework', 'paradigm', 'theoretical', 'empirical',
            'analysis', 'syndraft', 'hypodraft', 'validation', 'verification',
            'algorithm', 'optimization', 'implementation', 'architecture',
            'governance', 'compliance', 'regulation', 'standard', 'protocol',
            'infrastructure', 'integration', 'scalability', 'performance',
            'systematic', 'comprehensive', 'interdisciplinary', 'multifaceted'
        ]
        technical_count = sum(1 for word in words if word.lower() in technical_terms)
        technical_density = min(technical_count / max(1, word_count / 100), 1.0)  # Per 100 words, capped at 1.0

        # Factor 2: Citation density (how research-heavy is this section?)
        citation_pattern_count = section_text.count('{cite_')
        citation_density = min(citation_pattern_count / max(1, sentence_count / 10), 1.0)  # Per 10 sentences

        # Factor 3: Section length (longer sections = more complex topics)
        # Normalize: 500 words = 0.5, 1000+ words = 1.0
        length_factor = min(word_count / 1000, 1.0)

        # Factor 4: Academic keywords (research-oriented language)
        academic_keywords = [
            'research', 'study', 'literature', 'review', 'survey', 'investigation',
            'evidence', 'findings', 'results', 'discussion', 'implications',
            'limitations', 'future work', 'contributions', 'novelty',
            'state-of-the-art', 'cutting-edge', 'emerging', 'recent developments'
        ]
        keyword_count = sum(1 for keyword in academic_keywords if keyword.lower() in section_text.lower())
        keyword_density = min(keyword_count / 5, 1.0)  # 5+ keywords = 1.0

        # Calculate weighted complexity score
        complexity_score = (
            technical_density * 0.3 +      # 30% weight
            citation_density * 0.3 +       # 30% weight
            length_factor * 0.2 +          # 20% weight
            keyword_density * 0.2          # 20% weight
        )

        is_complex = complexity_score >= self.complexity_threshold

        return {
            'complexity_score': round(complexity_score, 3),
            'is_complex': is_complex,
            'factors': {
                'technical_density': round(technical_density, 3),
                'citation_density': round(citation_density, 3),
                'length_factor': round(length_factor, 3),
                'keyword_density': round(keyword_density, 3)
            },
            'recommendation': 'deep_research' if is_complex else 'standard_research',
            'metrics': {
                'word_count': word_count,
                'sentence_count': sentence_count,
                'citation_count': citation_pattern_count,
                'technical_terms': technical_count,
                'academic_keywords': keyword_count
            }
        }


def format_coverage_report(report: Dict[str, Any]) -> str:
    """
    Format coverage report as markdown.

    Args:
        report: Coverage report from generate_coverage_report()

    Returns:
        str: Formatted markdown report
    """
    output = f"""# Citation Coverage Report

## Summary Statistics

- **Total citations available**: {report['total_citations_available']}
- **Citations used in draft**: {report['citations_used']}
- **Citations unused**: {report['citations_unused']}
- **Coverage percentage**: {report['coverage_percentage']:.1f}%

## Analysis

"""

    # Add analysis based on coverage percentage
    if report['coverage_percentage'] < 50:
        output += "⚠️  **Low citation coverage** - Consider using more sources from the database.\n\n"
    elif report['coverage_percentage'] > 90:
        output += "✅ **Excellent citation coverage** - Most available sources are utilized.\n\n"
    else:
        output += "✅ **Good citation coverage** - Reasonable use of available sources.\n\n"

    # List unused citations
    if report['unused_citations']:
        output += "## Unused Citations\n\n"
        output += "The following citations are in the database but not used in the draft:\n\n"

        for citation in report['unused_citations']:
            authors_str = ", ".join(citation.authors[:2])
            if len(citation.authors) > 2:
                authors_str += " et al."

            # Truncate title if too long
            title = citation.title
            if len(title) > 80:
                title = title[:77] + "..."

            output += f"- **{citation.id}**: {authors_str} ({citation.year}) - {title}\n"

    else:
        output += "## All Citations Used\n\n"
        output += "✅ All citations in the database have been used in the draft.\n"

    return output


def compile_citations_in_file(
    input_path: Path,
    output_path: Path,
    database: CitationDatabase,
    model: Optional[Any] = None,
    research_missing: bool = True
) -> Tuple[bool, List[str], List[str]]:
    """
    Compile citations in file using database, optionally researching missing citations.

    Args:
        input_path: Input file with citation IDs and/or {cite_MISSING:topic} placeholders
        output_path: Output file for compiled text
        database: Citation database
        model: Optional Gemini model for researching missing citations
        research_missing: Whether to research {cite_MISSING:topic} placeholders

    Returns:
        tuple: (success, list_of_missing_ids, list_of_researched_topics)
    """
    # Read input
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Compile citations
    compiler = CitationCompiler(database, model=model)
    compiled_text, missing_ids, researched_topics = compiler.compile_citations(
        text,
        research_missing=research_missing
    )

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(compiled_text)

    return len(missing_ids) == 0, missing_ids, researched_topics
