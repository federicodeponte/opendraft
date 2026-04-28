"""
Fallback Services for Web Search and Page Scraping
===================================================

Tools:
- Serper.dev: Web search via Google SERP API (preferred)
- DataForSEO: Web search via SERP API (2000 RPM) (legacy fallback)
- Tavily Extract: Page content extraction via Tavily API (preferred when TAVILY_API_KEY set)
- Firecrawl: Page scraping with JavaScript rendering (fallback)
- OpenPull: Page scraping with JavaScript rendering (crawl4ai + Playwright) (legacy)
- Simple fallback: Basic requests-based scraping for non-JS pages

Usage:
    from fallback_services import search_web_serper, scrape_page_with_firecrawl
    from fallback_services import scrape_page_with_tavily
    # Legacy:
    from fallback_services import search_web_dataforseo, scrape_page_with_openpull
"""

import os
import base64
import json
import logging
import time
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)

# ==============================================================================
# Rate Limiting with Thread-Safe Semaphores + Retries
# ==============================================================================

import threading
import time

# Thread-safe semaphores for rate limiting (shared across all workers in a container)
# DataForSEO: 2000 RPM = ~33/sec, use 30 concurrent to be safe
DATAFORSEO_LOCK = threading.Semaphore(30)
# Gemini: 4000 RPM = ~66/sec, use 60 concurrent to be safe  
GEMINI_LOCK = threading.Semaphore(60)

def with_retry_sync(func, max_retries=3, base_delay=0.5):
    """Execute sync function with exponential backoff retry."""
    import time
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            # Check for rate limit errors
            error_str = str(e).lower()
            if '429' in error_str or 'rate' in error_str or 'quota' in error_str:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise


# ==============================================================================
# Serper.dev Web Search (Preferred)
# ==============================================================================

def search_web_serper(
    query: str,
    num_results: int = 5,
) -> Dict[str, Any]:
    """
    Search the web using Serper.dev Google Search API.

    Preferred over DataForSEO for better pricing and speed.

    Args:
        query: Search query string
        num_results: Number of results to return (default 5)

    Returns:
        Dict with 'success', 'results' (list of search results), and 'error' if failed

    Environment Variables Required:
        SERPER_API_KEY: Serper.dev API key
    """
    try:
        from utils.api_citations.serper_client import SerperClient

        client = SerperClient(num_results=num_results)
        result = client.search_paper(query)

        if result:
            return {
                "success": True,
                "results": [result],  # Wrap single result in list for compatibility
                "query": query
            }
        return {"success": False, "error": "No results found", "results": []}

    except Exception as e:
        logger.warning(f"Serper search failed: {e}, falling back to DataForSEO")
        return search_web_dataforseo(query, num_results)


# ==============================================================================
# Tavily Extract Page Scraping (Preferred when TAVILY_API_KEY is set)
# ==============================================================================

def scrape_page_with_tavily(url: str) -> Dict[str, Any]:
    """
    Extract webpage content using Tavily Extract API.

    Args:
        url: The URL to extract content from

    Returns:
        Dict with 'success', 'content', and 'error' if failed

    Environment Variables Required:
        TAVILY_API_KEY: Tavily API key
    """
    try:
        from utils.tavily_extract_client import TavilyExtractClient

        client = TavilyExtractClient()
        if not client.enabled:
            return {'success': False, 'error': 'Tavily Extract not configured', 'content': ''}
        return client.scrape_url(url)

    except ImportError:
        logger.warning("tavily-python not installed, skipping Tavily Extract")
        return {'success': False, 'error': 'tavily-python not installed', 'content': ''}
    except Exception as e:
        logger.warning(f"Tavily Extract failed: {e}")
        return {'success': False, 'error': str(e), 'content': ''}


# ==============================================================================
# Firecrawl Page Scraping (Fallback after Tavily Extract)
# ==============================================================================

def scrape_page_with_firecrawl(url: str) -> Dict[str, Any]:
    """
    Scrape a webpage, trying Tavily Extract first (if configured),
    then Firecrawl, then simple scraper as final fallback.

    Args:
        url: The URL to scrape

    Returns:
        Dict with 'success', 'content', and 'error' if failed

    Environment Variables:
        TAVILY_API_KEY: Tavily API key (enables Tavily Extract as primary)
        FIRECRAWL_API_KEY: Firecrawl API key (secondary fallback)
    """
    # Try Tavily Extract first when TAVILY_API_KEY is set
    if os.environ.get('TAVILY_API_KEY'):
        result = scrape_page_with_tavily(url)
        if result.get('success'):
            return result
        logger.info(f"Tavily Extract failed for {url}, falling back to Firecrawl")

    # Firecrawl as secondary
    try:
        from utils.firecrawl_client import FirecrawlClient

        client = FirecrawlClient()
        return client.scrape_url(url)

    except Exception as e:
        logger.warning(f"Firecrawl scrape failed: {e}, falling back to simple scraper")
        return get_url_context_simple(url)


# ==============================================================================
# DataForSEO Web Search Fallback (Legacy)
# ==============================================================================

def search_web_dataforseo(
    query: str,
    num_results: int = 5,
    location_code: int = 2840,  # USA
) -> Dict[str, Any]:
    """
    Search the web using DataForSEO SERP API with rate limiting.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default 5)
        location_code: DataForSEO location code (2840 = USA)
    
    Returns:
        Dict with 'success', 'results' (list of search results), and 'error' if failed
    
    Environment Variables Required:
        DATAFORSEO_LOGIN: DataForSEO API login
        DATAFORSEO_PASSWORD: DataForSEO API password
    """
    login = os.environ.get("DATAFORSEO_LOGIN")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    
    if not login or not password:
        return {
            "success": False,
            "error": "DataForSEO credentials not configured (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)",
            "results": []
        }
    
    # Use semaphore for rate limiting (max 30 concurrent requests)
    with DATAFORSEO_LOCK:
        try:
            # Build auth header
            credentials = f"{login}:{password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            # Use SERP API for organic search results
            endpoint = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
            
            payload = [{
                "keyword": query,
                "location_code": location_code,
                "language_code": "en",
                "depth": num_results,
            }]
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract search results
            results = []
            if data.get("tasks"):
                for task in data["tasks"]:
                    if task.get("result"):
                        for result in task["result"]:
                            if result.get("items"):
                                for item in result["items"]:
                                    if item.get("type") == "organic":
                                        results.append({
                                            "title": item.get("title", ""),
                                            "url": item.get("url", ""),
                                            "snippet": item.get("description", ""),
                                            "position": item.get("rank_absolute", 0)
                                        })
            
            logger.info(f"[DataForSEO] Found {len(results)} results for query: {query[:50]}...")
            
            return {
                "success": True,
                "results": results[:num_results],
                "query": query
            }
            
        except requests.exceptions.Timeout:
            logger.warning(f"[DataForSEO] Timeout for query: {query[:50]}...")
            return {"success": False, "error": "DataForSEO request timed out", "results": []}
        except requests.exceptions.RequestException as e:
            logger.error(f"[DataForSEO] Request error: {e}")
            return {"success": False, "error": str(e), "results": []}
        except Exception as e:
            logger.error(f"[DataForSEO] Unexpected error: {e}")
            return {"success": False, "error": str(e), "results": []}


def format_search_results_for_context(search_result: Dict[str, Any]) -> str:
    """
    Format DataForSEO search results into a context string for the LLM.
    
    Args:
        search_result: Result from search_web_dataforseo()
    
    Returns:
        Formatted string with search results
    """
    if not search_result.get("success") or not search_result.get("results"):
        return ""
    
    lines = [f"Web Search Results for: {search_result.get('query', 'query')}\n"]
    
    for i, result in enumerate(search_result["results"], 1):
        lines.append(f"{i}. {result['title']}")
        lines.append(f"   URL: {result['url']}")
        lines.append(f"   {result['snippet']}\n")
    
    return "\n".join(lines)


# ==============================================================================
# OpenPull Page Scraping (with JavaScript rendering)
# ==============================================================================

# Global browser instance for crawl4ai (reuse across requests)
_crawl4ai_crawler = None
_crawl4ai_lock = threading.Lock()


def _run_async_in_new_loop(coro):
    """
    Run an async coroutine in a completely new thread with its own event loop.
    This avoids conflicts with any existing event loops (like Modal's).
    """
    import concurrent.futures
    
    def run_in_thread():
        import asyncio
        # Create a completely new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result(timeout=90)


def scrape_page_with_openpull(
    url: str,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scrape a webpage using OpenPull/crawl4ai for JavaScript rendering.
    
    This uses crawl4ai to render JavaScript and extract the page content.
    The LLM extraction happens separately in the main processing.
    
    Args:
        url: The URL to scrape
        gemini_api_key: Optional Gemini API key (for OpenPull's LLM extraction if needed)
    
    Returns:
        Dict with 'success', 'content' (page content), and 'error' if failed
    """
    
    async def scrape_with_crawl4ai():
        """Use crawl4ai directly for raw content extraction."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
        
        # Create browser config with proper settings for Modal/headless environment
        browser_config = BrowserConfig(
            headless=True,
            browser_type="chromium",
            verbose=False,
            # Disable sandbox for containerized environments
            extra_args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )
        
        # Create crawler config (using cache_mode instead of deprecated bypass_cache)
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # Updated from deprecated bypass_cache=True
            page_timeout=30000,  # 30 seconds
            delay_before_return_html=1.0,  # Wait 1s after page load
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                config=crawler_config,
            )
            
            if not result.success:
                error_msg = f"ERROR: Failed to access {url}"
                err_str = str(result.error_message) if result.error_message else ""
                if "ERR_NAME_NOT_RESOLVED" in err_str:
                    error_msg = f"ERROR: Domain not found - {url}"
                elif "ERR_CONNECTION_REFUSED" in err_str:
                    error_msg = f"ERROR: Connection refused - website may be down: {url}"
                elif "ERR_CONNECTION_TIMED_OUT" in err_str or "timeout" in err_str.lower():
                    error_msg = f"ERROR: Connection timed out - website too slow: {url}"
                elif "404" in err_str or (hasattr(result, 'status_code') and result.status_code == 404):
                    error_msg = f"ERROR: Page not found (404) - {url}"
                return {"success": False, "error": error_msg, "content": ""}
            
            # Get markdown content (best for LLM processing)
            content = ""
            if hasattr(result, 'markdown') and result.markdown:
                content = result.markdown
            elif hasattr(result, 'cleaned_html') and result.cleaned_html:
                content = result.cleaned_html
            elif hasattr(result, 'html') and result.html:
                content = result.html
            
            if not content.strip():
                return {
                    "success": False,
                    "error": f"ERROR: No content retrieved from {url} - page may be empty or blocked",
                    "content": ""
                }
            
            # Truncate very long content
            if len(content) > 15000:
                content = content[:15000] + "\n\n... [content truncated for length]"
            
            logger.info(f"[crawl4ai] Scraped {len(content)} chars from: {url[:50]}...")
            
            return {
                "success": True,
                "content": content,
                "url": url
            }
    
    # Try crawl4ai first
    try:
        print(f"[scrape_page] Starting scrape for: {url}")
        
        # Use our thread-safe async runner that creates a fresh event loop
        result = _run_async_in_new_loop(scrape_with_crawl4ai())
        
        if result is not None:
            print(f"[scrape_page] Result: success={result.get('success')}, content_len={len(result.get('content', ''))}")
            return result
            
    except ImportError as e:
        print(f"[scrape_page] crawl4ai not available: {e}")
        logger.warning(f"[crawl4ai] Not available: {e}, falling back to simple scraper")
    except Exception as e:
        print(f"[scrape_page] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        logger.warning(f"[crawl4ai] Error: {e}, falling back to simple scraper")
    
    # Fallback to simple requests-based scraper
    print(f"[scrape_page] Using simple fallback scraper for: {url}")
    logger.info(f"[Fallback] Using simple scraper for: {url[:50]}...")
    return get_url_context_simple(url)


# Legacy alias for backward compatibility
def get_url_context_openpull(url: str, prompt: str = "", gemini_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Legacy function - redirects to scrape_page_with_openpull."""
    return scrape_page_with_openpull(url, gemini_api_key)


def get_url_context_simple(url: str) -> Dict[str, Any]:
    """
    Simple URL content extraction fallback using requests + basic parsing.
    Used when OpenPull is not available.
    
    Args:
        url: The URL to fetch content from
    
    Returns:
        Dict with 'success', 'content', and 'error' if failed
    """
    print(f"[simple_scraper] Starting simple scrape for: {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        print(f"[simple_scraper] Making request...")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"[simple_scraper] Response status: {response.status_code}, content length: {len(response.text)}")
        
        # Check for HTTP errors BEFORE parsing
        if response.status_code == 404:
            logger.warning(f"[SimpleURLContext] 404 Not Found: {url}")
            return {"success": False, "error": f"ERROR: Page not found (404) - URL does not exist: {url}", "content": ""}
        if response.status_code == 403:
            logger.warning(f"[SimpleURLContext] 403 Forbidden: {url}")
            return {"success": False, "error": f"ERROR: Access forbidden (403) - website blocked access: {url}", "content": ""}
        if response.status_code >= 400:
            logger.warning(f"[SimpleURLContext] HTTP {response.status_code}: {url}")
            return {"success": False, "error": f"ERROR: HTTP {response.status_code} - failed to load page: {url}", "content": ""}
        
        response.raise_for_status()
        
        # Use BeautifulSoup for robust text extraction
        from bs4 import BeautifulSoup
        
        print(f"[simple_scraper] Parsing HTML with BeautifulSoup...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script, style, and other non-content tags
        for element in soup(['script', 'style', 'noscript', 'head', 'meta', 'link', 'svg', 'iframe']):
            element.decompose()
        
        # Get text with proper whitespace handling
        content = soup.get_text(separator=' ', strip=True)
        print(f"[simple_scraper] Extracted {len(content)} chars")
        # Truncate to reasonable length
        if len(content) > 10000:
            content = content[:10000] + "... [truncated]"
        
        print(f"[simple_scraper] Content preview: {content[:200]}...")
        logger.info(f"[SimpleURLContext] Extracted {len(content)} chars from: {url[:50]}...")
        
        return {
            "success": True,
            "content": content,
            "url": url
        }
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out", "content": ""}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "content": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "content": ""}


# ==============================================================================
# Combined Fallback Handler
# ==============================================================================

def get_tool_context_with_fallback(
    tools: List[str],
    prompt: str,
    row_data: Dict[str, Any],
) -> str:
    """
    Get context using fallback services when Gemini native tools fail.
    
    This function extracts relevant queries/URLs from the prompt and row data,
    then uses DataForSEO/OpenPull to gather context.
    
    Args:
        tools: List of tools requested (e.g., ['web-search', 'scrape-page'])
        prompt: The user's prompt
        row_data: Row data dictionary
    
    Returns:
        Additional context string to prepend to the prompt
    """
    context_parts = []
    
    # Extract any URLs from row data
    urls_to_process = []
    for key, value in row_data.items():
        if isinstance(value, str) and value.startswith(('http://', 'https://')):
            urls_to_process.append(value)
    
    # Handle web search - FAST: single search per row
    if "web-search" in tools:
        # Replace placeholders in prompt to get filled version
        filled_prompt = prompt
        for key, value in row_data.items():
            placeholder = f"{{{{{key}}}}}"
            if value:
                filled_prompt = filled_prompt.replace(placeholder, str(value))
        
        # Build ONE smart search query from row data + prompt context
        search_parts = []
        for key, value in row_data.items():
            if value and len(str(value)) > 2 and not str(value).startswith(('http://', 'https://')):
                search_parts.append(str(value))
        
        # Add context from prompt for better search
        prompt_lower = filled_prompt.lower()
        
        # Check for date-related queries FIRST (these need specific searches)
        if any(kw in prompt_lower for kw in ['today', 'current date', 'what date', 'todays date', "today's date"]):
            search_parts.append("current date today")
        
        # Stock/financial queries
        if any(kw in prompt_lower for kw in ['stock', 'price', 'share', 'ticker', 'market']):
            search_parts.append("stock price today")
        elif any(kw in prompt_lower for kw in ['news', 'latest', 'recent']):
            search_parts.append("latest news")
        elif any(kw in prompt_lower for kw in ['revenue', 'funding', 'valuation']):
            search_parts.append("company funding revenue")
        
        # Single search query
        search_query = " ".join(search_parts[:3])  # Max 3 parts for clean query
        if search_query:
            logger.info(f"[Fallback] Single search: {search_query[:50]}...")
            result = search_web_dataforseo(search_query, num_results=5)
            
            if result["success"]:
                formatted = format_search_results_for_context(result)
                if formatted:
                    context_parts.append("=== Web Search Results ===")
                    context_parts.append(formatted)
    
    # Handle URL context - use simple fallback directly (openpull not installed)
    if "scrape-page" in tools and urls_to_process:
        context_parts.append("=== URL Content ===")
        
        for url in urls_to_process[:3]:  # Limit to 3 URLs
            logger.info(f"[Fallback] Extracting content from: {url[:50]}...")
            # Use simple requests-based extraction directly
            result = get_url_context_simple(url)
            if result["success"] and result["content"]:
                context_parts.append(f"\nContent from {url}:")
                context_parts.append(result["content"][:5000])
    
    if context_parts:
        return "\n\n".join(context_parts) + "\n\n"
    
    return ""

