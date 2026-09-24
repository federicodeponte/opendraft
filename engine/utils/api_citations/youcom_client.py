#!/usr/bin/env python3
"""
ABOUTME: You.com Search API client for web search with citation extraction
ABOUTME: Drop-in replacement for SerperClient using You.com's Search API

Keyless mode: no API key needed (uses free tier at api.you.com/search).
Authenticated mode: set YDC_API_KEY for higher rate limits and premium results.

Supports both modes natively. Keyless mode uses the same endpoint without
an Authorization header, falling back gracefully if the free rate limit
is exhausted.

Keyless alternative (MCP-based): https://api.you.com/mcp?profile=free
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, quote

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base import BaseAPIClient, validate_author_name, validate_publication_year

logger = logging.getLogger(__name__)


# Same domain filtering constants as serper_client.py
TRUSTED_INDUSTRY_DOMAINS = [
    'mckinsey.com', 'bcg.com', 'bain.com', 'deloitte.com', 'pwc.com', 'kpmg.com', 'ey.com', 'accenture.com',
    'who.int', 'oecd.org', 'worldbank.org', 'un.org', 'imf.org', 'wto.org', 'unesco.org',
    'gartner.com', 'forrester.com', 'idc.com', 'statista.com',
    '.gov', '.edu', '.ac.uk', '.gov.uk', '.edu.au', '.ac.jp', '.edu.cn',
    'reuters.com', 'bbc.com', 'nytimes.com', 'ft.com', 'economist.com', 'wsj.com',
    'research.google', 'ai.google', 'research.microsoft.com', 'research.ibm.com',
    'openai.com', 'deepmind.com', 'anthropic.com',
]

BLOCKED_DOMAINS = [
    '/blog/', '/blogs/', 'blog.', 'medium.com', 'substack.com', 'dev.to', 'hashnode.dev',
    'linkedin.com', 'twitter.com', 'facebook.com', 'instagram.com', 'tiktok.com',
    'youtube.com', 'vimeo.com',
    'quora.com', 'reddit.com', 'stackoverflow.com',
    'wikipedia.org',
    'github.io', 'gitlab.io', 'netlify.app', 'vercel.app', 'herokuapp.com',
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


class YoucomClient(BaseAPIClient):
    """
    You.com Search API client for web search with citation support.

    Uses the You.com Search API to find credible sources, then validates
    and enriches results with metadata from CrossRef/PubMed when available.

    Features:
    - Web search via You.com API (free tier available, no API key required)
    - Keyless mode works out of the box (lower rate limit)
    - YDC_API_KEY unlocks authenticated mode (higher rate limits)
    - Domain filtering (blocks blogs, social media, etc.)
    - Academic URL detection and metadata enrichment
    - DOI extraction and CrossRef lookup
    - Rate limiting and retries

    Environment Variables:
        YDC_API_KEY: You.com API key (optional — keyless mode without it)
    """

    # You.com Search API endpoint
    SEARCH_API_URL = "https://api.you.com/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
        num_results: int = 10,
        validate_urls: bool = True,
        keyless: bool = False,
    ):
        """
        Initialize You.com client.

        Args:
            api_key: You.com API key (defaults to YDC_API_KEY env var).
                If neither is set, keyless mode is used.
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            num_results: Number of search results to request
            validate_urls: Whether to validate URLs return HTTP 200
            keyless: Force keyless mode even if YDC_API_KEY is set
        """
        if load_dotenv is not None:
            load_dotenv()

        self.youcom_api_key = api_key or os.getenv('YDC_API_KEY')

        if self.youcom_api_key and not keyless:
            # Authenticated mode
            super().__init__(
                base_url=self.SEARCH_API_URL,
                api_key=self.youcom_api_key,
                timeout=timeout,
                max_retries=max_retries,
                api_type='youcom',
            )
            self.auth_header = f"Bearer {self.youcom_api_key}"
            logger.info("You.com client initialized in AUTHENTICATED mode (YDC_API_KEY set)")
        else:
            # Keyless mode
            super().__init__(
                base_url=self.SEARCH_API_URL,
                api_key=None,
                timeout=timeout,
                max_retries=max_retries,
                api_type='youcom',
            )
            self.auth_header = None
            if self.youcom_api_key:
                logger.info("You.com client initialized in KEYLESS mode (YDC_API_KEY ignored, keyless=True)")
            else:
                logger.info("You.com client initialized in KEYLESS mode (no YDC_API_KEY)")

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
        Search for a credible source using You.com Search API.

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
            results = self._search_youcom(query)

            if not results:
                return None

            # Filter and validate results
            for result in results:
                validated = self._validate_and_enrich(result)
                if validated:
                    return validated

            return None

        except Exception as e:
            logger.error(f"You.com search error: {e}")
            return None

    def _search_youcom(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute search via You.com Search API.

        Args:
            query: Search query

        Returns:
            List of raw search result dicts
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if self.auth_header:
            headers['Authorization'] = self.auth_header

        # Build request payload
        params = {
            'query': query,
            'num_results': self.num_results,
        }

        try:
            response = self.session.get(
                self.SEARCH_API_URL,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )

            if not response.ok:
                logger.warning(
                    f"You.com API error {response.status_code}: {response.text[:200]}"
                    f"{' (keyless mode rate limit?)' if not self.auth_header else ''}"
                )
                return []

            data = response.json()

            # Extract results - You.com Search API returns them in 'results' key
            results_raw = data.get('results', data.get('hits', []))

            results = []
            for item in results_raw:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('url', item.get('link', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                    'position': item.get('position', 0),
                })

            logger.info(
                f"You.com: Found {len(results)} results for: {query[:50]}..."
                f"{' [keyless]' if not self.auth_header else ''}"
            )
            return results

        except requests.exceptions.Timeout:
            logger.warning(f"You.com timeout for query: {query[:50]}...")
            return []
        except Exception as e:
            logger.error(f"You.com request error: {e}")
            return []

    def _validate_and_enrich(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate source domain and enrich with metadata.

        Args:
            result: Raw search result dict

        Returns:
            Enriched source dict or None if invalid
        """
        url = result.get('url', '')
        title = result.get('title', '')

        if not url:
            return None

        # Domain filtering
        if is_blocked_domain(url):
            logger.debug(f"Blocked domain: {url}")
            return None

        # Check for DOI in URL
        doi = self._extract_doi_from_url(url)
        has_doi = bool(doi)

        # Validate domain quality
        if not has_doi and not is_trusted_domain(url):
            if not self._is_academic_url(url):
                logger.debug(f"Untrusted domain without DOI: {url}")
                return None

        # Optional URL validation (HTTP 200 check)
        if self.validate_urls:
            if not self._validate_url(url):
                logger.debug(f"URL validation failed: {url}")
                return None

        # Build base result
        validated = {
            'title': title,
            'url': url,
            'snippet': result.get('snippet'),
            'authors': None,
            'year': None,
            'doi': doi,
            'source_type': 'report' if is_trusted_domain(url) else 'website',
        }

        # Try to extract year from URL
        url_year = extract_year_from_url(url)
        if url_year:
            validated['year'] = str(url_year)

        # Enrich academic URLs with metadata
        if self._is_academic_url(url):
            enriched = self._enrich_academic_metadata(url)
            if enriched:
                enriched['url'] = url
                if not enriched.get('snippet'):
                    enriched['snippet'] = result.get('snippet')
                return enriched

        # Enrich via DOI if available
        if doi and not validated.get('authors'):
            crossref_data = self._fetch_crossref_metadata(doi)
            if crossref_data:
                validated.update({
                    'title': crossref_data.get('title') or title,
                    'authors': crossref_data.get('authors'),
                    'year': crossref_data.get('year') or validated.get('year'),
                    'journal': crossref_data.get('journal'),
                    'source_type': 'journal',
                })

        return validated

    def _extract_doi_from_url(self, url: str) -> Optional[str]:
        """Extract DOI from URL if present."""
        match = re.search(r'doi\.org/(10\.[^\s&?#]+)', url)
        if match:
            return match.group(1)

        match = re.search(r'(10\.\d{4,}/[^\s&?#]+)', url)
        if match:
            return match.group(1)

        return None

    def _is_academic_url(self, url: str) -> bool:
        """Check if URL is from an academic domain."""
        academic_domains = [
            'pubmed.ncbi.nlm.nih.gov', 'pmc.ncbi.nlm.nih.gov', 'doi.org',
            'mdpi.com', 'springer.com', 'nature.com', 'sciencedirect.com',
            'wiley.com', 'tandfonline.com', 'frontiersin.org', 'plos.org',
            'cell.com', 'bmj.com', 'jamanetwork.com', 'thelancet.com', 'nejm.org',
            'arxiv.org', 'biorxiv.org', 'medrxiv.org', 'ieee.org', 'acm.org',
            'journals.sagepub.com', 'cambridge.org', 'oxford.ac.uk',
        ]
        url_lower = url.lower()
        return any(domain in url_lower for domain in academic_domains)

    def _validate_url(self, url: str) -> bool:
        """Validate URL returns HTTP 200."""
        try:
            response = self.validation_session.head(
                url,
                allow_redirects=True,
                timeout=10,
            )
            if response.status_code == 405:
                response = self.validation_session.get(
                    url,
                    allow_redirects=True,
                    timeout=10,
                    stream=True,
                )
                response.close()
            return response.status_code == 200
        except Exception:
            return False

    def _enrich_academic_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Enrich source with metadata from academic APIs."""
        try:
            if 'pubmed.ncbi.nlm.nih.gov' in url:
                pmid = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
                if pmid:
                    return self._fetch_pubmed_metadata(pmid.group(1), url)

            if 'pmc.ncbi.nlm.nih.gov' in url:
                pmcid = re.search(r'PMC(\d+)', url)
                if pmcid:
                    return self._fetch_pmc_metadata(pmcid.group(1), url)

            if 'doi.org' in url:
                doi = self._extract_doi_from_url(url)
                if doi:
                    return self._fetch_crossref_metadata(doi, url)

            doi = self._extract_doi_from_url(url)
            if doi:
                return self._fetch_crossref_metadata(doi, url)

        except Exception as e:
            logger.debug(f"Metadata enrichment error for {url}: {e}")

        return None

    def _fetch_pubmed_metadata(self, pmid: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata from PubMed via NCBI E-utilities."""
        try:
            api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {"db": "pubmed", "id": pmid, "retmode": "json"}

            response = self.validation_session.get(api_url, params=params, timeout=10)
            if not response.ok:
                return None

            data = response.json()
            result = data.get('result', {}).get(pmid, {})

            if not result or 'error' in result:
                return None

            authors = result.get('authors', [])
            author_str = self._format_authors(authors) if authors else None

            pubdate = result.get('pubdate', '')
            year = pubdate[:4] if pubdate and len(pubdate) >= 4 else None

            doi = None
            for aid in result.get('articleids', []):
                if aid.get('idtype') == 'doi':
                    doi = aid.get('value')
                    break

            return {
                'title': result.get('title', '').rstrip('.'),
                'authors': author_str,
                'year': year,
                'doi': doi,
                'url': original_url,
                'journal': result.get('fulljournalname') or result.get('source'),
                'source_type': 'journal',
            }
        except Exception as e:
            logger.debug(f"PubMed API error: {e}")
            return None

    def _fetch_pmc_metadata(self, pmcid: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata from PMC via NCBI E-utilities."""
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pmc", "term": f"PMC{pmcid}[pmcid]", "retmode": "json"}

            response = self.validation_session.get(search_url, params=params, timeout=10)
            if not response.ok:
                return None

            data = response.json()
            id_list = data.get('esearchresult', {}).get('idlist', [])

            if not id_list:
                return None

            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {"db": "pmc", "id": id_list[0], "retmode": "json"}

            response = self.validation_session.get(summary_url, params=params, timeout=10)
            if not response.ok:
                return None

            data = response.json()
            result = data.get('result', {}).get(id_list[0], {})

            if not result or 'error' in result:
                return None

            authors = result.get('authors', [])
            author_str = self._format_authors(authors) if authors else None

            pubdate = result.get('pubdate', '') or result.get('epubdate', '')
            year = pubdate[:4] if pubdate and len(pubdate) >= 4 else None

            doi = None
            for aid in result.get('articleids', []):
                if aid.get('idtype') == 'doi':
                    doi = aid.get('value')
                    break

            return {
                'title': result.get('title', '').rstrip('.'),
                'authors': author_str,
                'year': year,
                'doi': doi,
                'url': original_url,
                'journal': result.get('fulljournalname') or result.get('source'),
                'source_type': 'journal',
            }
        except Exception as e:
            logger.debug(f"PMC API error: {e}")
            return None

    def _fetch_crossref_metadata(self, doi: str, original_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch metadata from Crossref by DOI."""
        try:
            crossref_url = f"https://api.crossref.org/works/{doi}"
            response = self.validation_session.get(crossref_url, timeout=10)
            if not response.ok:
                return None

            data = response.json()
            message = data.get('message', {})

            # Extract authors
            authors = message.get('author', [])
            author_list = []
            for author in authors:
                given = author.get('given', '')
                family = author.get('family', '')
                if given and family:
                    author_list.append(f"{family}, {given}")
                elif family:
                    author_list.append(family)

            author_str = '; '.join(author_list[:5]) if author_list else None
            if author_list and len(author_list) > 5:
                author_str += ' et al.'

            # Extract year
            date_parts = message.get('published-print', {}).get('date-parts', [[]])[0]
            if not date_parts:
                date_parts = message.get('published-online', {}).get('date-parts', [[]])[0]
            if not date_parts:
                date_parts = message.get('created', {}).get('date-parts', [[]])[0]
            year = str(date_parts[0]) if date_parts and len(date_parts) > 0 else None

            # Extract type
            pub_type = message.get('type', 'journal-article')
            source_type = 'journal' if 'journal' in pub_type else 'report'

            return {
                'title': message.get('title', [''])[0] if message.get('title') else None,
                'authors': author_str,
                'year': year,
                'doi': doi,
                'url': original_url or message.get('URL'),
                'journal': message.get('container-title', [''])[0] if message.get('container-title') else None,
                'source_type': source_type,
            }
        except Exception as e:
            logger.debug(f"Crossref API error: {e}")
            return None

    def _format_authors(self, authors: List[Dict[str, Any]]) -> str:
        """Format author list to string."""
        author_list = []
        for author in authors:
            name = author.get('name', '')
            if name:
                author_list.append(name)
            else:
                given = author.get('given', '')
                family = author.get('family', '')
                if given and family:
                    author_list.append(f"{family}, {given}")
                elif family:
                    author_list.append(family)
        if not author_list:
            return None
        result = '; '.join(author_list[:5])
        if len(author_list) > 5:
            result += ' et al.'
        return result

    def close(self) -> None:
        """Close all sessions."""
        super().close()
        self.validation_session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()