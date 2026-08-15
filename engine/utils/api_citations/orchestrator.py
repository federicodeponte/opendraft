#!/usr/bin/env python3
"""
ABOUTME: Citation research orchestrator with intelligent fallback chain
ABOUTME: Discovers candidates across Crossref/OpenAlex/Semantic Scholar/web, then confirms each DOI in 2+ of them
"""

import logging
import json
import os
import sys
from typing import Optional, Dict, Any, Tuple, List, Callable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from pydantic import ValidationError

# Safe print function that handles broken pipes (worker runs with stdio: 'ignore')
def safe_print(*args, **kwargs):
    """Print wrapper that catches BrokenPipeError and respects verbosity settings."""
    # In quiet mode, suppress detailed research output
    if not _verbose_research:
        return

    try:
        print(*args, **kwargs)
    except (BrokenPipeError, OSError):
        # Pipe is closed (worker running with stdio: 'ignore'), use logger instead
        message = ' '.join(str(arg) for arg in args)
        logger.debug(message)
        # Prevent further broken pipe errors by redirecting stdout
        try:
            sys.stdout = open(os.devnull, 'w')
        except:
            pass

from .crossref import CrossrefClient
from .openalex import OpenAlexClient
from .semantic_scholar import SemanticScholarClient
from .gemini_grounded import GeminiGroundedClient
from .serper_client import SerperClient
from .query_router import QueryRouter, QueryClassification
from .base import validate_publication_year, validate_author_name
from .multi_source import (
    MultiSourceConfirmer,
    SCHOLARLY_SOURCES,
    VERIFICATION_LLM_UNVERIFIED,
    VERIFICATION_MULTI_SOURCE,
    VERIFICATION_NOT_CHECKED,
    VERIFICATION_SINGLE_SOURCE,
    VERIFICATION_WEB_SEARCH,
)

from ..models import strip_markdown_json, LLMCitationResponse

# =========================================================================
# Preprint Detection (Fix 3 from devil's advocate analysis)
# =========================================================================

# DOI prefixes that indicate preprints (not peer-reviewed)
PREPRINT_DOI_PREFIXES = [
    '10.2139/ssrn',       # SSRN
    '10.48550/arxiv',     # arXiv
    '10.1101/',           # bioRxiv/medRxiv
    '10.20944/preprints', # Preprints.org
    '10.31219/osf',       # OSF Preprints
    '10.21203/rs',        # Research Square
    '10.26434/chemrxiv',  # ChemRxiv
]

def is_preprint_doi(doi: str) -> bool:
    """Check if DOI indicates a preprint (not peer-reviewed)."""
    if not doi:
        return False
    doi_lower = doi.lower()
    return any(doi_lower.startswith(prefix) for prefix in PREPRINT_DOI_PREFIXES)

# Import existing Citation dataclass
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.citation_database import Citation

logger = logging.getLogger(__name__)

# Global verbose flag for CLI mode control
_verbose_research = True


def set_research_verbosity(verbose: bool) -> None:
    """Control verbosity of research output for CLI mode."""
    global _verbose_research
    _verbose_research = verbose


# =========================================================================
# Rate Limiting
# =========================================================================
class GeminiRateLimiter:
    """Simple rate limiter for Gemini API calls (free tier: ~60 req/min)."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0

    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit."""
        import time

        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()


# Global rate limiter instance
_gemini_rate_limiter = GeminiRateLimiter()


def get_gemini_rate_limiter() -> GeminiRateLimiter:
    """Get the global Gemini rate limiter instance."""
    return _gemini_rate_limiter


class CitationResearcher:
    """
    Finds candidate citations, then confirms them across scholarly databases.

    Two distinct stages, which earlier versions of this docstring conflated:

    STAGE 1 - DISCOVERY (a fallback/routing chain).
    Locates candidate works. Any one source can satisfy this stage; that is the
    point of a fallback chain. Discovery alone establishes nothing about
    whether a work is real.

    Smart routing (default):
    - Industry queries → Gemini Grounded → Semantic Scholar → Crossref
    - Academic queries → Crossref → Semantic Scholar → Gemini Grounded
    - Mixed queries → Semantic Scholar → Gemini Grounded → Crossref

    Classic chain (smart routing disabled):
    1. Crossref, 2. OpenAlex, 3. Semantic Scholar, 4. Gemini Grounded,
    5. Gemini LLM (opt-in only; see below).

    STAGE 2 - CONFIRMATION (default: on, and strict).
    Each candidate carrying a DOI is looked up by DOI in each of the three
    scholarly databases (Crossref, OpenAlex, Semantic Scholar) via
    MultiSourceConfirmer. With require_multi_source=True (the default), a
    candidate is kept only if at least min_confirming_sources (default 2)
    distinct databases hold that DOI. Single-source candidates are dropped.

    Set require_multi_source=False to opt out and accept first-responder
    results. That is an explicit opt-out, not the default.

    What confirmation does and does not mean:
    - It means: that DOI is registered and indexed in N scholarly databases.
    - It does NOT mean the work supports any particular claim. Claim-level
      semantic checking is CitationClaimVerifier's job, not this class's.
    - The three databases are not fully independent. OpenAlex and Semantic
      Scholar both ingest Crossref metadata, so agreement is evidence of
      registration and indexing, not three separately sourced attestations.

    SOURCES THAT CANNOT BE CONFIRMED THIS WAY.
    - Web search (Gemini Grounded / Serper) usually returns sources with no
      DOI (industry reports, agency pages). Scholarly databases cannot be
      queried for them, so they are tagged VERIFICATION_WEB_SEARCH and, under
      the strict default, dropped. Set allow_unconfirmed_web_sources=True to
      keep them; they stay tagged so a reader can see they were not confirmed.
    - Gemini LLM last resort asserts a citation with no external lookup at all.
      It is DISABLED by default (enable_llm_fallback=False) and must be turned
      on deliberately. Anything it produces is tagged
      VERIFICATION_LLM_UNVERIFIED and is never presented like a confirmed
      citation.

    Every returned Citation carries verification_status, verification_sources
    and verification_notes, which persist into bibliography.json.
    """

    # Persistent cache file path
    CACHE_FILE = Path(".citation_cache_orchestrator.json")

    def __init__(
        self,
        gemini_model: Optional[Any] = None,
        enable_crossref: bool = True,
        enable_openalex: bool = True,
        enable_semantic_scholar: bool = True,
        enable_gemini_grounded: bool = True,
        enable_llm_fallback: bool = False,
        enable_smart_routing: bool = True,
        use_serper: bool = None,  # None = auto-detect from env
        require_multi_source: bool = True,
        min_confirming_sources: int = 2,
        allow_unconfirmed_web_sources: bool = False,
        verbose: bool = True,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize Citation Researcher.

        Args:
            gemini_model: Gemini model for LLM fallback (optional)
            enable_crossref: Whether to use Crossref API
            enable_openalex: Whether to use OpenAlex API (250M+ works)
            enable_semantic_scholar: Whether to use Semantic Scholar API
            enable_gemini_grounded: Whether to use Gemini with Google Search grounding (includes DataForSEO fallback)
            enable_llm_fallback: Whether to let the LLM assert a citation when
                every lookup fails. DEFAULT False. Nothing external checks an
                LLM assertion, so this is opt-in and its output is always
                tagged VERIFICATION_LLM_UNVERIFIED.
            enable_smart_routing: Whether to use smart query routing (default: True)
            use_serper: Whether to use Serper.dev instead of Gemini Grounded for web search
            require_multi_source: Whether a citation must be held by at least
                min_confirming_sources scholarly databases to be kept.
                DEFAULT True. Set False to opt out and accept first-responder
                (single-source) results.
            min_confirming_sources: How many of {Crossref, OpenAlex, Semantic
                Scholar} must hold the DOI (default 2). Only meaningful when
                require_multi_source is True.
            allow_unconfirmed_web_sources: Whether to keep DOI-less web-search
                results, which no scholarly database can confirm. DEFAULT
                False. When True they are kept but stay tagged
                VERIFICATION_WEB_SEARCH.
            verbose: Whether to print progress
            progress_callback: Optional callback(message, event_type) for progress reporting
        """
        self.gemini_model = gemini_model
        self.progress_callback = progress_callback
        self.enable_crossref = enable_crossref
        self.enable_openalex = enable_openalex
        self.enable_semantic_scholar = enable_semantic_scholar
        self.enable_gemini_grounded = enable_gemini_grounded
        self.enable_llm_fallback = enable_llm_fallback and gemini_model is not None
        self.enable_smart_routing = enable_smart_routing
        self.require_multi_source = require_multi_source
        self.min_confirming_sources = min_confirming_sources
        self.allow_unconfirmed_web_sources = allow_unconfirmed_web_sources
        # Auto-detect Serper from env if not explicitly set
        if use_serper is None:
            self.use_serper = os.getenv('USE_SERPER', 'false').lower() == 'true'
        else:
            self.use_serper = use_serper
        self.verbose = verbose

        # Initialize API clients
        if self.enable_crossref:
            self.crossref = CrossrefClient()
        if self.enable_openalex:
            self.openalex = OpenAlexClient()
        if self.enable_semantic_scholar:
            self.semantic_scholar = SemanticScholarClient()

        # Web search client: Serper (preferred) or Gemini Grounded (fallback)
        if self.enable_gemini_grounded:
            if self.use_serper:
                try:
                    self.gemini_grounded = SerperClient(
                        validate_urls=False,  # Disable URL validation for speed
                        timeout=15,
                    )
                    logger.info("Using Serper.dev for web search (replaces Gemini Grounded)")
                except Exception as e:
                    logger.warning(f"Serper client unavailable: {e}, falling back to Gemini Grounded")
                    self.use_serper = False
                    self._init_gemini_grounded()
            else:
                self._init_gemini_grounded()

        # Initialize smart query router
        if self.enable_smart_routing:
            self.query_router = QueryRouter()

        # Multi-source confirmation across the scholarly databases that are
        # actually enabled. Built from the same client instances used for
        # discovery, so no extra sessions are created.
        self.confirmer = MultiSourceConfirmer(
            crossref_client=getattr(self, "crossref", None),
            openalex_client=getattr(self, "openalex", None),
            semantic_scholar_client=getattr(self, "semantic_scholar", None),
            min_confirming_sources=self.min_confirming_sources,
        )

        # Requiring more confirmations than there are enabled databases would
        # reject every citation. That is a misconfiguration, not a finding, so
        # fail loudly at construction rather than silently returning nothing.
        if self.require_multi_source and not self.confirmer.can_reach_threshold:
            raise ValueError(
                f"require_multi_source=True needs at least {self.min_confirming_sources} "
                f"scholarly databases enabled, but only {len(self.confirmer.available_sources)} "
                f"are ({', '.join(self.confirmer.available_sources) or 'none'}). "
                f"Enable more of Crossref/OpenAlex/Semantic Scholar, lower "
                f"min_confirming_sources, or set require_multi_source=False."
            )

        # Load persistent cache (or initialize empty if file doesn't exist)
        self.cache: Dict[str, Optional[Tuple[Dict[str, Any], str]]] = self._load_cache()

        # Track source usage for round-robin variety (reset each session)
        self.source_usage_count: Dict[str, int] = {
            "Crossref": 0,
            "OpenAlex": 0,
            "Semantic Scholar": 0,
            "Gemini Grounded": 0,
            "Serper": 0,
        }

    def _init_gemini_grounded(self):
        """Initialize Gemini Grounded client."""
        try:
            self.gemini_grounded = GeminiGroundedClient(
                validate_urls=False,  # Disable URL validation to prevent timeouts
                timeout=30  # Reduced timeout for fast gemini-2.5-flash
            )
        except Exception as e:
            logger.warning(f"Gemini Grounded client unavailable: {e}")
            self.enable_gemini_grounded = False

    def _report_progress(self, message: str, event_type: str = "search") -> None:
        """Report progress to callback if available."""
        if self.progress_callback:
            try:
                self.progress_callback(message, event_type)
            except Exception as e:
                logger.debug(f"Progress callback error: {e}")

    def _load_cache(self) -> Dict[str, Optional[Tuple[Dict[str, Any], str]]]:
        """
        Load citation cache from disk.

        Returns:
            Dict mapping topics to (metadata, source) tuples, list of tuples, or None
        """
        if not self.CACHE_FILE.exists():
            logger.info(f"No existing cache file found at {self.CACHE_FILE}")
            return {}

        try:
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            logger.info(f"Loaded {len(cache_data)} cached citations from {self.CACHE_FILE}")

            # Convert JSON back to cache format
            cache = {}
            for topic, value in cache_data.items():
                if value is None:
                    cache[topic] = None
                elif isinstance(value, list) and len(value) == 2 and isinstance(value[0], dict):
                    # Old format: [metadata_dict, source_string] - single citation
                    cache[topic] = (value[0], value[1])
                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], list):
                    # New format: [[metadata1, source1], [metadata2, source2], ...] - multiple citations
                    cache[topic] = [(item[0], item[1]) for item in value]
                else:
                    # Fallback for unexpected format
                    cache[topic] = (value[0], value[1]) if isinstance(value, list) and len(value) >= 2 else None

            return cache
        except Exception as e:
            logger.warning(f"Failed to load cache from {self.CACHE_FILE}: {e}")
            return {}

    def _save_cache(self) -> None:
        """
        Save citation cache to disk.

        Persists the in-memory cache to a JSON file for reuse across runs.
        """
        try:
            # Convert cache to JSON-serializable format
            cache_data = {}
            for topic, value in self.cache.items():
                if value is None:
                    cache_data[topic] = None
                elif isinstance(value, list):
                    if len(value) == 0:
                        # Empty list - treat as no results
                        cache_data[topic] = None
                    elif isinstance(value[0], tuple):
                        # List of (metadata, source) tuples - convert to list of [metadata, source] lists
                        cache_data[topic] = [[metadata, source] for metadata, source in value]
                    else:
                        # Unexpected format - skip
                        logger.warning(f"Unexpected cache format for topic '{topic}': {type(value[0])}")
                        cache_data[topic] = None
                elif isinstance(value, tuple) and len(value) == 2:
                    # Single (metadata, source) tuple - for backward compatibility
                    metadata, source = value
                    cache_data[topic] = [metadata, source]
                else:
                    # Unexpected format - skip
                    logger.warning(f"Unexpected cache format for topic '{topic}': {type(value)}")
                    cache_data[topic] = None

            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved {len(cache_data)} citations to cache file {self.CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save cache to {self.CACHE_FILE}: {e}")

    def research_citation(self, topic: str) -> List[Citation]:
        """
        Research citations using parallel API calls.

        Args:
            topic: Topic or description to research

        Returns:
            List of Citation objects (may be empty if none found)
        """
        # Check cache first
        if topic in self.cache:
            cached = self.cache[topic]
            if cached is None:
                return []
            # Cache may store either single tuple or list of tuples
            if isinstance(cached, list):
                # List of (metadata, source) tuples
                cached_list = cached
            else:
                # Single (metadata, source) tuple - convert to list
                cached_list = [cached]

            # Verify cache hits too. A cache file written before verification
            # existed carries no verification_status, and must not be allowed
            # to bypass the current strictness settings.
            verified_cached = self._verify_results(cached_list)
            if len(verified_cached) != len(cached_list):
                # Persist the verdicts so the same entries are not re-checked
                # on every run.
                self.cache[topic] = verified_cached if verified_cached else None
                self._save_cache()

            citations = []
            for cached_metadata, cached_source in verified_cached:
                if self.verbose:
                    safe_print(
                        f"    ✓ Cached: {cached_metadata.get('authors', ['Unknown'])[0] if cached_metadata.get('authors') else 'Unknown'} et al. ({cached_metadata.get('year', 'n.d.')}) [from {cached_source}]"
                    )
                citation = self._create_citation(cached_metadata, cached_source)
                if citation:
                    citations.append(citation)
            return citations


        if self.verbose:
                    safe_print(f"  🔍 Researching: {topic[:70]}{'...' if len(topic) > 70 else ''}")

        # Classify query and determine API chain
        api_chain = None
        if self.enable_smart_routing:
            classification = self.query_router.classify_and_route(topic)
            api_chain = classification.api_chain
            if self.verbose:
                safe_print(f"    📊 Query type: {classification.query_type} (confidence: {classification.confidence:.2f})")
        else:
            # Use original fallback chain if smart routing disabled
            api_chain = ['crossref', 'openalex', 'semantic_scholar', 'gemini_grounded']

        # Filter out disabled APIs from chain (Day 1 Fix)
        enabled_chain = []
        for api_name in api_chain:
            if api_name == 'crossref' and not self.enable_crossref:
                continue
            if api_name == 'openalex' and not self.enable_openalex:
                continue
            if api_name == 'semantic_scholar' and not self.enable_semantic_scholar:
                continue
            if api_name == 'gemini_grounded' and not self.enable_gemini_grounded:
                continue
            enabled_chain.append(api_name)

        api_chain = enabled_chain

        if self.verbose and api_chain:
            safe_print(f"    🔀 API chain: {' → '.join(api_chain)}")


        # Collect ALL valid results from API chain
        valid_results: List[Tuple[Dict[str, Any], str]] = []


        # Determine if we should use parallel queries
        # Use parallel for academic/journal queries where multiple academic APIs are in chain
        use_parallel = (
            'crossref' in api_chain
            and ('openalex' in api_chain or 'semantic_scholar' in api_chain)
            and self.enable_crossref
        )

        if use_parallel:
            # Query ALL academic APIs in parallel for maximum source diversity
            parallel_apis = ['crossref']
            if self.enable_openalex:
                parallel_apis.append('openalex')
            if self.enable_semantic_scholar:
                parallel_apis.append('semantic_scholar')
            if self.enable_gemini_grounded:
                parallel_apis.append('gemini_grounded')


            # Report progress for parallel search
            self._report_progress("Querying academic APIs in parallel...", "search")

            if self.verbose:
                apis_str = " + ".join([a.replace("_", " ").title() for a in parallel_apis])
                safe_print(f"    → Querying {apis_str} in parallel...", end=" ", flush=True)
            results: List[Tuple[Optional[Dict[str, Any]], str]] = []

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(self._search_api, api, topic): api
                    for api in parallel_apis
                }
                try:
                    for future in as_completed(futures, timeout=30):  # 30s timeout - balanced for Gemini
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            api = futures[future]
                            logger.debug(f"Parallel {api} error: {e}")
                            results.append((None, api))
                except (TimeoutError, FuturesTimeoutError):
                    # Graceful degradation: use whatever results we have
                    logger.warning(f"Parallel query timeout - {len(results)} of {len(futures)} APIs responded")
                    # Collect any completed futures
                    for future, api in futures.items():
                        if future.done():
                            try:
                                result = future.result(timeout=0)
                                if result not in results:
                                    results.append(result)
                            except Exception:
                                pass

            # Collect ALL valid results (not just best one)
            for result_metadata, result_source in results:
                if result_metadata and (result_metadata.get('doi') or result_metadata.get('url')):
                    valid_results.append((result_metadata, result_source))
                    # Update source usage count for logging
                    self.source_usage_count[result_source] = self.source_usage_count.get(result_source, 0) + 1


            if valid_results:
                if self.verbose:
                    sources_str = ", ".join([src for _, src in valid_results])
                    safe_print(f"✓ ({sources_str})")
            else:
                if self.verbose:
                    safe_print(f"✗")
        else:
            # Sequential fallback for industry queries or when parallel not applicable
            for api_name in api_chain:
                if api_name == 'crossref' and self.enable_crossref:
                    self._report_progress("Querying Crossref for peer-reviewed papers...", "search")
                    if self.verbose:
                        safe_print(f"    → Trying Crossref API...", end=" ", flush=True)
                    try:
                        metadata = self.crossref.search_paper(topic)
                        if metadata and (metadata.get('doi') or metadata.get('url')):
                            valid_results.append((metadata, "Crossref"))
                            self.source_usage_count["Crossref"] = self.source_usage_count.get("Crossref", 0) + 1
                            if self.verbose:
                                safe_print(f"✓")
                        else:
                            if self.verbose:
                                safe_print(f"✗")
                    except Exception as e:
                        if self.verbose:
                            safe_print(f"✗ Error: {e}")
                        logger.error(f"Crossref error: {e}")

                elif api_name == 'openalex' and self.enable_openalex:
                    self._report_progress("Searching OpenAlex (250M+ works)...", "search")
                    if self.verbose:
                        safe_print(f"    → Trying OpenAlex API...", end=" ", flush=True)
                    try:
                        metadata = self.openalex.search_paper(topic)
                        if metadata and (metadata.get('doi') or metadata.get('url')):
                            valid_results.append((metadata, "OpenAlex"))
                            self.source_usage_count["OpenAlex"] = self.source_usage_count.get("OpenAlex", 0) + 1
                            if self.verbose:
                                safe_print(f"✓")
                        else:
                            if self.verbose:
                                safe_print(f"✗")
                    except Exception as e:
                        if self.verbose:
                            safe_print(f"✗ Error: {e}")
                        logger.error(f"OpenAlex error: {e}")

                elif api_name == 'semantic_scholar' and self.enable_semantic_scholar:
                    self._report_progress("Searching Semantic Scholar (200M+ papers)...", "search")
                    if self.verbose:
                        safe_print(f"    → Trying Semantic Scholar API...", end=" ", flush=True)
                    try:
                        metadata = self.semantic_scholar.search_paper(topic)
                        if metadata and (metadata.get('doi') or metadata.get('url')):
                            valid_results.append((metadata, "Semantic Scholar"))
                            self.source_usage_count["Semantic Scholar"] = self.source_usage_count.get("Semantic Scholar", 0) + 1
                            if self.verbose:
                                safe_print(f"✓")
                        else:
                            if self.verbose:
                                safe_print(f"✗")
                    except Exception as e:
                        if self.verbose:
                            safe_print(f"✗ Error: {e}")
                        logger.error(f"Semantic Scholar error: {e}")

                elif api_name == 'gemini_grounded' and self.enable_gemini_grounded:
                    self._report_progress("AI-powered academic search...", "search")
                    if self.verbose:
                        search_name = "Serper" if self.use_serper else "Gemini Grounded (Google Search)"
                        safe_print(f"    → Trying {search_name}...", end=" ", flush=True)
                    try:
                        metadata = self.gemini_grounded.search_paper(topic)
                        if metadata and (metadata.get('doi') or metadata.get('url')):
                            source_name = "Serper" if self.use_serper else "Gemini Grounded"
                            valid_results.append((metadata, source_name))
                            self.source_usage_count[source_name] = self.source_usage_count.get(source_name, 0) + 1
                            if self.verbose:
                                safe_print(f"✓")
                        else:
                            if self.verbose:
                                safe_print(f"✗")
                    except Exception as e:
                        if self.verbose:
                            safe_print(f"✗ Error: {e}")
                        logger.error(f"Gemini Grounded error: {e}")

        # Try Gemini LLM as absolute last resort (not part of smart routing).
        # Disabled by default: nothing external checks what the LLM asserts.
        # Anything produced here is tagged VERIFICATION_LLM_UNVERIFIED below.
        if not valid_results and self.enable_llm_fallback:
            if self.verbose:
                safe_print(f"    → Trying Gemini LLM fallback (UNVERIFIED)...", end=" ", flush=True)
            try:
                metadata = self._llm_research(topic)
                if metadata and (metadata.get('doi') or metadata.get('url')):
                    valid_results.append((metadata, "Gemini LLM"))
                    if self.verbose:
                        safe_print(f"✓")
                else:
                    if self.verbose:
                        safe_print(f"✗")
            except Exception as e:
                if self.verbose:
                    safe_print(f"✗ Error: {e}")
                logger.error(f"Gemini LLM error: {e}")

        # STAGE 2: confirm each candidate across the scholarly databases and
        # drop whatever does not meet the configured strictness. Runs before
        # caching so the cache stores verdicts, not raw first-responder hits.
        valid_results = self._verify_results(valid_results)

        # Cache results (even if empty list)
        if valid_results:
            self.cache[topic] = valid_results
        else:
            self.cache[topic] = None

        # Persist cache to disk
        self._save_cache()

        # Convert to Citation objects
        citations = []
        if valid_results:
            for metadata, source in valid_results:
                citation = self._create_citation(metadata, source)
                if citation:
                    citations.append(citation)
                    if self.verbose:
                        # Check if preprint and show visible marker (Fix 3)
                        preprint_marker = " ⚠️ [PREPRINT]" if citation.source_type == "preprint" else ""
                        safe_print(f"    ✓ Found: {citation.authors[0]} et al. ({citation.year}) [from {source}]{preprint_marker}")
                        if citation.doi:
                            safe_print(f"      DOI: {citation.doi}")
                        elif citation.url:
                            safe_print(f"      URL: {citation.url}")

        if not citations and self.verbose:
            safe_print(f"    ✗ No citations found for: {topic[:70]}...")

        return citations

    def _tag_verification(self, metadata: Dict[str, Any], source: Optional[str]) -> None:
        """
        Record on the metadata how this candidate was established.

        Mutates metadata in place, adding verification_status,
        verification_sources and verification_notes. Idempotent: a candidate
        that already carries a status (for example one restored from the
        on-disk cache) is left alone.

        Network lookups only happen when require_multi_source is True. When the
        caller has opted out, DOI-bearing candidates are tagged
        VERIFICATION_NOT_CHECKED rather than being described as confirmed,
        because in that mode nothing checked them.
        """
        if metadata.get("verification_status"):
            return

        if source == "Gemini LLM":
            # No external lookup happened at any point for this candidate.
            metadata["verification_status"] = VERIFICATION_LLM_UNVERIFIED
            metadata["verification_sources"] = []
            metadata["verification_notes"] = (
                "Asserted by the LLM with no external lookup. No database was queried "
                "and nothing confirmed that this work exists."
            )
            return

        if not self.require_multi_source:
            has_doi = bool(metadata.get("doi"))
            metadata["verification_status"] = (
                VERIFICATION_NOT_CHECKED if has_doi else VERIFICATION_WEB_SEARCH
            )
            metadata["verification_sources"] = []
            metadata["verification_notes"] = (
                f"Returned by {source or 'an unnamed source'}. Multi-source confirmation "
                f"was disabled (require_multi_source=False), so no second database was "
                f"queried for this record."
            )
            return

        result = self.confirmer.confirm(metadata, found_by=source)
        metadata["verification_status"] = result.status
        metadata["verification_sources"] = list(result.confirming_sources)
        metadata["verification_notes"] = result.notes

    def _keep_after_verification(self, metadata: Dict[str, Any], source: Optional[str]) -> bool:
        """
        Decide whether a tagged candidate survives the current strictness settings.

        Returns True to keep. Logs the reason whenever a candidate is dropped,
        so a dropped citation is never silently invisible.
        """
        status = metadata.get("verification_status")
        title = str(metadata.get("title", ""))[:70]

        if status == VERIFICATION_MULTI_SOURCE:
            return True

        if status == VERIFICATION_LLM_UNVERIFIED:
            # Multi-source confirmation cannot apply here: there is no DOI to
            # look up and no database claims the work. The operator turned
            # enable_llm_fallback on deliberately, so dropping it here would
            # make that flag do nothing. It is kept and permanently tagged
            # instead; the tag is the safeguard, not removal.
            logger.warning(
                f"Keeping LLM-asserted, UNVERIFIED citation '{title}' "
                f"(enable_llm_fallback=True). Tagged {VERIFICATION_LLM_UNVERIFIED}."
            )
            return True

        if status == VERIFICATION_WEB_SEARCH:
            if self.allow_unconfirmed_web_sources or not self.require_multi_source:
                return True
            logger.info(
                f"Dropping web source '{title}' from {source}: no DOI, so no scholarly "
                f"database can confirm it. Set allow_unconfirmed_web_sources=True to keep it."
            )
            return False

        if status == VERIFICATION_NOT_CHECKED:
            # Only reachable when require_multi_source is False.
            return True

        # VERIFICATION_SINGLE_SOURCE
        if self.require_multi_source:
            logger.info(
                f"Dropping single-source citation '{title}': held by "
                f"{len(metadata.get('verification_sources') or [])} scholarly database(s), "
                f"needs {self.min_confirming_sources}. "
                f"{metadata.get('verification_notes', '')}"
            )
            return False
        return True

    def _verify_results(
        self,
        valid_results: List[Tuple[Dict[str, Any], str]],
    ) -> List[Tuple[Dict[str, Any], str]]:
        """
        Tag every candidate with its verification provenance, then filter.

        Runs on freshly discovered results AND on results restored from the
        on-disk cache, so a cache entry written before verification existed
        cannot bypass the current strictness settings.
        """
        kept: List[Tuple[Dict[str, Any], str]] = []
        for metadata, source in valid_results:
            if not isinstance(metadata, dict):
                continue
            self._tag_verification(metadata, source)
            if self._keep_after_verification(metadata, source):
                kept.append((metadata, source))

        if self.verbose and len(kept) != len(valid_results):
            dropped = len(valid_results) - len(kept)
            safe_print(
                f"    🔒 Verification: kept {len(kept)}, dropped {dropped} "
                f"(need {self.min_confirming_sources} of {', '.join(SCHOLARLY_SOURCES)})"
            )

        return kept

    def _create_citation(self, metadata: Dict[str, Any], source: Optional[str] = None) -> Optional[Citation]:
        """
        Create Citation object from metadata.

        Args:
            metadata: Paper metadata from API or LLM
            source: API source that found this citation (Crossref, Semantic Scholar, etc.)

        Returns:
            Citation object or None if validation fails
        """
        try:
            # Validate required fields
            # For web sources (Gemini Grounded), only title and URL are required
            # Academic sources need authors and year
            is_web_source = source == "Gemini Grounded" or metadata.get("source_type") == "website"

            if is_web_source:
                # Web sources: require title + (URL or DOI)
                if not metadata.get("title"):
                    logger.debug(f"Invalid web source: missing title")
                    return None
                if not metadata.get("url") and not metadata.get("doi"):
                    logger.debug(f"Invalid web source: missing URL/DOI")
                    return None
                # Fill in missing academic fields for web sources
                if not metadata.get("authors"):
                    # Extract organization name for web sources (better than domain)
                    url = metadata.get("url", "")
                    if url:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc.lower().replace('www.', '')
                        
                        # Map known domains to proper organization names
                        DOMAIN_TO_ORG = {
                            # Consulting firms
                            'mckinsey.com': 'McKinsey & Company',
                            'bcg.com': 'Boston Consulting Group',
                            'bain.com': 'Bain & Company',
                            'deloitte.com': 'Deloitte',
                            'pwc.com': 'PwC',
                            'kpmg.com': 'KPMG',
                            'ey.com': 'Ernst & Young',
                            'accenture.com': 'Accenture',
                            # Industry analysts
                            'gartner.com': 'Gartner',
                            'forrester.com': 'Forrester',
                            'idc.com': 'IDC',
                            'statista.com': 'Statista',
                            # International organizations
                            'who.int': 'World Health Organization',
                            'oecd.org': 'OECD',
                            'worldbank.org': 'World Bank',
                            'un.org': 'United Nations',
                            'imf.org': 'IMF',
                            'wto.org': 'World Trade Organization',
                            'unesco.org': 'UNESCO',
                            # US Government agencies
                            'nist.gov': 'NIST',
                            'nih.gov': 'NIH',
                            'cdc.gov': 'CDC',
                            'fda.gov': 'FDA',
                            'epa.gov': 'EPA',
                            'nasa.gov': 'NASA',
                            'nsf.gov': 'NSF',
                            'energy.gov': 'U.S. Department of Energy',
                            'state.gov': 'U.S. Department of State',
                            'whitehouse.gov': 'White House',
                            'congress.gov': 'U.S. Congress',
                            'gao.gov': 'GAO',
                            'cbo.gov': 'CBO',
                            # EU institutions
                            'europa.eu': 'European Commission',
                            'europarl.europa.eu': 'European Parliament',
                            'ecb.europa.eu': 'European Central Bank',
                            # Think tanks & research institutes
                            'brookings.edu': 'Brookings Institution',
                            'rand.org': 'RAND Corporation',
                            'cfr.org': 'Council on Foreign Relations',
                            'carnegieendowment.org': 'Carnegie Endowment',
                            'csis.org': 'CSIS',
                            'heritage.org': 'Heritage Foundation',
                            'aei.org': 'American Enterprise Institute',
                            'pewresearch.org': 'Pew Research Center',
                            'urban.org': 'Urban Institute',
                            'cato.org': 'Cato Institute',
                            # AI research centers
                            'cset.georgetown.edu': 'Georgetown CSET',
                            'hai.stanford.edu': 'Stanford HAI',
                            'ainowinstitute.org': 'AI Now Institute',
                            # Top universities (research centers)
                            'mit.edu': 'MIT',
                            'stanford.edu': 'Stanford University',
                            'harvard.edu': 'Harvard University',
                            'berkeley.edu': 'UC Berkeley',
                            'ox.ac.uk': 'University of Oxford',
                            'cam.ac.uk': 'University of Cambridge',
                            'princeton.edu': 'Princeton University',
                            'yale.edu': 'Yale University',
                            'columbia.edu': 'Columbia University',
                            'cmu.edu': 'Carnegie Mellon University',
                            # News & journalism
                            'reuters.com': 'Reuters',
                            'bbc.com': 'BBC',
                            'nytimes.com': 'New York Times',
                            'ft.com': 'Financial Times',
                            'economist.com': 'The Economist',
                            'wsj.com': 'Wall Street Journal',
                            # Tech giants (official research)
                            'openai.com': 'OpenAI',
                            'deepmind.com': 'DeepMind',
                            'anthropic.com': 'Anthropic',
                            'research.google': 'Google Research',
                            'ai.google': 'Google AI',
                            'research.microsoft.com': 'Microsoft Research',
                            'research.ibm.com': 'IBM Research',
                            'research.facebook.com': 'Meta AI',
                        }
                        
                        # Try exact match first, then suffix match for subdomains
                        org_name = DOMAIN_TO_ORG.get(domain)
                        if not org_name:
                            # Suffix match: energy.ec.europa.eu -> europa.eu -> European Commission
                            for known_domain, org in DOMAIN_TO_ORG.items():
                                if domain.endswith('.' + known_domain) or domain == known_domain:
                                    org_name = org
                                    break
                        
                        if org_name:
                            metadata["authors"] = [org_name]
                        else:
                            # REJECT unknown domains - don't use domain as author
                            # This prevents "issuu.com et al." citations
                            logger.debug(f"Rejecting web source: unknown org for domain '{domain}'")
                            return None
                    else:
                        metadata["authors"] = ["Web Source"]
                if not metadata.get("year"):
                    # Use current year for undated web sources
                    from datetime import datetime
                    metadata["year"] = datetime.now().year
            else:
                # Academic sources: require title + authors + year
                if not metadata.get("title") or not metadata.get("authors") or not metadata.get("year"):
                    logger.debug(f"Invalid metadata: missing required fields")
                    return None

            # Fix 4: Validate publication year
            year = metadata.get("year")
            if year:
                is_valid_year, year_reason, is_recent = validate_publication_year(year)
                if not is_valid_year:
                    logger.debug(f"Rejecting citation: invalid year {year} ({year_reason})")
                    return None
            
            # Fix 7: Validate author names for ALL sources (catches single-letter and generic names)
            authors = metadata.get("authors", [])
            if authors:
                first_author = authors[0] if authors else ""
                is_valid_author, author_reason = validate_author_name(first_author)
                if not is_valid_author:
                    logger.debug(f"Rejecting citation: invalid author '{first_author}' ({author_reason})")
                    return None
            
            # Check if this is a preprint (Fix 3)
            doi = metadata.get("doi", "")
            is_preprint = is_preprint_doi(doi)
            
            # Determine source_type (preprint overrides other types)
            source_type = metadata.get("source_type", "website")
            if is_preprint:
                source_type = "preprint"
            
            # Extract abstract/snippet (Gemini returns "snippet", others return "abstract")
            abstract = metadata.get("abstract") or metadata.get("snippet")

            citation = Citation(
                citation_id="temp_id",  # Will be assigned by CitationCompiler
                authors=metadata["authors"],
                year=int(metadata["year"]),
                title=metadata["title"],
                source_type=source_type,
                language="english",  # Assume English for API results
                journal=metadata.get("journal", ""),
                publisher=metadata.get("publisher", ""),
                volume=metadata.get("volume"),
                issue=metadata.get("issue"),
                pages=metadata.get("pages", ""),
                doi=doi,
                url=metadata.get("url", ""),
                api_source=source,  # Track which API found this citation
                abstract=abstract,  # Include abstract from API responses
                citation_count=metadata.get("citation_count"),
                # Verification provenance travels with the citation into
                # bibliography.json so a reader can always tell a
                # database-confirmed citation from an unconfirmed one.
                verification_status=metadata.get("verification_status"),
                verification_sources=metadata.get("verification_sources"),
                verification_notes=metadata.get("verification_notes"),
            )

            return citation

        except Exception as e:
            logger.error(f"Error creating citation: {e}")
            return None
    def _search_api(self, api_name: str, topic: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Search a single API for citations.

        Args:
            api_name: Name of the API ('crossref', 'openalex', 'semantic_scholar', 'gemini_grounded')
            topic: Topic to search for

        Returns:
            Tuple of (metadata, source_name) or (None, api_name)
        """
        try:
            logger.info(f"🔍 [{api_name.upper()}] Starting search for: {topic[:80]}...")

            if api_name == 'crossref' and self.enable_crossref:
                logger.debug(f"  → Calling Crossref API...")
                metadata = self.crossref.search_paper(topic)
                if metadata:
                    logger.info(
                        f"  ✓ Crossref found: {metadata.get('title', 'Unknown')[:80]}... (DOI: {metadata.get('doi', 'N/A')})"
                    )
                    return (metadata, "Crossref")
                else:
                    logger.debug(f"  ✗ Crossref returned no results")
            elif api_name == 'openalex' and self.enable_openalex:
                logger.debug(f"  → Calling OpenAlex API...")
                metadata = self.openalex.search_paper(topic)
                if metadata:
                    logger.info(
                        f"  ✓ OpenAlex found: {metadata.get('title', 'Unknown')[:80]}... (DOI: {metadata.get('doi', 'N/A')})"
                    )
                    return (metadata, "OpenAlex")
                else:
                    logger.debug(f"  ✗ OpenAlex returned no results")
            elif api_name == 'semantic_scholar' and self.enable_semantic_scholar:
                logger.debug(f"  → Calling Semantic Scholar API...")
                metadata = self.semantic_scholar.search_paper(topic)
                if metadata:
                    logger.info(
                        f"  ✓ Semantic Scholar found: {metadata.get('title', 'Unknown')[:80]}... (DOI: {metadata.get('doi', 'N/A')})"
                    )
                    return (metadata, "Semantic Scholar")
                else:
                    logger.debug(f"  ✗ Semantic Scholar returned no results")
            elif api_name == 'gemini_grounded' and self.enable_gemini_grounded:
                logger.debug(f"  → Applying rate limiting before Gemini Grounded call...")
                rate_limiter = get_gemini_rate_limiter()
                rate_limiter.wait_if_needed()
                logger.debug(f"  → Calling Gemini Grounded API...")
                metadata = self.gemini_grounded.search_paper(topic)
                if metadata:
                    logger.info(
                        f"  ✓ Gemini Grounded found: {metadata.get('title', 'Unknown')[:80]}... (URL: {metadata.get('url', 'N/A')[:50]})"
                    )
                    source_name = "Serper" if self.use_serper else "Gemini Grounded"
                    return (metadata, source_name)
                else:
                    logger.debug(f"  ✗ Gemini Grounded returned no results")

            return (None, api_name)

        except Exception as e:
            logger.error(
                f"❌ [{api_name.upper()}] Error during search: {type(e).__name__}: {str(e)[:100]}",
                exc_info=False,
            )
            return (None, api_name)

    def _pick_best_result(
        self, 
        results: List[Tuple[Optional[Dict[str, Any]], str]]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Pick the best result from multiple API responses with source variety.
        
        Uses round-robin source selection to ensure variety:
        - If multiple sources return valid results, prefer the least-used source
        - Still requires minimum quality (DOI or URL)
        
        Args:
            results: List of (metadata, source) tuples
            
        Returns:
            Best (metadata, source) tuple, or (None, None) if all failed
        """
        valid_results = [(m, s) for m, s in results if m is not None]
        
        if not valid_results:
            return (None, None)
        
        if len(valid_results) == 1:
            # Update usage count
            _, source = valid_results[0]
            self.source_usage_count[source] = self.source_usage_count.get(source, 0) + 1
            return valid_results[0]
        
        # Filter to only results with acceptable quality (DOI or URL)
        quality_results = [
            (m, s) for m, s in valid_results 
            if m.get('doi') or m.get('url')
        ]
        
        # If no quality results, fall back to any valid result
        if not quality_results:
            quality_results = valid_results
        
        # Sort by source usage count (ascending) to prefer least-used sources
        # This creates round-robin variety across all sources
        sorted_by_variety = sorted(
            quality_results,
            key=lambda x: self.source_usage_count.get(x[1], 0)
        )
        
        # Pick the least-used source
        metadata, source = sorted_by_variety[0]
        
        # Update usage count
        self.source_usage_count[source] = self.source_usage_count.get(source, 0) + 1
        
        return (metadata, source)



    def _llm_research(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Research citation using Gemini LLM (fallback only).

        This is the current behavior - kept for backward compatibility.

        Args:
            topic: Topic to research

        Returns:
            Metadata dict or None
        """
        if not self.gemini_model:
            return None

        try:
            # Load Scout agent prompt
            from utils.agent_runner import load_prompt

            scout_prompt = load_prompt("prompts/01_research/scout.md")

            # Build research request (same as current implementation)
            user_input = f"""# Research Task

Find the most relevant academic paper for this topic:

**Topic:** {topic}

## Requirements

1. Search for papers matching this topic
2. Find the single MOST relevant paper (highest quality, most cited, most recent)
3. Return ONLY ONE paper with complete metadata

## Output Format

Return a JSON object with this structure:

```json
{{
  "authors": ["Author One", "Author Two"],
  "year": 2023,
  "title": "Complete Paper Title",
  "source_type": "journal|conference|book|report|article",
  "journal": "Journal Name (if journal article)",
  "conference": "Conference Name (if conference paper)",
  "doi": "10.xxxx/xxxxx (if available)",
  "url": "https://... (if available)",
  "pages": "1-10 (if available)",
  "volume": "5 (if available)",
  "publisher": "Publisher Name (if available)"
}}
```

## Important

- Return ONLY the JSON object, no markdown, no explanation
- Ensure all fields are present (use empty string "" if not available)
- year must be an integer
- authors must be a list (even if only one author)
- source_type must be one of: journal, conference, book, report, article
- If you cannot find a paper, return: {{"error": "No paper found"}}
"""

            # Call Gemini for LLM fallback
            # Note: Safety settings are handled by model/provider configuration.
            response = self.gemini_model.generate_content(
                [scout_prompt, user_input],
                generation_config={"temperature": 0.2, "max_output_tokens": 2048},
            )

            # Parse JSON response with error handling for safety blocks
            import json

            # Check if response was blocked by safety filter
            if not response.candidates:
                logger.warning(f"LLM response blocked (no candidates) for topic: {topic[:50]}...")
                return None

            candidate = response.candidates[0]
            if candidate.finish_reason not in [1, 0]:  # 1 = STOP (normal), 0 = UNSPECIFIED
                logger.warning(
                    f"LLM response blocked (finish_reason={candidate.finish_reason}) for topic: {topic[:50]}..."
                )
                return None

            # Try to access response text safely
            try:
                response_text = response.text.strip()
            except ValueError as e:
                # response.text raises ValueError if no valid part exists
                logger.warning(f"LLM response has no valid text (safety filter likely) for topic: {topic[:50]}...")
                return None

            # Remove markdown code blocks if present
            response_text = strip_markdown_json(response_text)

            # Parse JSON first (error responses lack required fields for Pydantic)
            try:
                raw_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"LLM returned invalid JSON for topic '{topic[:50]}...': {e}")
                logger.debug(f"Raw response: {response_text[:200]}...")
                return None

            # Check for error before validation
            if "error" in raw_data:
                logger.debug(f"LLM returned error response for topic '{topic[:50]}...': {raw_data['error']}")
                return None

            # Validate with Pydantic
            try:
                data = LLMCitationResponse.model_validate(raw_data)
            except ValidationError as e:
                logger.warning(f"LLM returned invalid citation for topic '{topic[:50]}...': {e}")
                return None

            # Convert validated model to dict for existing pipeline
            return {
                "title": data.title,
                "authors": data.authors,
                "year": data.year,
                "doi": data.doi,
                "url": data.url,
                "journal": data.journal or data.conference,
                "publisher": data.publisher,
                "volume": data.volume,
                "issue": data.issue,
                "pages": data.pages,
                "source_type": data.source_type,
                "confidence": 0.5,  # Lower confidence for LLM results
            }

        except Exception as e:
            logger.error(f"LLM research failed for topic '{topic[:50]}...': {e}")
            return None

    def close(self) -> None:
        """Close API clients."""
        if hasattr(self, "crossref"):
            self.crossref.close()
        if hasattr(self, "openalex"):
            # Was omitted before OpenAlex became a confirmation source; its
            # session stayed open for the life of the process.
            self.openalex.close()
        if hasattr(self, "semantic_scholar"):
            self.semantic_scholar.close()
        if hasattr(self, "gemini_grounded"):
            self.gemini_grounded.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
