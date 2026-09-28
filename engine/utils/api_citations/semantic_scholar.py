#!/usr/bin/env python3
"""
ABOUTME: Semantic Scholar API client for AI-powered academic paper search
ABOUTME: Secondary citation source with 200M+ papers and better keyword search
"""

import logging
from typing import Optional, Dict, Any, List
from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class SemanticScholarClient(BaseAPIClient):
    """
    Semantic Scholar API client for academic paper search.

    Semantic Scholar is an AI-powered academic search engine from the Allen Institute.
    Provides excellent keyword search and citation analysis for 200M+ papers.

    API Documentation: https://api.semanticscholar.org/api-docs/
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_per_second: float = 5.0,
        timeout: int = 15,
        max_retries: int = 5,
    ):
        """
        Initialize Semantic Scholar API client.

        Args:
            api_key: Optional S2 API key for higher rate limits (get free key at https://www.semanticscholar.org/product/api)
            rate_limit_per_second: Maximum requests per second (S2 allows 100 with key, 1/sec without)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts (increased for rate limit resilience)
        """
        import os

        # Use provided key or fall back to environment variable
        self.s2_api_key = api_key or os.getenv('SEMANTIC_SCHOLAR_API_KEY')

        # With API key: higher rate limit (100/sec allowed, we use 10 to be safe)
        # Without API key: lower rate limit (1/sec enforced by S2)
        if self.s2_api_key:
            rate_limit_per_second = min(rate_limit_per_second, 10.0)
            logger.info("Semantic Scholar: Using API key for higher rate limits")
        else:
            # Without key, S2 enforces 1 req/sec - use 0.5 to be safe
            rate_limit_per_second = 0.5
            logger.debug("Semantic Scholar: No API key, using conservative rate limit (0.5 req/sec)")

        super().__init__(
            base_url="https://api.semanticscholar.org",
            api_key=self.s2_api_key,
            rate_limit_per_second=rate_limit_per_second,
            timeout=timeout,
            max_retries=max_retries,
            api_type="semantic_scholar",
        )

    def search_paper(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a paper by title, author, or keywords.

        Args:
            query: Search query (title, authors, keywords)

        Returns:
            Paper metadata dict with standardized fields or None if not found

        Example return:
            {
                "title": "Paper Title",
                "authors": ["Smith", "Jones"],
                "year": 2023,
                "doi": "10.xxxx/xxxxx",
                "url": "https://www.semanticscholar.org/paper/...",
                "journal": "Nature",
                "publisher": "",
                "volume": "",
                "issue": "",
                "pages": "",
                "source_type": "journal",
                "confidence": 0.85
            }
        """
        # Search Semantic Scholar API
        response = self._make_request(
            method="GET",
            endpoint="/graph/v1/paper/search",
            params={
                "query": query,
                "limit": 5,  # Get top 5 results
                "fields": "title,authors,year,venue,externalIds,url,citationCount,publicationTypes,abstract",
            },
        )

        if not response:
            logger.debug(f"SemanticScholar: No results for query '{query[:50]}...'")
            return None

        # Extract first result (most relevant)
        try:
            papers = response.get("data", [])
            if not papers:
                logger.debug(f"SemanticScholar: Empty results for '{query[:50]}...'")
                return None

            paper = papers[0]

            # Extract metadata
            metadata = self._extract_metadata(paper)

            if metadata:
                logger.info(
                    f"SemanticScholar: Found '{metadata['title'][:50]}...' by {metadata['authors'][0]} ({metadata['year']})"
                )
                return metadata
            else:
                logger.debug(f"SemanticScholar: Incomplete metadata for '{query[:50]}...'")
                return None

        except Exception as e:
            logger.error(f"SemanticScholar: Error parsing response: {e}")
            return None

    def get_paper_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Look up a single paper by its DOI.

        Used by MultiSourceConfirmer to independently confirm that a work found
        by one database also exists in Semantic Scholar. A DOI lookup is an
        identity lookup, not a relevance search, so a hit means "S2 holds a
        record for this exact DOI" and nothing more.

        Args:
            doi: Bare DOI string (e.g. "10.1038/nature12373"), no URL prefix

        Returns:
            Normalized metadata dict, or None if S2 has no record for it
        """
        if not doi:
            return None

        # S2 accepts the "DOI:<doi>" identifier form on the single-paper route.
        response = self._make_request(
            method="GET",
            endpoint=f"/graph/v1/paper/DOI:{doi}",
            params={
                "fields": "title,authors,year,venue,externalIds,url,citationCount,publicationTypes,abstract",
            },
        )

        if not response:
            logger.debug(f"SemanticScholar: No record for DOI '{doi}'")
            return None

        try:
            # The single-paper route returns the paper object directly (no
            # "data" envelope), with the same field shape as a search hit.
            if not isinstance(response, dict) or not response.get("title"):
                logger.debug(f"SemanticScholar: Unexpected DOI response shape for '{doi}'")
                return None
            return self._extract_metadata(response)
        except Exception as e:
            logger.error(f"SemanticScholar: Error parsing DOI response for '{doi}': {e}")
            return None

    def _extract_metadata(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract and normalize paper metadata from Semantic Scholar response.

        Args:
            paper: Semantic Scholar paper object

        Returns:
            Normalized metadata dict or None if required fields missing
        """
        try:
            # Title (required)
            title = paper.get("title", "")
            if not title:
                return None

            # Authors (required)
            authors_raw = paper.get("authors", [])
            authors = []
            for author in authors_raw:
                if isinstance(author, dict):
                    name = author.get("name", "")
                    if name:
                        # Extract last name (Semantic Scholar gives full names)
                        # "John Smith" -> "Smith"
                        name_parts = name.split()
                        last_name = name_parts[-1] if name_parts else name
                        authors.append(last_name)

            if not authors:
                logger.debug(f"No authors found for '{title[:50]}...'")
                return None

            # Year (required)
            year = paper.get("year", 0)
            if year == 0:
                logger.debug(f"No publication year for '{title[:50]}...'")
                return None

            # External IDs (DOI, arXiv, etc.)
            external_ids = paper.get("externalIds", {})
            doi = external_ids.get("DOI", "")
            arxiv_id = external_ids.get("ArXiv", "")

            # URL (use DOI if available, else Semantic Scholar URL, else arXiv)
            url = ""
            if doi:
                url = f"https://doi.org/{doi}"
            elif paper.get("url"):
                url = paper.get("url", "")
            elif arxiv_id:
                url = f"https://arxiv.org/abs/{arxiv_id}"

            # Venue (journal/conference)
            journal = paper.get("venue", "")

            # Publisher (not provided by S2)
            publisher = ""

            # Volume, Issue, Pages (not provided by S2)
            volume = ""
            issue = ""
            pages = ""

            # Abstract (optional)
            abstract = paper.get("abstract", "")
            if abstract:
                abstract = abstract.strip()

            # Source type
            publication_types = paper.get("publicationTypes", [])
            source_type = self._map_source_type(publication_types, journal)

            # Calculate confidence score
            citation_count = paper.get("citationCount", 0)
            confidence = self._calculate_confidence(
                has_doi=bool(doi),
                has_url=bool(url),
                has_venue=bool(journal),
                author_count=len(authors),
                citation_count=citation_count,
            )

            return {
                "title": title,
                "authors": authors,
                "year": year,
                "doi": doi,
                "url": url,
                "journal": journal,
                "publisher": publisher,
                "volume": volume,
                "issue": issue,
                "pages": pages,
                "source_type": source_type,
                "confidence": confidence,
                "abstract": abstract if abstract else None,
                "citation_count": citation_count,
            }

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return None

    def _map_source_type(self, publication_types: List[str], venue: str) -> str:
        """
        Map Semantic Scholar publication types to our source_type enum.

        Args:
            publication_types: List of S2 publication types
            venue: Venue name

        Returns:
            source_type: One of: journal, conference, book, report, website
        """
        if not publication_types:
            # Guess from venue name
            if venue:
                venue_lower = venue.lower()
                if any(keyword in venue_lower for keyword in ["conference", "proceedings", "workshop", "symposium"]):
                    return "conference"
            return "journal"  # Default

        # Check publication types
        types_str = " ".join(publication_types).lower()

        if "journal" in types_str:
            return "journal"
        elif any(keyword in types_str for keyword in ["conference", "proceedings"]):
            return "conference"
        elif "book" in types_str:
            return "book"
        elif any(keyword in types_str for keyword in ["review", "editorial"]):
            return "journal"
        else:
            return "journal"  # Default

    def _calculate_confidence(
        self, has_doi: bool, has_url: bool, has_venue: bool, author_count: int, citation_count: int
    ) -> float:
        """
        Calculate confidence score for paper metadata.

        Args:
            has_doi: Whether DOI is present
            has_url: Whether URL is present
            has_venue: Whether venue name is present
            author_count: Number of authors
            citation_count: Number of citations

        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.4  # Base score (lower than Crossref since less metadata)

        if has_doi:
            score += 0.3  # DOI is strong signal
        elif has_url:
            score += 0.1  # At least we have a URL

        if has_venue:
            score += 0.1
        if author_count > 0:
            score += 0.05

        # Citation count as quality signal
        if citation_count > 100:
            score += 0.1
        elif citation_count > 10:
            score += 0.05

        return min(score, 1.0)  # Cap at 1.0
