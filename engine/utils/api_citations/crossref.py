#!/usr/bin/env python3
"""
ABOUTME: Crossref API client for academic paper lookup via DOI and title search
ABOUTME: Primary citation source with 50M+ papers and guaranteed metadata quality
"""

import logging
from typing import Optional, Dict, Any, List
from .base import BaseAPIClient, validate_author_name

logger = logging.getLogger(__name__)


class CrossrefClient(BaseAPIClient):
    """
    Crossref API client for academic paper search.

    Crossref is the official DOI registration agency for academic publishing.
    Provides high-quality metadata for 50M+ papers.

    API Documentation: https://api.crossref.org/swagger-ui/index.html
    """

    def __init__(
        self,
        rate_limit_per_second: float = 10.0,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        """
        Initialize Crossref API client.

        Args:
            rate_limit_per_second: Maximum requests per second (Crossref allows 50, we use 10)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        super().__init__(
            base_url="https://api.crossref.org",
            rate_limit_per_second=rate_limit_per_second,
            timeout=timeout,
            max_retries=max_retries,
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
                "url": "https://doi.org/10.xxxx/xxxxx",
                "journal": "Nature",
                "publisher": "Springer",
                "volume": "5",
                "issue": "2",
                "pages": "100-110",
                "source_type": "journal",
                "confidence": 0.95
            }
        """
        # Search Crossref Works API
        response = self._make_request(
            method="GET",
            endpoint="/works",
            params={
                "query": query,
                "rows": 5,  # Get top 5 results
                "sort": "relevance",
                "select": "DOI,title,author,published,container-title,publisher,volume,issue,page,type,abstract",
            },
        )

        if not response:
            logger.debug(f"Crossref: No results for query '{query[:50]}...'")
            return None

        # Extract first result (most relevant)
        try:
            items = response.get("message", {}).get("items", [])
            if not items:
                logger.debug(f"Crossref: Empty results for '{query[:50]}...'")
                return None

            paper = items[0]

            # Extract metadata
            metadata = self._extract_metadata(paper)

            if metadata:
                logger.info(
                    f"Crossref: Found '{metadata['title'][:50]}...' by {metadata['authors'][0]} ({metadata['year']})"
                )
                return metadata
            else:
                logger.debug(f"Crossref: Incomplete metadata for '{query[:50]}...'")
                return None

        except Exception as e:
            logger.error(f"Crossref: Error parsing response: {e}")
            return None

    def get_paper_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Look up a single work by its DOI.

        Used by MultiSourceConfirmer to independently confirm that a work found
        by one database also exists in Crossref. A DOI lookup is an identity
        lookup, not a relevance search, so a hit means "Crossref holds a record
        for this exact DOI" and nothing more.

        Args:
            doi: Bare DOI string (e.g. "10.1038/nature12373"), no URL prefix

        Returns:
            Normalized metadata dict, or None if Crossref has no record for it
        """
        if not doi:
            return None

        response = self._make_request(
            method="GET",
            endpoint=f"/works/{doi}",
        )

        if not response:
            logger.debug(f"Crossref: No record for DOI '{doi}'")
            return None

        try:
            # A single-work response wraps the item in "message"; the item has
            # the same shape as an element of the /works search "items" list.
            paper = response.get("message")
            if not isinstance(paper, dict):
                logger.debug(f"Crossref: Unexpected DOI response shape for '{doi}'")
                return None
            return self._extract_metadata(paper)
        except Exception as e:
            logger.error(f"Crossref: Error parsing DOI response for '{doi}': {e}")
            return None

    def _extract_metadata(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract and normalize paper metadata from Crossref response.

        Args:
            paper: Crossref paper object

        Returns:
            Normalized metadata dict or None if required fields missing
        """
        try:
            # Title (required)
            title = paper.get("title", [])
            if not title or not isinstance(title, list):
                return None
            title_str = title[0] if title else ""
            if not title_str:
                return None

            # Authors (required)
            authors_raw = paper.get("author", [])
            authors = []
            for author in authors_raw:
                if isinstance(author, dict):
                    family = author.get("family", "")
                    given = author.get("given", "")
                    if family:
                        # Validate author name (Fix 2 - reject single-letter authors)
                        is_valid, reason = validate_author_name(family)
                        if not is_valid:
                            logger.debug(f"Invalid author name '{family}': {reason}")
                            continue  # Skip invalid author, try next
                        # Store as "Family" only (consistent with existing format)
                        authors.append(family)

            if not authors:
                logger.debug(f"No authors found for '{title_str[:50]}...'")
                return None

            # Year (required)
            published = paper.get("published", {})
            date_parts = published.get("date-parts", [[]])
            year = 0
            if date_parts and date_parts[0]:
                year = date_parts[0][0] if date_parts[0] else 0

            if year == 0:
                # Try alternative date field
                published_online = paper.get("published-online", {})
                date_parts = published_online.get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    year = date_parts[0][0] if date_parts[0] else 0

            if year == 0:
                logger.debug(f"No publication year for '{title_str[:50]}...'")
                return None

            # DOI (highly preferred)
            doi = paper.get("DOI", "")

            # URL (construct from DOI if available)
            url = f"https://doi.org/{doi}" if doi else ""

            # Journal/Container (optional)
            container_title = paper.get("container-title", [])
            journal = container_title[0] if container_title else ""

            # Publisher (optional)
            publisher = paper.get("publisher", "")

            # Volume, Issue, Pages (optional)
            volume = paper.get("volume", "")
            issue = paper.get("issue", "")
            page = paper.get("page", "")

            # Abstract (optional) - Crossref sometimes returns JATS XML, extract text
            abstract = paper.get("abstract", "")
            if abstract:
                # Strip JATS XML tags if present (<jats:p>, <jats:italic>, etc.)
                import re
                abstract = re.sub(r'<[^>]+>', '', abstract)
                abstract = abstract.strip()

            # Source type
            crossref_type = paper.get("type", "")
            source_type = self._map_source_type(crossref_type)

            # Calculate confidence score
            confidence = self._calculate_confidence(
                has_doi=bool(doi), has_journal=bool(journal), has_publisher=bool(publisher), author_count=len(authors)
            )

            return {
                "title": title_str,
                "authors": authors,
                "year": year,
                "doi": doi,
                "url": url,
                "journal": journal,
                "publisher": publisher,
                "volume": volume,
                "issue": issue,
                "pages": page,
                "source_type": source_type,
                "confidence": confidence,
                "abstract": abstract if abstract else None,
            }

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return None

    def _map_source_type(self, crossref_type: str) -> str:
        """
        Map Crossref type to our source_type enum.

        Args:
            crossref_type: Crossref work type

        Returns:
            source_type: One of: journal, conference, book, report, website
        """
        type_mapping = {
            "journal-article": "journal",
            "proceedings-article": "conference",
            "book": "book",
            "book-chapter": "book",
            "report": "report",
            "posted-content": "report",
            "dataset": "report",
        }

        return type_mapping.get(crossref_type, "journal")  # Default to journal

    def _calculate_confidence(self, has_doi: bool, has_journal: bool, has_publisher: bool, author_count: int) -> float:
        """
        Calculate confidence score for paper metadata.

        Args:
            has_doi: Whether DOI is present
            has_journal: Whether journal name is present
            has_publisher: Whether publisher is present
            author_count: Number of authors

        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.5  # Base score

        if has_doi:
            score += 0.3  # DOI is strong signal of quality
        if has_journal:
            score += 0.1
        if has_publisher:
            score += 0.05
        if author_count > 0:
            score += 0.05

        return min(score, 1.0)  # Cap at 1.0
