#!/usr/bin/env python3
"""
ABOUTME: Serper.dev API client for web search with citation extraction
ABOUTME: Drop-in replacement for GeminiGroundedClient using Serper's Google Search API
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base import BaseAPIClient, validate_author_name, validate_publication_year
from .web_search_mixin import WebSearchMixin

logger = logging.getLogger(__name__)


# Domain filtering (shared with gemini_grounded.py)
TRUSTED_INDUSTRY_DOMAINS = [
    # Consulting firms
    'mckinsey.com', 'bcg.com', 'bain.com', 'deloitte.com', 'pwc.com', 'kpmg.com', 'ey.com', 'accenture.com',
    # International organizations
    'who.int', 'oecd.org', 'worldbank.org', 'un.org', 'imf.org', 'wto.org', 'unesco.org',
    # Industry analysts
    'gartner.com', 'forrester.com', 'idc.com', 'statista.com',
    # Government/academic TLDs
    '.gov', '.edu', '.ac.uk', '.gov.uk', '.edu.au', '.ac.jp', '.edu.cn',
    # News/quality journalism
    'reuters.com', 'bbc.com', 'nytimes.com', 'ft.com', 'economist.com', 'wsj.com',
    # Tech giants (official docs/research)
    'research.google', 'ai.google', 'research.microsoft.com', 'research.ibm.com',
    'openai.com', 'deepmind.com', 'anthropic.com',
]

BLOCKED_DOMAINS = [
    # Blog indicators
    '/blog/', '/blogs/', 'blog.', 'medium.com', 'substack.com', 'dev.to', 'hashnode.dev',
    # Social media
    'linkedin.com', 'twitter.com', 'facebook.com', 'instagram.com', 'tiktok.com',
    # Video platforms
    'youtube.com', 'vimeo.com',
    # Q&A sites (not primary sources)
    'quora.com', 'reddit.com', 'stackoverflow.com',
    # Wikipedia (not primary source)
    'wikipedia.org',
    # User-generated hosting platforms
    'github.io', 'gitlab.io', 'netlify.app', 'vercel.app', 'herokuapp.com',
    # Academic aggregators (need DOI enrichment)
    'semanticscholar.org', 'researchgate.net', 'academia.edu',
]


def is_trusted_domain(url: str) -> bool:
    """Check if URL is from a trusted industry domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in TRUSTED_INDUSTRY_DOMAINS)


def is_blocked_domain(url: str) -> bool:
    """Check if URL is from a blocked domain."""
    url_lower = url.lower()
    return any(blocked in url_lower for blocked in BLOCKED_DOMAINS)


def extract_year_from_url(url: str) -> Optional[int]:
    """Extract publication year from URL path patterns."""
    if not url:
        return None
    match = re.search(r'/20(1[0-9]|2[0-6])/', url)
    if match:
        return int(f"20{match.group(1)}")
    return None


class SerperClient(WebSearchMixin, BaseAPIClient):
    """
    Serper.dev API client for web search with citation support.

    Uses Serper's Google Search API to find credible sources, then validates
    and enriches results with metadata from CrossRef/PubMed when available.

    Features:
    - Google Search via Serper API (faster, cheaper than direct Google API)
    - Domain filtering (blocks blogs, social media, etc.)
    - Academic URL detection and metadata enrichment
    - DOI extraction and CrossRef lookup
    - Rate limiting and retries

    Requirements:
    - requests
    - SERPER_API_KEY environment variable
    """

    SERPER_API_URL = "https://google.serper.dev/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
        num_results: int = 10,
        validate_urls: bool = True,
    ):
        """
        Initialize Serper client.

        Args:
            api_key: Serper API key (defaults to SERPER_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            num_results: Number of search results to request
            validate_urls: Whether to validate URLs return HTTP 200
        """
        if load_dotenv is not None:
            load_dotenv()

        self.serper_api_key = api_key or os.getenv('SERPER_API_KEY')

        if not self.serper_api_key:
            raise ValueError(
                "SERPER_API_KEY not found. Set via environment variable or constructor."
            )

        super().__init__(
            base_url=self.SERPER_API_URL,
            api_key=self.serper_api_key,
            timeout=timeout,
            max_retries=max_retries,
            api_type='serper',
        )

        self.num_results = num_results
        self.validate_urls = validate_urls

        # Session for URL validation
        self.validation_session = requests.Session()
        self.validation_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        })

    def search_paper(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a credible source using Serper Google Search API.

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
            # Search via Serper
            results = self._search_serper(query)

            if not results:
                return None

            # Filter and validate results
            for result in results:
                validated = self._validate_and_enrich(result)
                if validated:
                    return validated

            return None

        except Exception as e:
            logger.error(f"Serper search error: {e}")
            return None

    def _search_serper(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute search via Serper API.

        Args:
            query: Search query

        Returns:
            List of raw search result dicts
        """
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json',
        }

        payload = {
            'q': query,
            'num': self.num_results,
        }

        try:
            response = self.session.post(
                self.SERPER_API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if not response.ok:
                logger.warning(f"Serper API error {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()

            # Extract organic results
            organic = data.get('organic', [])

            results = []
            for item in organic:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'position': item.get('position', 0),
                })

            logger.info(f"Serper: Found {len(results)} results for: {query[:50]}...")
            return results

        except requests.exceptions.Timeout:
            logger.warning(f"Serper timeout for query: {query[:50]}...")
            return []
        except Exception as e:
            logger.error(f"Serper request error: {e}")
            return []

    def close(self) -> None:
        """Close HTTP sessions."""
        super().close()
        if hasattr(self, 'validation_session'):
            self.validation_session.close()


# Convenience function matching existing interface
def search_with_serper(query: str, num_results: int = 10) -> Optional[Dict[str, Any]]:
    """
    Search for a credible source using Serper.

    Args:
        query: Search query
        num_results: Number of results to request

    Returns:
        Source metadata dict or None
    """
    try:
        client = SerperClient(num_results=num_results)
        return client.search_paper(query)
    except Exception as e:
        logger.error(f"Serper search error: {e}")
        return None
