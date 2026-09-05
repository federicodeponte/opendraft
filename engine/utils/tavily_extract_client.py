#!/usr/bin/env python3
"""
ABOUTME: Tavily Extract API client for web page content extraction
ABOUTME: Parallel option alongside Firecrawl for page scraping
"""

import os
import logging
from typing import Optional, Dict, Any, List

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

logger = logging.getLogger(__name__)


class TavilyExtractClient:
    """
    Tavily Extract API client for web page content extraction.

    Uses Tavily's extract() endpoint to fetch clean content from URLs.
    Returns the same {success, content, url, metadata} dict that
    FirecrawlClient.scrape_url() returns for drop-in compatibility.

    Requirements:
    - tavily-python
    - TAVILY_API_KEY environment variable
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily Extract client.

        Args:
            api_key: Tavily API key (defaults to TAVILY_API_KEY env var)
        """
        if load_dotenv is not None:
            load_dotenv()

        self.api_key = api_key or os.getenv('TAVILY_API_KEY')

        if not TavilyClient:
            raise ImportError("tavily-python not installed. Run: pip install tavily-python")

        if self.api_key:
            self._client = TavilyClient(api_key=self.api_key)
        else:
            self._client = None

    @property
    def enabled(self) -> bool:
        """Check if Tavily Extract is configured and available."""
        return bool(self.api_key and self._client)

    def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Extract content from a webpage using Tavily Extract.

        Args:
            url: The URL to extract content from

        Returns:
            Dict with:
                - success: bool
                - content: str (extracted text content)
                - url: str
                - metadata: dict
                - error: str (if failed)
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Tavily Extract not configured (TAVILY_API_KEY missing)',
                'content': '',
                'url': url,
                'metadata': {},
            }

        try:
            response = self._client.extract(urls=[url])

            results = response.get('results', [])
            if results:
                result = results[0]
                raw_content = result.get('raw_content', '')

                if not raw_content or not raw_content.strip():
                    return {
                        'success': False,
                        'error': f'Tavily Extract returned empty content for {url}',
                        'content': '',
                        'url': url,
                        'metadata': {},
                    }

                # Truncate to reasonable length (matching Firecrawl convention)
                if len(raw_content) > 15000:
                    raw_content = raw_content[:15000] + "\n\n... [content truncated]"

                logger.info(f"[TavilyExtract] Extracted {len(raw_content)} chars from: {url[:50]}...")

                return {
                    'success': True,
                    'content': raw_content,
                    'url': result.get('url', url),
                    'metadata': {},
                }

            # Check for failed results
            failed = response.get('failed_results', [])
            if failed:
                error_msg = failed[0].get('error', 'Unknown extraction error')
                logger.warning(f"[TavilyExtract] Failed for {url}: {error_msg}")
                return {
                    'success': False,
                    'error': f'Tavily Extract failed: {error_msg}',
                    'content': '',
                    'url': url,
                    'metadata': {},
                }

            return {
                'success': False,
                'error': f'Tavily Extract returned no results for {url}',
                'content': '',
                'url': url,
                'metadata': {},
            }

        except Exception as e:
            logger.warning(f"[TavilyExtract] Error for {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': '',
                'url': url,
                'metadata': {},
            }
