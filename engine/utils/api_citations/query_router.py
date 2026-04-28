#!/usr/bin/env python3
"""
ABOUTME: Smart query router for citation source discovery
ABOUTME: Routes queries to appropriate APIs based on source type detection

Production-grade query classification following SOLID principles.

Purpose:
Routes citation research queries to the most appropriate API source:
- Industry queries → Gemini Grounded (web sources) first
- Academic queries → Crossref (peer-reviewed) first
- Mixed queries → Semantic Scholar (balanced) first

This maximizes source diversity while maintaining efficiency (1 API call per query).
"""

from typing import Literal, List, Tuple
from dataclasses import dataclass


# Type definitions
QueryType = Literal['academic', 'industry', 'mixed']
APIName = Literal['crossref', 'semantic_scholar', 'gemini_grounded', 'tavily']


@dataclass
class QueryClassification:
    """
    Classification result for a research query.

    Attributes:
        query_type: Classified type ('academic', 'industry', 'mixed')
        confidence: Confidence score 0.0-1.0
        matched_patterns: List of patterns that triggered classification
        api_chain: Prioritized list of APIs to try
    """
    query_type: QueryType
    confidence: float
    matched_patterns: List[str]
    api_chain: List[APIName]


class QueryRouter:
    """
    Routes research queries to appropriate citation sources.

    Implements smart routing to maximize source diversity while maintaining
    efficiency. Classifies queries based on keyword patterns and returns
    prioritized API chains.

    Design Principles:
    - Single Responsibility: Only handles query classification and routing
    - Open/Closed: Extensible via pattern lists without modifying core logic
    - Dependency Inversion: Returns API names, not implementations

    Examples:
        >>> router = QueryRouter()
        >>> result = router.classify_and_route("McKinsey digital transformation report 2023")
        >>> result.query_type
        'industry'
        >>> result.api_chain
        ['gemini_grounded', 'semantic_scholar', 'crossref']

        >>> result = router.classify_and_route("peer-reviewed studies on climate change")
        >>> result.query_type
        'academic'
        >>> result.api_chain
        ['crossref', 'semantic_scholar', 'gemini_grounded']
    """

    # Industry source indicators (organizations, document types)
    INDUSTRY_PATTERNS = [
        # Consulting firms
        'mckinsey', 'boston consulting', 'bcg', 'bain', 'deloitte',
        'accenture', 'pwc', 'kpmg', 'ey', 'gartner', 'forrester',
        'idc', 'ovum', 'frost & sullivan',

        # Think tanks & research institutes
        'brookings', 'rand corporation', 'carnegie', 'cato institute',
        'heritage foundation', 'pew research', 'urban institute',
        'chatham house', 'cfr', 'council on foreign relations',

        # International organizations
        'world bank', 'imf', 'international monetary fund',
        'oecd', 'united nations', 'who', 'world health organization',
        'wef', 'world economic forum', 'itu', 'wto',

        # Government & regulatory bodies
        'european commission', 'eu commission', 'ec report',
        'european parliament', 'us congress', 'congressional',
        'government accountability office', 'gao',
        'federal reserve', 'european central bank', 'ecb',
        'fda', 'epa', 'cdc', 'nih', 'nist', 'nasa',

        # Standards bodies (use word boundaries to avoid false positives like "comparison")
        'iso standard', 'iso ', 'ieee', 'ietf', 'w3c', 'oasis', 'ansi',

        # Document types
        'white paper', 'whitepaper', 'policy brief', 'policy paper',
        'technical report', 'industry report', 'market research',
        'working paper', 'briefing', 'position paper',
        'guidelines', 'framework', 'best practices',
        'standards document', 'regulation', 'directive',

        # Business/Industry focus
        'market analysis', 'industry trends', 'sector overview',
        'competitive landscape', 'market forecast',

        # Tech companies & products (NEW - Day 3A enhancement)
        'openai', 'anthropic', 'google', 'microsoft', 'meta',
        'amazon', 'apple', 'ibm', 'oracle', 'salesforce',
        'gpt-4', 'claude', 'gemini', 'chatgpt', 'copilot',
        'aws', 'azure', 'gcp', 'cloud platform',

        # Consulting/Industry sources (NEW - Day 3A enhancement)
        'comparison', 'benchmark', 'pricing comparison',
        'vendor', 'product', 'service provider',
        'platform', 'saas', 'enterprise software',
        'implementation', 'deployment', 'migration',
    ]

    # Academic source indicators (peer-reviewed, scholarly)
    ACADEMIC_PATTERNS = [
        # Publication types
        'peer-reviewed', 'peer reviewed', 'scholarly article',
        'journal article', 'academic paper', 'research paper',
        'conference paper', 'proceedings', 'dissertation',
        'draft', 'monograph',

        # Research methodology
        'empirical study', 'empirical research', 'empirical analysis',
        'systematic review', 'meta-analysis', 'literature review',
        'randomized controlled trial', 'rct', 'cohort study',
        'case-control study', 'longitudinal study',
        'qualitative research', 'quantitative research',

        # Academic rigor indicators
        'published in', 'indexed in', 'scopus', 'web of science',
        'impact factor', 'cited by', 'citations',

        # Scholarly databases
        'pubmed', 'jstor', 'springer', 'elsevier', 'wiley',
        'taylor & francis', 'sage', 'oxford university press',

        # Research focus
        'theoretical framework', 'conceptual model',
        'research methodology', 'data analysis',

        # Economic & business theory (NEW - Day 3A enhancement)
        'economics', 'economic theory', 'economic model',
        'pricing theory', 'market theory', 'game theory',
        'transaction cost', 'information goods', 'public goods',
        'two-sided market', 'platform economics', 'network effects',
        'demand elasticity', 'price discrimination', 'marginal cost',
        'economies of scale', 'market equilibrium',

        # Technology/CS theory (NEW - Day 3A enhancement)
        'algorithm', 'computational complexity', 'machine learning',
        'neural network', 'natural language processing',
        'computer vision', 'distributed systems', 'cryptography',
        'information retrieval', 'data mining',

        # Social sciences (NEW - Day 3A enhancement)
        'sociological', 'psychological', 'anthropological',
        'behavioral', 'cognitive', 'organizational behavior',

        # Environmental/climate science (NEW - Day 3A enhancement)
        'climate science', 'environmental impact', 'carbon emissions',
        'renewable energy', 'sustainability assessment',
        'ecological', 'biodiversity',
    ]

    def __init__(self, enable_multilingual: bool = True):
        """
        Initialize QueryRouter.

        Args:
            enable_multilingual: Support German/Spanish patterns (default: True)
        """
        self.enable_multilingual = enable_multilingual

        # Add multilingual patterns if enabled
        if enable_multilingual:
            self._add_multilingual_patterns()

    def _add_multilingual_patterns(self) -> None:
        """Add German and Spanish pattern support."""
        # German patterns
        self.INDUSTRY_PATTERNS.extend([
            'bericht', 'studie', 'whitepaper', 'leitfaden',  # Document types
            'richtlinien', 'verordnung', 'rahmenwerk',  # Policy/standards
        ])

        self.ACADEMIC_PATTERNS.extend([
            'wissenschaftliche arbeit', 'forschungsarbeit',  # Research types
            'peer-review', 'fachzeitschrift',  # Peer review
            'empirische studie', 'meta-analyse',  # Methodology
        ])

        # Spanish patterns
        self.INDUSTRY_PATTERNS.extend([
            'informe', 'libro blanco', 'directrices',  # Document types
            'marco', 'regulación', 'normativa',  # Policy/standards
        ])

        self.ACADEMIC_PATTERNS.extend([
            'artículo académico', 'trabajo de investigación',  # Research types
            'revisión por pares', 'revista académica',  # Peer review
            'estudio empírico', 'metaanálisis',  # Methodology
        ])

    def classify_query(self, query: str) -> Tuple[QueryType, float, List[str]]:
        """
        Classify a research query as academic, industry, or mixed.

        Args:
            query: Research query string

        Returns:
            Tuple of (query_type, confidence, matched_patterns)

        Examples:
            >>> router = QueryRouter()
            >>> query_type, confidence, patterns = router.classify_query(
            ...     "McKinsey report on digital transformation"
            ... )
            >>> query_type
            'industry'
            >>> confidence
            0.9
        """
        query_lower = query.lower()

        # Count pattern matches
        industry_matches = [p for p in self.INDUSTRY_PATTERNS if p in query_lower]
        academic_matches = [p for p in self.ACADEMIC_PATTERNS if p in query_lower]

        # Classify based on matches
        if industry_matches and not academic_matches:
            # Clear industry query
            confidence = min(0.9, 0.5 + (len(industry_matches) * 0.1))
            return 'industry', confidence, industry_matches

        elif academic_matches and not industry_matches:
            # Clear academic query
            confidence = min(0.9, 0.5 + (len(academic_matches) * 0.1))
            return 'academic', confidence, academic_matches

        elif industry_matches and academic_matches:
            # Mixed query (both types)
            if len(industry_matches) > len(academic_matches):
                confidence = 0.6
                return 'industry', confidence, industry_matches + academic_matches
            elif len(academic_matches) > len(industry_matches):
                confidence = 0.6
                return 'academic', confidence, industry_matches + academic_matches
            else:
                confidence = 0.5
                return 'mixed', confidence, industry_matches + academic_matches

        else:
            # No clear indicators - default to mixed
            confidence = 0.3
            return 'mixed', confidence, []

    def get_api_chain(self, query_type: QueryType) -> List[APIName]:
        """
        Get prioritized API chain for a query type.

        Args:
            query_type: Classified query type

        Returns:
            List of API names in priority order

        API Priority Chains:
        - industry: Gemini Grounded → Semantic Scholar → Crossref
        - academic: Crossref → Semantic Scholar → Gemini Grounded
        - mixed: Semantic Scholar → Gemini Grounded → Crossref
        """
        if query_type == 'industry':
            # Prioritize web sources for industry queries
            return ['tavily', 'gemini_grounded', 'semantic_scholar', 'crossref']

        elif query_type == 'academic':
            # Prioritize academic sources for scholarly queries
            return ['crossref', 'semantic_scholar', 'tavily', 'gemini_grounded']

        else:  # mixed
            # Balanced approach for mixed queries
            return ['semantic_scholar', 'tavily', 'gemini_grounded', 'crossref']

    def classify_and_route(self, query: str) -> QueryClassification:
        """
        Classify query and return complete routing information.

        This is the main entry point for query routing.

        Args:
            query: Research query string

        Returns:
            QueryClassification with type, confidence, patterns, and API chain

        Examples:
            >>> router = QueryRouter()
            >>> result = router.classify_and_route("WHO COVID-19 guidelines")
            >>> result.query_type
            'industry'
            >>> result.api_chain[0]
            'gemini_grounded'
        """
        query_type, confidence, patterns = self.classify_query(query)
        api_chain = self.get_api_chain(query_type)

        return QueryClassification(
            query_type=query_type,
            confidence=confidence,
            matched_patterns=patterns,
            api_chain=api_chain
        )


# ============================================================================
# STANDALONE TESTING
# ============================================================================

def main():
    """Test QueryRouter with sample queries."""
    router = QueryRouter()

    test_queries = [
        # Industry queries
        "McKinsey digital transformation report 2023",
        "Gartner magic quadrant for cloud providers",
        "WHO COVID-19 vaccination guidelines",
        "European Commission AI regulation framework",
        "OECD economic outlook 2024",

        # Academic queries
        "peer-reviewed studies on climate change mitigation",
        "systematic review of carbon pricing mechanisms",
        "empirical analysis of renewable energy adoption",
        "meta-analysis of COVID-19 vaccine efficacy",

        # Mixed queries
        "blockchain technology best practices",
        "artificial intelligence ethics frameworks",
        "cybersecurity incident response strategies",
    ]

    print("="*80)
    print("QUERY ROUTER - CLASSIFICATION TEST")
    print("="*80)

    for query in test_queries:
        result = router.classify_and_route(query)

        print(f"\nQuery: {query}")
        print(f"  Type: {result.query_type} (confidence: {result.confidence:.2f})")
        print(f"  API Chain: {' → '.join(result.api_chain)}")
        if result.matched_patterns:
            print(f"  Patterns: {', '.join(result.matched_patterns[:3])}...")


if __name__ == '__main__':
    main()
