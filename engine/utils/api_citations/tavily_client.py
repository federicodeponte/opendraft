#!/usr/bin/env python3
"""
ABOUTME: Tavily Search API client for web search with citation extraction
ABOUTME: Parallel search option alongside Serper using Tavily's AI-optimized search API
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List

import requests

try:
    from tavily import TavilyClient as _TavilyClient
except ImportError:
    _TavilyClient = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base import BaseAPIClient, validate_author_name, validate_publication_year
from .web_search_mixin import WebSearchMixin

logger = logging.getLogger(__name__)


class TavilySearchClient(WebSearchMixin, BaseAPIClient):
    """
    Tavily Search API client for web search with citation support.

    Uses Tavily's AI-optimized search API to find credible sources, then validates
    and enriches results with metadata from CrossRef/PubMed when available.

    Features:
    - AI-optimized search via Tavily API (relevance-scored results)
    - Domain filtering (blocks blogs, social media, etc.)
    - Academic URL detection and metadata enrichment
    - DOI extraction and CrossRef lookup

    Requirements:
    - tavily-python
    - TAVILY_API_KEY environment variable
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
        num_results: int = 10,
        validate_urls: bool = True,
    ):
        """
        Initialize Tavily client.

        Args:
            api_key: Tavily API key (defaults to TAVILY_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            num_results: Number of search results to request
            validate_urls: Whether to validate URLs return HTTP 200
        """
        if _TavilyClient is None:
            raise ImportError(
                "tavily-python is required. Install with: pip install tavily-python"
            )

        if load_dotenv is not None:
            load_dotenv()

        self.tavily_api_key = api_key or os.getenv('TAVILY_API_KEY')

        if not self.tavily_api_key:
            raise ValueError(
                "TAVILY_API_KEY not found. Set via environment variable or constructor."
            )

        super().__init__(
            base_url="https://api.tavily.com",
            api_key=self.tavily_api_key,
            timeout=timeout,
            max_retries=max_retries,
            api_type='tavily',
        )

        self.num_results = num_results
        self.validate_urls = validate_urls

        # Initialize Tavily client
        self.tavily_client = _TavilyClient(api_key=self.tavily_api_key)

        # Session for URL validation and metadata enrichment
        self.validation_session = requests.Session()
        self.validation_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        })

    def search_paper(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a credible source using Tavily Search API.

        Args:
            query: Search query (topic, title, keywords)

        Returns:
            Source metadata dict with keys:
                - title: str
                - url: str
                - authors: Optional[str]
                - year: Optional[str]
                - doi: Optional[str]
                - snippet: Optional[str]
                - source_type: str ('journal', 'report', 'website')
            Returns None if no valid source found.
        """
        try:
            results = self._search_tavily(query)

            if not results:
                return None

            # Filter and validate results
            for result in results:
                validated = self._validate_and_enrich(result)
                if validated:
                    return validated

            return None

        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return None

    def _search_tavily(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute search via Tavily API.

        Args:
            query: Search query

        Returns:
            List of raw search result dicts
        """
        try:
            response = self.tavily_client.search(
                query=query,
                max_results=self.num_results,
                search_depth="advanced",
            )

            tavily_results = response.get('results', [])

            results = []
            for idx, item in enumerate(tavily_results):
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('url', ''),
                    'snippet': item.get('content', ''),
                    'position': idx + 1,
                    'score': item.get('score', 0),
                })

            logger.info(f"Tavily: Found {len(results)} results for: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Tavily request error: {e}")
            return []

    def close(self) -> None:
        """Close HTTP sessions."""
        super().close()
        if hasattr(self, 'validation_session'):
            self.validation_session.close()


# Convenience function matching existing interface
def search_with_tavily(query: str, num_results: int = 10) -> Optional[Dict[str, Any]]:
    """
    Search for a credible source using Tavily.

    Args:
        query: Search query
        num_results: Number of results to request

    Returns:
        Source metadata dict or None
    """
    try:
        client = TavilySearchClient(num_results=num_results)
        return client.search_paper(query)
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return None
