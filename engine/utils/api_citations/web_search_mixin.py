#!/usr/bin/env python3
"""
ABOUTME: Shared mixin for web search clients (Serper, Tavily)
ABOUTME: Extracts common validation, enrichment, and metadata logic to avoid duplication
"""

import re
import logging
from typing import Optional, Dict, Any

from .serper_client import is_trusted_domain, is_blocked_domain, extract_year_from_url

logger = logging.getLogger(__name__)


class WebSearchMixin:
    """
    Mixin providing shared validation and metadata enrichment for web search clients.

    Both SerperClient and TavilySearchClient share identical logic for:
    - Domain filtering and URL validation
    - DOI extraction from URLs
    - Academic URL detection
    - Metadata enrichment from PubMed, PMC, and CrossRef
    - Author formatting

    Subclasses must provide:
    - self.validate_urls: bool
    - self.validation_session: requests.Session
    """

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

    def _fetch_crossref_metadata(self, doi: str, original_url: str = None) -> Optional[Dict[str, Any]]:
        """Fetch metadata from CrossRef using DOI."""
        try:
            api_url = f"https://api.crossref.org/works/{doi}"
            headers = {'User-Agent': 'OpenDraft/1.0 (mailto:support@opendraft.ai)'}

            response = self.validation_session.get(api_url, headers=headers, timeout=10)
            if not response.ok:
                return None

            data = response.json().get('message', {})
            if not data:
                return None

            title_list = data.get('title', [])
            title = title_list[0] if title_list else None

            authors = data.get('author', [])
            author_str = None
            if authors:
                first = authors[0]
                last_name = first.get('family', first.get('name', 'Unknown'))
                author_str = f"{last_name} et al." if len(authors) > 1 else last_name

            year = None
            for date_field in ['published-print', 'published-online', 'created']:
                date_parts = data.get(date_field, {}).get('date-parts', [[]])
                if date_parts and date_parts[0]:
                    year = str(date_parts[0][0])
                    break

            container = data.get('container-title', [])
            journal = container[0] if container else None

            return {
                'title': title,
                'authors': author_str,
                'year': year,
                'doi': doi,
                'url': original_url or f"https://doi.org/{doi}",
                'journal': journal,
                'source_type': 'journal',
            }
        except Exception as e:
            logger.debug(f"CrossRef API error: {e}")
            return None

    def _format_authors(self, authors: list) -> Optional[str]:
        """Format author list to 'LastName et al.' format."""
        if not authors:
            return None

        first = authors[0]
        if isinstance(first, dict):
            name = first.get('name', '')
        else:
            name = str(first)

        parts = name.split()
        last_name = parts[0] if parts else name

        if len(authors) > 1:
            return f"{last_name} et al."
        return last_name
