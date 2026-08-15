"""
ABOUTME: API-backed citation research and multi-source confirmation
ABOUTME: Discovery via Crossref/OpenAlex/Semantic Scholar, then DOI confirmation across them
"""

from .orchestrator import CitationResearcher
from .crossref import CrossrefClient
from .openalex import OpenAlexClient
from .semantic_scholar import SemanticScholarClient
from .multi_source import (
    ConfirmationResult,
    MultiSourceConfirmer,
    SCHOLARLY_SOURCES,
    VERIFICATION_LLM_UNVERIFIED,
    VERIFICATION_MULTI_SOURCE,
    VERIFICATION_NOT_CHECKED,
    VERIFICATION_SINGLE_SOURCE,
    VERIFICATION_WEB_SEARCH,
)

__all__ = [
    "CitationResearcher",
    "CrossrefClient",
    "OpenAlexClient",
    "SemanticScholarClient",
    "MultiSourceConfirmer",
    "ConfirmationResult",
    "SCHOLARLY_SOURCES",
    "VERIFICATION_MULTI_SOURCE",
    "VERIFICATION_SINGLE_SOURCE",
    "VERIFICATION_WEB_SEARCH",
    "VERIFICATION_LLM_UNVERIFIED",
    "VERIFICATION_NOT_CHECKED",
]
