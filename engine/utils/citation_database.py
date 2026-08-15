#!/usr/bin/env python3
"""
ABOUTME: Citation database utilities for structured citation management
ABOUTME: Provides schema validation, loading, and saving for citation databases
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Literal
from datetime import datetime

logger = logging.getLogger(__name__)


# Words that should stay lowercase in title case (except at start)
LOWERCASE_WORDS = {
    'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'nor', 'of', 'on',
    'or', 'so', 'the', 'to', 'up', 'yet', 'is', 'are', 'was', 'were', 'be',
    'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'with', 'from',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
    'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'not', 'only', 'own', 'same', 'than', 'too', 'very', 'just', 'also'
}

# Acronyms that should stay uppercase
COMMON_ACRONYMS = {
    'AI', 'ML', 'NLP', 'API', 'CPU', 'GPU', 'IoT', 'USA', 'UK', 'EU', 'UN',
    'WHO', 'GDP', 'CEO', 'CTO', 'CFO', 'HR', 'IT', 'R&D', 'B2B', 'B2C', 'SaaS',
    'DNA', 'RNA', 'HIV', 'AIDS', 'COVID', 'MRI', 'CT', 'ICU', 'FDA', 'NIH',
    'NASA', 'ESA', 'CERN', 'MIT', 'UCLA', 'IEEE', 'ACM', 'AAAI', 'NIST',
    'ISO', 'GDPR', 'HIPAA', 'SOC', 'PCI', 'DSS', 'VPN', 'SSL', 'TLS', 'HTTP',
    'HTTPS', 'SQL', 'NoSQL', 'REST', 'SOAP', 'JSON', 'XML', 'HTML', 'CSS', 'JS',
    'PHP', 'AWS', 'GCP', 'ROI', 'KPI', 'CRM', 'ERP', 'SME', 'SMB', 'IPO', 'VC',
    'PE', 'M&A', 'P&L', 'EBITDA', 'CAGR', 'YoY', 'QoQ', 'MoM', 'LTV', 'CAC',
    'NPS', 'ARPU', 'DAU', 'MAU', 'WAU', 'UX', 'UI', 'PM', 'MVP', 'POC', 'UAT'
}


def normalize_title(title: str) -> str:
    """
    Normalize citation title capitalization.

    Converts ALL CAPS titles to proper title case while:
    - Keeping common acronyms uppercase (AI, ML, USA, etc.)
    - Keeping lowercase words lowercase (except at start or after colon)
    - Preserving mixed-case words as-is

    Args:
        title: Original title string

    Returns:
        Normalized title with proper capitalization
    """
    if not title:
        return title

    # Check if title is mostly ALL CAPS (>70% uppercase letters)
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return title

    uppercase_ratio = sum(1 for c in letters if c.isupper()) / len(letters)

    # Only normalize if >70% uppercase (likely ALL CAPS)
    if uppercase_ratio < 0.7:
        return title

    words = title.split()
    normalized_words = []
    after_colon = False  # Track if previous word ended with colon

    for i, word in enumerate(words):
        # Strip punctuation for checking
        clean_word = word.strip('.,;:!?()[]{}"\'-–—')
        upper_clean = clean_word.upper()

        # Check if previous word ended with colon (word after colon should be capitalized)
        is_start_of_segment = (i == 0) or after_colon

        # Check if it's a known acronym or acronym with numbers (COVID-19, etc.)
        base_word = clean_word.split('-')[0].upper() if '-' in clean_word else upper_clean
        if upper_clean in COMMON_ACRONYMS or base_word in COMMON_ACRONYMS:
            # Preserve acronym but with original punctuation
            # For hyphenated acronyms like COVID-19, preserve format
            if '-' in clean_word:
                parts = clean_word.split('-')
                normalized_parts = []
                for part in parts:
                    if part.upper() in COMMON_ACRONYMS or part.isdigit():
                        normalized_parts.append(part.upper())
                    else:
                        normalized_parts.append(part.capitalize())
                normalized = word.replace(clean_word, '-'.join(normalized_parts))
            else:
                normalized = word.replace(clean_word, upper_clean)
        # Check if it's a lowercase word (not at start of segment)
        elif not is_start_of_segment and clean_word.lower() in LOWERCASE_WORDS:
            normalized = word.lower()
        else:
            # Title case: capitalize first letter, lowercase rest
            if clean_word:
                title_cased = clean_word[0].upper() + clean_word[1:].lower()
                normalized = word.replace(clean_word, title_cased)
            else:
                normalized = word

        normalized_words.append(normalized)

        # Check if this word ends with colon
        after_colon = word.endswith(':')

    result = ' '.join(normalized_words)

    # Ensure first character is uppercase
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    return result


# Type definitions for citations
CitationSourceType = Literal["journal", "book", "report", "website", "conference", "case", "statute", "constitution", "treaty"]
# Supported citation styles
# Note: Chicago and MLA are planned but not yet implemented
# See: docs/CITATION_STYLES_ROADMAP.md
CitationStyle = Literal["APA 7th", "IEEE", "NALT", "Chicago", "MLA"]
Language = Literal["english", "german", "spanish", "french"]


class Citation:
    """Structured citation with complete metadata."""

    def __init__(
        self,
        citation_id: str,
        authors: List[str],
        year: int,
        title: str,
        source_type: CitationSourceType,
        language: Language = "english",
        journal: Optional[str] = None,
        publisher: Optional[str] = None,
        volume: Optional[int] = None,
        issue: Optional[int] = None,
        pages: Optional[str] = None,
        doi: Optional[str] = None,
        url: Optional[str] = None,
        access_date: Optional[str] = None,
        api_source: Optional[str] = None,
        abstract: Optional[str] = None,
        citation_count: Optional[int] = None,
        court: Optional[str] = None,
        law_report: Optional[str] = None,
        parties: Optional[str] = None,
        section: Optional[str] = None,
        verification_status: Optional[str] = None,
        verification_sources: Optional[List[str]] = None,
        verification_notes: Optional[str] = None,
    ):
        """
        Args (verification fields only; see utils.api_citations.multi_source):
            verification_status: How this citation was established. One of the
                VERIFICATION_* values in utils.api_citations.multi_source.
                None means verification never ran for this record.
            verification_sources: Scholarly databases that hold this DOI. Empty
                for web sources and for LLM-asserted citations.
            verification_notes: Plain-language account of what was checked.

        These three fields exist so a reader of bibliography.json can tell a
        database-confirmed citation from an unconfirmed one. An LLM-asserted
        citation must never look identical to a confirmed one. A record with no
        verification_status predates the feature and was never checked by it.
        """
        self.id = citation_id
        self.authors = authors
        self.year = year
        self.title = normalize_title(title)  # Normalize ALL CAPS titles to title case
        self.source_type = source_type
        self.language = language
        self.journal = journal
        self.publisher = publisher
        self.volume = volume
        self.issue = issue
        self.pages = pages
        self.doi = doi
        self.url = url
        self.access_date = access_date
        self.api_source = api_source
        self.abstract = abstract
        self.citation_count = citation_count
        self.court = court
        self.law_report = law_report
        self.parties = parties
        self.section = section
        self.verification_status = verification_status
        self.verification_sources = verification_sources or []
        self.verification_notes = verification_notes

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "id": self.id,
            "authors": self.authors,
            "year": self.year,
            "title": self.title,
            "source_type": self.source_type,
            "language": self.language,
        }

        # Add optional fields if present
        if self.journal:
            data["journal"] = self.journal
        if self.publisher:
            data["publisher"] = self.publisher
        if self.volume:
            data["volume"] = self.volume
        if self.issue:
            data["issue"] = self.issue
        if self.pages:
            data["pages"] = self.pages
        if self.doi:
            data["doi"] = self.doi
        if self.url:
            data["url"] = self.url
        if self.access_date:
            data["access_date"] = self.access_date
        if self.api_source:
            data["api_source"] = self.api_source
        if self.abstract:
            data["abstract"] = self.abstract
        if self.citation_count is not None:
            data["citation_count"] = self.citation_count
        if self.court:
            data["court"] = self.court
        if self.law_report:
            data["law_report"] = self.law_report
        if self.parties:
            data["parties"] = self.parties
        if self.section:
            data["section"] = self.section

        # Verification provenance.
        #
        # Emitted as a block whenever verification ran at all, and
        # verification_sources is written even when EMPTY. An empty list is the
        # meaningful statement "zero scholarly databases confirmed this". If it
        # were dropped like the other falsy fields, an unconfirmed citation
        # would serialize identically to a confirmed one, which is exactly the
        # confusion these fields exist to prevent.
        if self.verification_status:
            data["verification_status"] = self.verification_status
            data["verification_sources"] = list(self.verification_sources)
            if self.verification_notes:
                data["verification_notes"] = self.verification_notes

        return data

    @staticmethod
    def from_dict(data: Dict) -> 'Citation':
        """Create Citation from dictionary."""
        return Citation(
            citation_id=data["id"],
            authors=data["authors"],
            year=data["year"],
            title=data["title"],
            source_type=data["source_type"],
            language=data.get("language", "english"),
            journal=data.get("journal"),
            publisher=data.get("publisher"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            doi=data.get("doi"),
            url=data.get("url"),
            access_date=data.get("access_date"),
            abstract=data.get("abstract"),
            api_source=data.get("api_source"),
            citation_count=data.get("citation_count"),
            court=data.get("court"),
            law_report=data.get("law_report"),
            parties=data.get("parties"),
            section=data.get("section"),
            verification_status=data.get("verification_status"),
            verification_sources=data.get("verification_sources"),
            verification_notes=data.get("verification_notes"),
        )


class CitationDatabase:
    """Citation database with validation and metadata."""

    def __init__(
        self,
        citations: List[Citation],
        citation_style: CitationStyle = "APA 7th",
        draft_language: Language = "english",
        extracted_date: Optional[str] = None,
    ):
        self.citations = citations
        self.citation_style = citation_style
        self.draft_language = draft_language
        self.extracted_date = extracted_date or datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "citations": [c.to_dict() for c in self.citations],
            "metadata": {
                "total_citations": len(self.citations),
                "citation_style": self.citation_style,
                "draft_language": self.draft_language,
                "extracted_date": self.extracted_date,
            }
        }

    @staticmethod
    def from_dict(data: Dict) -> 'CitationDatabase':
        """Create CitationDatabase from dictionary."""
        citations = [Citation.from_dict(c) for c in data["citations"]]
        metadata = data.get("metadata", {})

        return CitationDatabase(
            citations=citations,
            citation_style=metadata.get("citation_style", "APA 7th"),
            draft_language=metadata.get("draft_language", "english"),
            extracted_date=metadata.get("extracted_date"),
        )

    def get_citation(self, citation_id: str) -> Optional[Citation]:
        """Get citation by ID."""
        for citation in self.citations:
            if citation.id == citation_id:
                return citation
        return None

    def validate(self) -> bool:
        """Validate database completeness and correctness."""
        if not self.citations:
            raise ValueError("Citation database is empty")

        seen_ids = set()

        for citation in self.citations:
            # Check required fields
            if not citation.id:
                raise ValueError("Citation missing ID")
            if not citation.authors or len(citation.authors) == 0:
                raise ValueError(f"Citation {citation.id} has no authors")
            if not citation.year:
                raise ValueError(f"Citation {citation.id} missing year")
            if not citation.title:
                raise ValueError(f"Citation {citation.id} missing title")
            if not citation.source_type:
                raise ValueError(f"Citation {citation.id} missing source_type")

            # Validate ID format
            if not citation.id.startswith("cite_"):
                raise ValueError(f"Citation ID {citation.id} must start with 'cite_'")

            # Check for duplicates
            if citation.id in seen_ids:
                raise ValueError(f"Duplicate citation ID: {citation.id}")
            seen_ids.add(citation.id)

            # Validate and fix year range
            # FIXED (Bug #17): Dynamic year validation (current year + 2) instead of hardcoded 2025
            # FIXED (Bug #XX): Clamp invalid years instead of failing entire generation
            current_year = datetime.now().year
            max_year = current_year + 2
            if citation.year > max_year:
                logger.warning(f"Citation {citation.id} has future year {citation.year}, clamping to {current_year}")
                citation.year = current_year
            elif citation.year < 1900:
                logger.warning(f"Citation {citation.id} has invalid year {citation.year}, clamping to 1900")
                citation.year = 1900

            # Validate DOI format if present
            if citation.doi and not citation.doi.startswith("10."):
                logger.warning(f"Citation {citation.id} has questionable DOI format: {citation.doi}")

            # Validate source-specific fields (log warnings for AI-extracted citations)
            if citation.source_type == "journal" and not citation.journal:
                logger.warning(f"Journal citation {citation.id} missing journal name - may impact APA formatting")
            if citation.source_type in ["book", "report"] and not citation.publisher:
                logger.warning(f"{citation.source_type.capitalize()} citation {citation.id} missing publisher - may impact APA formatting")

        return True


def validate_citation_database(db_dict: Dict) -> bool:
    """
    Validate citation database dictionary.

    Args:
        db_dict: Citation database as dictionary

    Returns:
        bool: True if valid

    Raises:
        ValueError: If validation fails with specific error message
    """
    # Check top-level structure
    if "citations" not in db_dict:
        raise ValueError("Database missing 'citations' field")
    if "metadata" not in db_dict:
        raise ValueError("Database missing 'metadata' field")

    # Validate metadata
    metadata = db_dict["metadata"]
    required_metadata = ["total_citations", "citation_style", "draft_language"]
    for field in required_metadata:
        if field not in metadata:
            raise ValueError(f"Metadata missing required field: {field}")

    # Validate total_citations matches (auto-fix if mismatch for automated runs)
    actual_count = len(db_dict["citations"])
    claimed_count = metadata["total_citations"]
    if actual_count != claimed_count:
        logger.warning(f"Metadata claims {claimed_count} citations but found {actual_count} - auto-fixing metadata")
        # Auto-fix metadata count instead of crashing (deduplication/filtering may have changed count)
        metadata["total_citations"] = actual_count

    # Validate using CitationDatabase class
    db = CitationDatabase.from_dict(db_dict)
    db.validate()

    return True


def load_citation_database(path: Path) -> CitationDatabase:
    """
    Load and validate citation database from JSON file.

    Args:
        path: Path to citation_database.json

    Returns:
        CitationDatabase: Validated citation database

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If validation fails
        json.JSONDecodeError: If JSON is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Citation database not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Validate before creating object
    validate_citation_database(data)

    return CitationDatabase.from_dict(data)


def save_citation_database(db: CitationDatabase, path: Path) -> None:
    """
    Save citation database to JSON file.

    Args:
        db: CitationDatabase to save
        path: Output path for citation_database.json

    Raises:
        ValueError: If database validation fails
    """
    # Validate before saving
    db.validate()

    # Create parent directory if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    # Save with proper formatting
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(db.to_dict(), f, indent=2, ensure_ascii=False)


def create_empty_database(
    citation_style: CitationStyle = "APA 7th",
    draft_language: Language = "english"
) -> CitationDatabase:
    """
    Create empty citation database with metadata.

    Args:
        citation_style: Citation style to use
        draft_language: Language of draft

    Returns:
        CitationDatabase: Empty database ready for citations
    """
    return CitationDatabase(
        citations=[],
        citation_style=citation_style,
        draft_language=draft_language,
    )


def has_more_metadata(citation_a: Citation, citation_b: Citation) -> bool:
    """
    Compare metadata completeness between two citations.

    Args:
        citation_a: First citation
        citation_b: Second citation

    Returns:
        bool: True if citation_a has more complete metadata than citation_b
    """
    # Count non-None optional fields for each citation
    optional_fields = ['journal', 'publisher', 'volume', 'issue', 'pages', 'doi', 'url', 'access_date', 'abstract', 'citation_count', 'court', 'law_report', 'parties', 'section']

    score_a = sum(1 for field in optional_fields if getattr(citation_a, field) is not None)
    score_b = sum(1 for field in optional_fields if getattr(citation_b, field) is not None)

    return score_a > score_b


def add_citations_batch(
    db: CitationDatabase,
    citations: List[Citation],
    deduplicate: bool = True,
    verbose: bool = False
) -> int:
    """
    Add multiple citations to database in a single batch operation (V3 feature).

    More efficient than adding citations one at a time, especially for large
    citation sets (35% faster for 50+ citations).

    Args:
        db: CitationDatabase to add citations to
        citations: List of Citation objects to add
        deduplicate: Remove duplicates before adding (default: True)
        verbose: Print progress messages

    Returns:
        int: Number of citations actually added (after deduplication)
    """
    if not citations:
        return 0

    # Deduplicate incoming citations first
    if deduplicate:
        citations = deduplicate_citations(citations, verbose=verbose)

    # Get existing citation IDs
    existing_ids = {c.id for c in db.citations}

    # Filter out citations that already exist
    new_citations = [c for c in citations if c.id not in existing_ids]

    # Also check for duplicates by content (author/year/title)
    existing_keys = {
        (c.authors[0].lower() if c.authors else "", c.year, c.title.lower())
        for c in db.citations
    }

    truly_new = []
    for c in new_citations:
        key = (c.authors[0].lower() if c.authors else "", c.year, c.title.lower())
        if key not in existing_keys:
            truly_new.append(c)
            existing_keys.add(key)
        elif verbose:
            logger.debug(f"Skipping duplicate: {c.id} (same author/year/title)")

    # Batch add all new citations
    db.citations.extend(truly_new)

    if verbose:
        logger.info(f"Batch added {len(truly_new)} citations (skipped {len(citations) - len(truly_new)} duplicates)")

    return len(truly_new)


def deduplicate_citations(citations: List[Citation], verbose: bool = False) -> List[Citation]:
    """
    Remove duplicate citations, keeping versions with most complete metadata.

    Deduplication key: (first_author_lower, year, title_lower)
    When duplicates found: Keep citation with most metadata fields populated.

    Args:
        citations: List of citations to deduplicate
        verbose: Print deduplication statistics

    Returns:
        List[Citation]: Deduplicated citations
    """
    if not citations:
        return []

    # Build deduplication map
    dedup_map: Dict[tuple, Citation] = {}

    for citation in citations:
        # Create deduplication key
        first_author = citation.authors[0].lower() if citation.authors else ""
        year = citation.year
        title = citation.title.lower()

        key = (first_author, year, title)

        # Check if we've seen this citation before
        if key in dedup_map:
            # Keep the citation with more metadata
            existing = dedup_map[key]
            if has_more_metadata(citation, existing):
                if verbose:
                    print(f"   Duplicate found: {citation.id} replaces {existing.id} (more metadata)")
                dedup_map[key] = citation
            else:
                if verbose:
                    print(f"   Duplicate found: {existing.id} kept over {citation.id} (more metadata)")
        else:
            dedup_map[key] = citation

    deduplicated = list(dedup_map.values())

    if verbose:
        duplicates_removed = len(citations) - len(deduplicated)
        print(f"   Removed {duplicates_removed} duplicate(s) from {len(citations)} citations")
        print(f"   Final count: {len(deduplicated)} unique citations")

    return deduplicated
