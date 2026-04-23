#!/usr/bin/env python3
"""
ABOUTME: Web search client with Google Search grounding for source discovery
ABOUTME: Uses grounded web search via REST API to find and validate real web sources with citations
"""

import os
import re
import json
import logging
import sys
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Safe print function that handles broken pipes (worker runs with stdio: 'ignore')
def safe_print(*args, **kwargs):
    """Print wrapper that catches BrokenPipeError when stdout is closed."""
    try:
        print(*args, **kwargs)
    except (BrokenPipeError, OSError):
        # Pipe is closed (worker running with stdio: 'ignore'), use logger instead
        try:
            message = ' '.join(str(arg) for arg in args)
            logger.debug(message)
        except:
            pass
        # Prevent further broken pipe errors by redirecting stdout
        try:
            sys.stdout = open(os.devnull, 'w')
        except:
            pass

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base import BaseAPIClient

# =========================================================================
# Domain Quality Filtering for Source Validation
# =========================================================================

# Trusted industry domains (accepted without DOI)
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
    'research.google', 'ai.google', 'research.microsoft.com', 'research.ibm.com', 'research.facebook.com',
    'openai.com', 'deepmind.com', 'anthropic.com',
]

# Blocked domains (never accept)
BLOCKED_DOMAINS = [
    # Blog indicators
    '/blog/', '/blogs/', 'blog.', 'medium.com', 'substack.com', 'dev.to', 'hashnode.dev',
    # AI startup marketing blogs (low quality)
    'private-ai.com', 'thoughtful.ai', 'skywork.ai', 'copy.ai', 'jasper.ai',
    # Social media
    'linkedin.com', 'twitter.com', 'facebook.com', 'instagram.com', 'tiktok.com',
    # Video platforms
    'youtube.com', 'vimeo.com',
    # Q&A sites (not primary sources)
    'quora.com', 'reddit.com', 'stackoverflow.com',
    # Wikipedia (not primary source)
    'wikipedia.org',
    # Generic content farms
    'hubspot.com/blog', 'forbes.com/sites', 'entrepreneur.com',
    # User-generated hosting platforms (Fix 2) - anyone can publish, no editorial review
    'github.io', 'gitlab.io', 'netlify.app', 'vercel.app', 'herokuapp.com',
    'pages.dev', 'surge.sh', 'firebaseapp.com', 'web.app', 'github.com',
    # Academic aggregators (need to enrich via DOI, not cite directly)
    'semanticscholar.org', 'researchgate.net',
    # Document publishing/sharing platforms (user-generated content)
    'issuu.com', 'scribd.com', 'slideshare.net', 'academia.edu',
    # Law firm blogs/marketing (not academic)
    'cooley.com', 'linklaters.com', 'cliffordchance.com', 'dlapiper.com',
]

def is_trusted_domain(url: str) -> bool:
    """Check if URL is from a trusted industry domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in TRUSTED_INDUSTRY_DOMAINS)

def is_blocked_domain(url: str) -> bool:
    """Check if URL is from a blocked domain (blogs, social, etc.)."""
    url_lower = url.lower()
    return any(blocked in url_lower for blocked in BLOCKED_DOMAINS)

def validate_source_domain(url: str, has_doi: bool = False) -> tuple:
    """
    Validate source domain for academic quality.
    
    Args:
        url: Source URL
        has_doi: Whether source has a valid DOI
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if not url:
        return (False, "no_url")
    
    # Always accept if has DOI (academic quality guaranteed)
    if has_doi:
        return (True, "has_doi")
    
    # Block known bad domains
    if is_blocked_domain(url):
        return (False, "blocked_domain")
    
    # Accept trusted industry domains
    if is_trusted_domain(url):
        return (True, "trusted_domain")
    
    # For unknown domains without DOI, reject
    # This prevents random websites from being cited
    return (False, "unknown_domain_no_doi")



def extract_year_from_url(url: str) -> int:
    """
    Extract publication year from URL path patterns.
    
    Many URLs contain publication year in path, e.g.:
    - /2023/05/article-title
    - /publications/2024/report.pdf
    - /news-events/news/2023/announcement
    
    Args:
        url: Source URL
        
    Returns:
        Extracted year (2010-2025 range) or None
    """
    import re
    if not url:
        return None
    
    # Match /20XX/ patterns in URL (years 2010-2025)
    match = re.search(r'/20(1[0-9]|2[0-5])/', url)
    if match:
        return int(f"20{match.group(1)}")
    
    # Also try ?year=20XX or &year=20XX query params
    match = re.search(r'[?&]year=(20(?:1[0-9]|2[0-5]))', url)
    if match:
        return int(match.group(1))
    
    return None


class GeminiGroundedClient(BaseAPIClient):
    """
    Web search client with Google Search grounding.

    Uses grounded search with Google Search tooling via REST API to discover real sources
    with citations. Validates URLs and extracts metadata.

    Features:
    - Google Search grounding for real-time source discovery (via REST API)
    - Deep research capability with high token limits
    - URL validation (HTTP 200 checks)
    - Redirect unwrapping to final destinations
    - Domain filtering (competitors, forbidden hosts)
    - Grounding citation extraction

    Requirements:
    - requests
    - GOOGLE_API_KEY environment variable
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,  # Reduced timeout for fast gemini-2.5-flash
        max_retries: int = 3,
        forbidden_domains: Optional[List[str]] = None,
        validate_urls: bool = True
    ):
        """
        Initialize grounded web search client.

        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY env var)
            timeout: Request timeout in seconds (60s for parallel execution)
            max_retries: Number of retry attempts
            forbidden_domains: List of domains to filter out
            validate_urls: Whether to validate URLs return HTTP 200
        """
        # Load .env file to ensure API key is available
        if load_dotenv is not None:
            load_dotenv()

        super().__init__(
            api_key=api_key or os.getenv('GOOGLE_API_KEY'),
            base_url='https://generativelanguage.googleapis.com/v1beta/models',
            timeout=timeout,
            max_retries=max_retries
        )

        if not requests:
            raise ImportError(
                "requests not installed. Run: pip install requests"
            )

        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found. Set via environment variable or constructor."
            )

        # Use the grounded search model for fast source discovery with a two-step approach
        self.model_name = 'gemini-2.5-flash'

        # Multi-key rotation for 429 rate limit handling
        self._fallback_keys = {
            'fallback': os.getenv('GOOGLE_API_KEY_FALLBACK', ''),
            'fallback_2': os.getenv('GOOGLE_API_KEY_FALLBACK_2', ''),
            'fallback_3': os.getenv('GOOGLE_API_KEY_FALLBACK_3', ''),
        }

        self.forbidden_domains = forbidden_domains or []
        self.validate_urls = validate_urls

        # Session for both API calls and URL validation
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
        })

    def _try_dataforseo_fallback(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Fallback to DataForSEO SERP API when web search hits quota limits.
        Uses DataForSEO to get search results, then feeds them to the grounded processor for validation.

        Args:
            query: Search query

        Returns:
            Citation metadata or None
        """
        try:
            from .dataforseo_client import DataForSEOClient
            dataforseo = DataForSEOClient(timeout=15)
            result = dataforseo.search_paper(query)
            return result
        except Exception as e:
            logger.warning(f"DataForSEO fallback failed: {e}")
            return None

    def search_paper(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a source using grounded web search via REST API.
        Falls back to DataForSEO SERP API when web search hits quota limits (429).

        Args:
            query: Search query (topic, title, keywords)

        Returns:
            Paper/source metadata dict with keys:
                - title: str
                - url: str (validated, unwrapped)
                - authors: Optional[str]
                - date: Optional[str]
                - snippet: Optional[str]
            Returns None if no valid source found.
        """
        try:
            # Construct grounded search prompt
            prompt = self._build_search_prompt(query)

            # Generate with grounded web search via REST API
            response_data = self._generate_content_with_grounding(prompt)

            # If web search hit quota limit (429), try DataForSEO fallback
            if not response_data:
                return self._try_dataforseo_fallback(query)

            # Extract grounding citations from response
            sources = self._extract_grounding_citations(response_data)

            if not sources:
                return None

            # Validate and unwrap URLs
            valid_sources = self._validate_sources(sources)

            if not valid_sources:
                return None

            # Return first valid source
            return valid_sources[0]

        except Exception as e:
            # Try DataForSEO fallback on any error
            try:
                from utils.web_search_fallback import WebSearchFallback
                fallback = WebSearchFallback()
                if fallback.dataforseo.enabled:
                    logger.info(f"Web search fallback - trying DataForSEO for: {query[:50]}...")
                    results = fallback.dataforseo.search(query, limit=5)
                    if results and len(results) > 0:
                        result = results[0]
                        return {
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("snippet", ""),
                            "source": "DataForSEO"
                        }
            except Exception as fallback_error:
                logger.warning(f"DataForSEO fallback failed: {fallback_error}")
            
            safe_print(f"Web search grounded error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_content_with_grounding(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Generate content using grounded web search via REST API.

        Args:
            prompt: User prompt for generation

        Returns:
            API response data dict, or None if error
        """
        try:
            # Build request body (matching gtm-os-v2 pattern)
            body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,  # Low temp for factual accuracy
                    "maxOutputTokens": 8192,  # High limit for deep research
                },
                "tools": [
                    {"googleSearch": {}},  # Enable grounded web search
                    {"urlContext": {}},    # Enable URL context for scraping
                ]
            }

            # Make REST API call
            url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"

            response = self.session.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )

            if not response.ok:
                error_text = response.text[:500]

                # Handle 429 rate limit with multi-key rotation
                if response.status_code == 429:
                    try:
                        from utils.backpressure import BackpressureManager, APIType
                        bp = BackpressureManager()
                        bp.signal_429(APIType.WEB_SEARCH)

                        # Only attempt key rotation if at least one fallback key is configured
                        available_fallbacks = [k for k in self._fallback_keys.values() if k]
                        if available_fallbacks:
                            # Use backpressure manager to pick the least-throttled key
                            best_key, best_type = bp.get_best_gemini_key(
                                primary=self.api_key,
                                fallback=available_fallbacks[0],
                                fallback_2=available_fallbacks[1] if len(available_fallbacks) > 1 else None,
                                fallback_3=available_fallbacks[2] if len(available_fallbacks) > 2 else None,
                            )

                            # Only retry if we got a different, non-empty key
                            if best_key and best_key != self.api_key:
                                safe_print(f"Web search rate limit (429) - switching to {best_type.value}")
                                retry_url = f"{self.base_url}/{self.model_name}:generateContent?key={best_key}"
                                response = self.session.post(
                                    retry_url,
                                    json=body,
                                    headers={"Content-Type": "application/json"},
                                    timeout=self.timeout
                                )
                                if response.ok:
                                    data = response.json()
                                    if data.get('candidates'):
                                        return data
                                # Signal 429 for the fallback key too
                                if response.status_code == 429:
                                    bp.signal_429(best_type)
                                safe_print(f"Fallback key ({best_type.value}) also failed: {response.status_code}")
                    except Exception as bp_err:
                        logger.debug(f"Backpressure key rotation error: {bp_err}")

                safe_print(f"Web search API error {response.status_code}: {error_text}")
                return None

            data = response.json()

            # Check for valid response
            if not data.get('candidates'):
                safe_print(f"No candidates in response: {data}")
                return None

            return data

        except Exception as e:
            safe_print(f"Error calling grounded web search API: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_search_prompt(self, query: str) -> str:
        """Build search prompt for grounded web search."""
        return f"""Find a credible web source about: {query}

Requirements:
- Must be from a reputable source (academic, news, official documentation)
- Must be publicly accessible (no paywalls)
- Prefer recent sources (last 5 years)
- Include author and publication date if available

Provide the source title, URL, and a brief snippet explaining relevance."""

    def _extract_grounding_citations(
        self,
        response_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Extract grounding citations from web search REST API response.

        Args:
            response_data: API response dict (from REST API)

        Returns:
            List of dicts with 'title', 'url', 'snippet' keys
        """
        sources = []

        try:
            # Check for candidates in response
            candidates = response_data.get('candidates', [])
            if not candidates:
                return sources

            candidate = candidates[0]

            # Extract grounding metadata (matching gtm-os-v2 pattern)
            grounding_metadata = candidate.get('groundingMetadata')

            if grounding_metadata:
                # Extract from grounding chunks
                grounding_chunks = grounding_metadata.get('groundingChunks', [])

                for chunk in grounding_chunks:
                    source = {}

                    # Extract web source details
                    web = chunk.get('web', {})
                    if web:
                        uri = web.get('uri')
                        title = web.get('title')

                        if uri:
                            source['url'] = uri
                            source['title'] = title if title else uri  # Use URL as title if title missing

                        if source.get('url'):  # Only URL required
                            sources.append(source)

            # Also extract from text content as fallback
            content = candidate.get('content', {})
            parts = content.get('parts', [])
            if parts:
                text = parts[0].get('text', '')
                if text:
                    sources.extend(self._extract_urls_from_text(text))

        except Exception as e:
            safe_print(f"Error extracting grounding citations: {e}")
            import traceback
            traceback.print_exc()

        return sources

    def _extract_urls_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract URLs from response text as fallback."""
        sources = []
        url_pattern = re.compile(r'https?://[^\s\)]+')

        matches = url_pattern.findall(text)
        for url in matches:
            url = url.rstrip('.,;:')
            sources.append({
                'url': url,
                'title': 'Source',  # Generic title
            })

        return sources

    def _validate_sources(
        self,
        sources: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Validate and unwrap source URLs.

        Args:
            sources: List of source dicts with 'url' and 'title'

        Returns:
            List of validated source dicts with metadata
        """
        valid_sources = []

        for source in sources:
            url = source.get('url')
            if not url:
                continue

            # Filter forbidden domains
            if self._is_forbidden_domain(url):
                continue

            # ALWAYS unwrap grounding-api-redirect URLs to get real destination
            # But skip HTTP validation to prevent timeouts
            if 'grounding-api-redirect' in url or 'vertexaisearch.cloud.google.com' in url:
                final_url = self._unwrap_url(url)
                if not final_url:
                    continue  # Failed to unwrap, skip this source
            elif self.validate_urls:
                # For non-grounding URLs, validate only if enabled
                final_url = self._unwrap_url(url)
                if not final_url:
                    continue
                if not self._validate_url(final_url):
                    continue
            else:
                # Use URL as-is (no unwrapping, no validation)
                final_url = url

            # Validate domain quality (Fix 1 from devil's advocate analysis)
            has_doi = bool(self._extract_doi_from_academic_url(final_url) or 
                          self._extract_doi_from_doi_url(final_url) if 'doi.org' in final_url else None)
            is_valid, reason = validate_source_domain(final_url, has_doi)
            
            if not is_valid:
                # Skip blocked/untrusted sources
                continue
            
            # Build validated source metadata
            valid_source = {
                'title': source.get('title', 'Source'),
                'url': final_url,
                'snippet': source.get('snippet'),
                'authors': None,  # Not available from grounding
                'date': None,  # Not available from grounding
                'source_type': 'report' if is_trusted_domain(final_url) else 'website',
            }
            
            # Enrich metadata for academic URLs
            if self._is_academic_url(final_url):
                enriched = self._enrich_metadata_from_url(final_url)
                if enriched and enriched.get('authors'):
                    # Use enriched metadata, keep original URL
                    enriched['url'] = final_url
                    valid_source = enriched

            valid_sources.append(valid_source)

        return valid_sources

    def _is_forbidden_domain(self, url: str) -> bool:
        """Check if URL is from forbidden domain."""
        try:
            domain = urlparse(url).netloc.lower()
            return any(
                forbidden in domain
                for forbidden in self.forbidden_domains
            )
        except Exception:
            return False

    def _unwrap_url(self, url: str) -> Optional[str]:
        """
        Follow redirects to get final destination URL.

        Args:
            url: Initial URL

        Returns:
            Final URL after redirects, or None if error
        """
        try:
            response = self.session.head(
                url,
                allow_redirects=True,
                timeout=self.timeout
            )
            return response.url
        except Exception:
            # Try GET if HEAD fails
            try:
                response = self.session.get(
                    url,
                    allow_redirects=True,
                    timeout=self.timeout,
                    stream=True
                )
                response.close()
                return response.url
            except Exception:
                return None

    def _validate_url(self, url: str) -> bool:
        """
        Validate URL returns HTTP 200.

        Args:
            url: URL to validate

        Returns:
            True if URL returns 200, False otherwise
        """
        try:
            response = self.session.head(
                url,
                allow_redirects=True,
                timeout=self.timeout
            )

            # Some servers block HEAD, try GET
            if response.status_code == 405:
                response = self.session.get(
                    url,
                    allow_redirects=True,
                    timeout=self.timeout,
                    stream=True
                )
                response.close()

            return response.status_code == 200

        except Exception:
            return False


    # =========================================================================
    # Academic URL Metadata Enrichment
    # =========================================================================
    
    def _is_academic_url(self, url: str) -> bool:
        """Check if URL is from an academic domain that can be enriched."""
        academic_domains = [
            # NCBI
            'pubmed.ncbi.nlm.nih.gov',
            'pmc.ncbi.nlm.nih.gov',
            # DOI resolver
            'doi.org',
            # Major publishers
            'mdpi.com',
            'springer.com',
            'nature.com',
            'academic.oup.com',
            'sciencedirect.com',
            'wiley.com',
            'tandfonline.com',
            'frontiersin.org',
            # Additional academic publishers
            'pubs.acs.org',  # American Chemical Society
            'researchgate.net',  # Has DOIs
            'cell.com',  # Cell Press
            'plos.org',  # PLOS journals
            'bmj.com',  # British Medical Journal
            'jamanetwork.com',  # JAMA
            'thelancet.com',  # Lancet
            'nejm.org',  # New England Journal of Medicine
            'arxiv.org',  # Preprints
            'biorxiv.org',  # Preprints
            'medrxiv.org',  # Preprints
            'journals.sagepub.com',  # SAGE
            'cambridge.org',  # Cambridge University Press
            'oxford.ac.uk',  # Oxford
            'ieee.org',  # IEEE
            'acm.org',  # ACM
            'aaai.org',  # AAAI
            'cureus.com',  # Cureus medical journal
        ]
        url_lower = url.lower()
        
        # Check known academic domains
        if any(domain in url_lower for domain in academic_domains):
            return True
        
        # Also check if URL contains a DOI pattern (10.xxxx/) - catches any academic site
        if re.search(r'10\.\d{4,}/', url_lower):
            return True
        
        return False
    
    def _enrich_metadata_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Enrich source metadata by extracting paper info from academic URLs.
        
        For PubMed/PMC: Extract PMID/PMCID and fetch via NCBI E-utilities
        For DOI URLs: Extract DOI and fetch via CrossRef
        For other academic sites: Extract DOI from URL if present
        """
        try:
            # PubMed: https://pubmed.ncbi.nlm.nih.gov/35058619/
            if 'pubmed.ncbi.nlm.nih.gov' in url:
                pmid = self._extract_pmid_from_url(url)
                if pmid:
                    return self._fetch_pubmed_metadata(pmid, url)
            
            # PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC12298131/
            if 'pmc.ncbi.nlm.nih.gov' in url:
                pmcid = self._extract_pmcid_from_url(url)
                if pmcid:
                    return self._fetch_pmc_metadata(pmcid, url)
            
            # DOI URLs: https://doi.org/10.xxxx/...
            if 'doi.org' in url:
                doi = self._extract_doi_from_doi_url(url)
                if doi:
                    return self._fetch_crossref_metadata(doi, url)
            
            # Academic sites with DOI in URL (MDPI, Springer, Nature, etc.)
            doi = self._extract_doi_from_academic_url(url)
            if doi:
                return self._fetch_crossref_metadata(doi, url)
            
        except Exception as e:
            safe_print(f"Metadata enrichment error for {url}: {e}")
        
        return None
    
    def _extract_pmid_from_url(self, url: str) -> Optional[str]:
        """Extract PMID from PubMed URL."""
        # https://pubmed.ncbi.nlm.nih.gov/35058619/
        match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
        return match.group(1) if match else None
    
    def _extract_pmcid_from_url(self, url: str) -> Optional[str]:
        """Extract PMCID from PMC URL."""
        # https://pmc.ncbi.nlm.nih.gov/articles/PMC12298131/
        match = re.search(r'PMC(\d+)', url)
        return match.group(1) if match else None
    
    def _extract_doi_from_doi_url(self, url: str) -> Optional[str]:
        """Extract DOI from doi.org URL."""
        # https://doi.org/10.1016/j.example.2023.001
        match = re.search(r'doi\.org/(10\.[^\s]+)', url)
        return match.group(1) if match else None
    
    def _extract_doi_from_academic_url(self, url: str) -> Optional[str]:
        """Extract DOI from academic publisher URLs."""
        # MDPI: https://www.mdpi.com/2227-9032/13/17/2154 -> 10.3390/healthcare13172154
        if 'mdpi.com' in url:
            match = re.search(r'mdpi\.com/([\d-]+)/(\d+)/(\d+)', url)
            if match:
                journal_id, vol, article = match.groups()
                # MDPI DOIs follow pattern: 10.3390/journalXXXXXXX
                return None  # Complex mapping, skip for now
        
        # Look for DOI in URL path
        match = re.search(r'(10\.\d{4,}/[^\s&?#]+)', url)
        return match.group(1) if match else None
    
    def _fetch_pubmed_metadata(self, pmid: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Fetch paper metadata from NCBI E-utilities using PMID."""
        try:
            api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "json"
            }
            response = self.session.get(api_url, params=params, timeout=10)
            if not response.ok:
                return None
            
            data = response.json()
            result = data.get('result', {}).get(pmid, {})
            
            if not result or 'error' in result:
                return None
            
            # Extract authors
            authors = result.get('authors', [])
            author_str = self._format_ncbi_authors(authors) if authors else None
            
            # Extract year from pubdate
            pubdate = result.get('pubdate', '')
            year = pubdate[:4] if pubdate and len(pubdate) >= 4 else None
            
            # Extract DOI from articleids
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
                'source_type': 'journal'
            }
        except Exception as e:
            safe_print(f"PubMed API error: {e}")
            return None
    
    def _fetch_pmc_metadata(self, pmcid: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Fetch paper metadata from NCBI E-utilities using PMCID."""
        try:
            # First get the PMID from PMCID
            api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pmc",
                "term": f"PMC{pmcid}[pmcid]",
                "retmode": "json"
            }
            response = self.session.get(api_url, params=params, timeout=10)
            if not response.ok:
                return None
            
            data = response.json()
            id_list = data.get('esearchresult', {}).get('idlist', [])
            
            if not id_list:
                return None
            
            # Now get summary using the pmc ID
            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {
                "db": "pmc",
                "id": id_list[0],
                "retmode": "json"
            }
            response = self.session.get(summary_url, params=params, timeout=10)
            if not response.ok:
                return None
            
            data = response.json()
            result = data.get('result', {}).get(id_list[0], {})
            
            if not result or 'error' in result:
                return None
            
            # Extract authors
            authors = result.get('authors', [])
            author_str = self._format_ncbi_authors(authors) if authors else None
            
            # Extract year
            pubdate = result.get('pubdate', '') or result.get('epubdate', '')
            year = pubdate[:4] if pubdate and len(pubdate) >= 4 else None
            
            # Extract DOI
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
                'source_type': 'journal'
            }
        except Exception as e:
            safe_print(f"PMC API error: {e}")
            return None
    
    def _fetch_crossref_metadata(self, doi: str, original_url: str) -> Optional[Dict[str, Any]]:
        """Fetch paper metadata from CrossRef using DOI."""
        try:
            api_url = f"https://api.crossref.org/works/{doi}"
            headers = {'User-Agent': 'AcademicDraftAI/1.0 (mailto:support@example.com)'}
            response = self.session.get(api_url, headers=headers, timeout=10)
            
            if not response.ok:
                return None
            
            data = response.json().get('message', {})
            
            if not data:
                return None
            
            # Extract title
            title_list = data.get('title', [])
            title = title_list[0] if title_list else None
            
            # Extract authors
            authors = data.get('author', [])
            author_str = self._format_crossref_authors(authors) if authors else None
            
            # Extract year
            year = None
            for date_field in ['published-print', 'published-online', 'created']:
                date_parts = data.get(date_field, {}).get('date-parts', [[]])
                if date_parts and date_parts[0]:
                    year = str(date_parts[0][0])
                    break
            
            # Extract journal
            container = data.get('container-title', [])
            journal = container[0] if container else None
            
            return {
                'title': title,
                'authors': author_str,
                'year': year,
                'doi': doi,
                'url': original_url,
                'journal': journal,
                'source_type': 'journal'
            }
        except Exception as e:
            safe_print(f"CrossRef API error: {e}")
            return None
    
    def _format_ncbi_authors(self, authors: list) -> Optional[str]:
        """Format NCBI author list to 'LastName et al.' format."""
        if not authors:
            return None
        
        # Get first author's last name
        first = authors[0]
        if isinstance(first, dict):
            name = first.get('name', '')
        else:
            name = str(first)
        
        # Extract last name (NCBI format: "LastName AB")
        parts = name.split()
        last_name = parts[0] if parts else name
        
        if len(authors) > 1:
            return f"{last_name} et al."
        return last_name
    
    def _format_crossref_authors(self, authors: list) -> Optional[str]:
        """Format CrossRef author list to 'LastName et al.' format."""
        if not authors:
            return None
        
        first = authors[0]
        last_name = first.get('family', first.get('name', 'Unknown'))
        
        if len(authors) > 1:
            return f"{last_name} et al."
        return last_name

    def close(self) -> None:
        """Close HTTP session."""
        if hasattr(self, 'session'):
            self.session.close()


# Backward-compatible alias while runtime shifts away from Gemini-specific naming.
WebSearchGroundedClient = GeminiGroundedClient
