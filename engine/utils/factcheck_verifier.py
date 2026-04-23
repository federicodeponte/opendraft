#!/usr/bin/env python3
"""
ABOUTME: Fact-check verification engine for OpenDraft QA pipeline
ABOUTME: Verifies factual claims in generated text using web-grounded evidence and LLM comparison
"""

import sys
import json
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================================================================
# FIFO Cache with TTL (ported from hallucination-detector-v2)
# =========================================================================

class FIFOCache:
    """Simple FIFO cache with TTL expiry for verification results."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired."""
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() - self._timestamps[key] > self.ttl_seconds:
                del self._cache[key]
                del self._timestamps[key]
                return None
            return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        """Add a value to cache, evicting oldest if full."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._timestamps.pop(oldest_key, None)
            self._cache[key] = value
            self._timestamps[key] = time.time()


# =========================================================================
# Verdict Classification
# =========================================================================

VERDICT_SUPPORTED = "SUPPORTED"
VERDICT_CONTRADICTED = "CONTRADICTED"
VERDICT_INSUFFICIENT = "INSUFFICIENT"
VALID_VERDICTS = {VERDICT_SUPPORTED, VERDICT_CONTRADICTED, VERDICT_INSUFFICIENT}


def strip_json_fences(text: str) -> str:
    """
    Strip markdown code fences from LLM JSON output.

    Handles ```json ... ```, ``` ... ```, and plain JSON.
    Returns the inner text ready for json.loads().
    """
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        lines = [l for l in lines if not l.strip().startswith('```')]
        text = '\n'.join(lines)
    return text


def _make_verdict(claim_obj: Dict[str, str], verdict: str = VERDICT_INSUFFICIENT,
                  confidence: float = 0.0, wrong_part: Optional[str] = None,
                  correct_value: Optional[str] = None, source_url: Optional[str] = None,
                  evidence_snippet: str = "") -> Dict[str, Any]:
    """Build a standardised verdict dict from a claim object."""
    return {
        "claim": claim_obj.get("claim", ""),
        "section": claim_obj.get("section", ""),
        "line": claim_obj.get("line", ""),
        "verdict": verdict,
        "confidence": confidence,
        "wrong_part": wrong_part,
        "correct_value": correct_value,
        "source_url": source_url,
        "evidence_snippet": evidence_snippet,
    }


# =========================================================================
# FactCheck Verifier
# =========================================================================

class FactCheckVerifier:
    """
    Verifies factual claims using web-grounded evidence.

    Uses a provider-neutral search backend when available and run_agent for
    claim-vs-evidence comparison. Produces a markdown report with
    find/replace corrections for false claims.
    """

    def __init__(self, api_key: str | None = None, model: Any = None, search_backend: Any = None):
        """
        Initialize the FactCheck verifier.

        Args:
            api_key: Provider API key (Gemini/OpenAI depending on active runtime)
            model: Configured model instance for judge LLM calls via run_agent
            search_backend: Optional search backend with a search_paper() method
        """
        self.api_key = api_key
        self.model = model
        self._cache = FIFOCache(max_size=100, ttl_seconds=3600)

        if search_backend is not None:
            self.search_client = search_backend
        else:
            self.search_client = self._build_default_search_client(api_key)

    def _build_default_search_client(self, api_key: str | None):
        """Build a search client using the best available backend."""
        import os

        use_serper = os.getenv('USE_SERPER', 'false').lower() == 'true' or bool(os.getenv('SERPER_API_KEY'))
        if use_serper:
            try:
                from utils.api_citations.serper_client import SerperClient
                return SerperClient(validate_urls=False, timeout=15)
            except Exception as e:
                logger.warning(f"[FactCheck] Serper client unavailable: {e}")

        # Fall back to Gemini grounded search only when a Google key is present.
        if api_key or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'):
            try:
                from utils.api_citations.gemini_grounded import GeminiGroundedClient
                return GeminiGroundedClient(api_key=api_key or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))
            except Exception as e:
                logger.warning(f"[FactCheck] Gemini grounded client unavailable: {e}")

        return None

    def _verify_single_claim(self, i: int, total: int, claim_obj: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Verify a single claim. Used as a worker for parallel execution.

        Returns verdict dict, or None if claim_text is empty.
        """
        claim_text = claim_obj.get("claim", "")
        if not claim_text:
            return None

        # Check cache
        cached = self._cache.get(claim_text)
        if cached is not None:
            logger.debug(f"Cache hit for claim: {claim_text[:60]}...")
            return cached

        logger.info(f"[FactCheck] Verifying claim {i+1}/{total}: {claim_text[:80]}...")

        try:
            # Step 1: Search for evidence
            evidence = self._search_evidence(claim_text)

            # Step 2: Judge claim against evidence
            verdict = self._judge(claim_obj, evidence)

            # Cache result
            self._cache.put(claim_text, verdict)
            return verdict

        except Exception as e:
            logger.warning(f"[FactCheck] Failed to verify claim: {e}")
            return _make_verdict(claim_obj, evidence_snippet=f"Verification failed: {e}")

    def verify_claims(self, claims: List[Dict[str, str]], max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Verify each claim using web evidence, in parallel.

        Args:
            claims: List of claim dicts with keys: claim, section, line
            max_workers: Max concurrent verification threads (default: 10)

        Returns:
            List of verdict dicts in the same order as input claims
        """
        total = len(claims)

        results: List[Optional[Dict[str, Any]]] = [None] * total

        with ThreadPoolExecutor(max_workers=min(max_workers, total or 1)) as executor:
            future_to_idx = {
                executor.submit(self._verify_single_claim, i, total, claim_obj): i
                for i, claim_obj in enumerate(claims)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.warning(f"[FactCheck] Unexpected error in worker: {e}")
                    results[idx] = _make_verdict(
                        claims[idx], evidence_snippet=f"Verification failed: {e}"
                    )

        # Filter out None results (empty claims)
        return [r for r in results if r is not None]

    def _search_evidence(self, claim: str) -> List[Dict[str, str]]:
        """
        Use the configured search backend to find evidence for/against a claim.

        Args:
            claim: The factual claim to search for

        Returns:
            List of evidence dicts with keys: snippet, url, title
        """
        evidence = []

        if self.search_client is None:
            logger.warning("[FactCheck] No search backend available")
            return evidence

        try:
            if hasattr(self.search_client, '_generate_content_with_grounding'):
                prompt = (
                    f"Is this claim true or false? Find evidence:\n\n"
                    f"Claim: \"{claim}\"\n\n"
                    f"Search for the most reliable sources that confirm or deny this claim. "
                    f"Report what the evidence says with specific numbers, dates, or facts. "
                    f"Include source URLs."
                )

                response_data = self.search_client._generate_content_with_grounding(prompt)

                if response_data:
                    candidates = response_data.get('candidates', [])
                    if candidates:
                        candidate = candidates[0]
                        content = candidate.get('content', {})
                        parts = content.get('parts', [])
                        text = parts[0].get('text', '') if parts else ''

                        if text:
                            evidence.append({
                                'snippet': text[:1000],
                                'url': '',
                                'title': 'Grounded Search',
                            })

                        grounding_metadata = candidate.get('groundingMetadata', {})
                        grounding_chunks = grounding_metadata.get('groundingChunks', [])

                        for chunk in grounding_chunks:
                            web = chunk.get('web', {})
                            if web.get('uri'):
                                evidence.append({
                                    'snippet': web.get('title', ''),
                                    'url': web.get('uri', ''),
                                    'title': web.get('title', 'Web Source'),
                                })
            elif hasattr(self.search_client, 'search_paper'):
                result = self.search_client.search_paper(claim)
                if result:
                    evidence.append({
                        'snippet': result.get('snippet', ''),
                        'url': result.get('url', ''),
                        'title': result.get('title', 'Source'),
                    })
        except Exception as e:
            logger.warning(f"[FactCheck] Evidence search failed: {e}")

        return evidence

    def _judge(self, claim_obj: Dict[str, str], evidence: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        LLM call: compare claim against evidence, return verdict.

        Uses run_agent with the factcheck_judge prompt to compare the
        claim text against the collected evidence and classify as
        SUPPORTED, CONTRADICTED, or INSUFFICIENT.

        Args:
            claim_obj: Dict with claim, section, line
            evidence: List of evidence dicts with snippet, url, title

        Returns:
            Verdict dict with claim, verdict, confidence, wrong_part,
            correct_value, source_url, evidence_snippet
        """
        claim_text = claim_obj.get("claim", "")

        # Format evidence for the judge prompt
        evidence_text = ""
        source_urls = []
        for i, ev in enumerate(evidence, 1):
            evidence_text += f"\n--- Evidence {i} ---\n"
            evidence_text += f"Source: {ev.get('title', 'Unknown')}\n"
            if ev.get('url'):
                evidence_text += f"URL: {ev['url']}\n"
                source_urls.append(ev['url'])
            evidence_text += f"Content: {ev.get('snippet', 'No content')}\n"

        if not evidence_text.strip():
            return _make_verdict(claim_obj, evidence_snippet="No evidence found")

        user_input = f'CLAIM: "{claim_text}"\n\nEVIDENCE:\n{evidence_text}'

        try:
            from utils.agent_runner import run_agent
            from utils.models import FactCheckJudgeVerdict

            raw_output = run_agent(
                model=self.model,
                name="FactCheck - Judge",
                prompt_path="prompts/04_validate/factcheck_judge.md",
                user_input=user_input,
                skip_validation=True,
                verbose=False,
            )

            result = json.loads(strip_json_fences(raw_output))
            parsed = FactCheckJudgeVerdict.model_validate(result)
            verdict = parsed.verdict
            confidence = parsed.confidence
            wrong_part = parsed.wrong_part
            correct_value = parsed.correct_value

            # Business logic: wrong_part must actually appear in the claim
            if wrong_part and wrong_part not in claim_text:
                logger.warning(
                    f"[FactCheck] wrong_part '{wrong_part}' not found in claim, clearing"
                )
                wrong_part = None
                correct_value = None
                if verdict == VERDICT_CONTRADICTED:
                    verdict = VERDICT_INSUFFICIENT

            return _make_verdict(
                claim_obj,
                verdict=verdict,
                confidence=confidence,
                wrong_part=wrong_part,
                correct_value=correct_value,
                source_url=source_urls[0] if source_urls else None,
                evidence_snippet=parsed.evidence_snippet,
            )
        except Exception as e:
            logger.warning(f"[FactCheck] Judge LLM failed: {e}")

        return _make_verdict(
            claim_obj,
            source_url=source_urls[0] if source_urls else None,
            evidence_snippet="Judge evaluation failed",
        )

    def format_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Format verification results as a markdown report.

        Args:
            results: List of verdict dicts from verify_claims()

        Returns:
            Formatted markdown report string
        """
        supported = [r for r in results if r["verdict"] == VERDICT_SUPPORTED]
        contradicted = [r for r in results if r["verdict"] == VERDICT_CONTRADICTED]
        insufficient = [r for r in results if r["verdict"] == VERDICT_INSUFFICIENT]

        lines = []
        lines.append("# Fact-Check Verification Report")
        lines.append("")
        lines.append(f"**Claims Checked:** {len(results)}")
        lines.append(f"**Verified:** {len(supported)} ✅")
        lines.append(f"**Issues Found:** {len(contradicted)} ⚠️")
        lines.append(f"**Unverifiable:** {len(insufficient)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Issues section
        if contradicted:
            lines.append("## ⚠️ ISSUES FOUND")
            lines.append("")

            for i, result in enumerate(contradicted, 1):
                lines.append(f"**Issue {i}: Incorrect Claim**")
                lines.append(f"- **Section:** {result.get('section', 'Unknown')}")
                lines.append(f"- **Claim:** \"{result['claim']}\"")
                lines.append(f"- **Evidence:** {result.get('evidence_snippet', 'N/A')}")

                if result.get("wrong_part") and result.get("correct_value"):
                    lines.append(f"- **Find:** \"{result['wrong_part']}\"")
                    lines.append(f"- **Replace with:** \"{result['correct_value']}\"")

                if result.get("source_url"):
                    lines.append(f"- **Source:** {result['source_url']}")

                lines.append(f"- **Confidence:** {result.get('confidence', 0):.0%}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Verified claims section
        if supported:
            lines.append("## ✅ VERIFIED CLAIMS")
            lines.append("")

            for result in supported:
                lines.append(f"- ✅ \"{result['claim']}\"")
                if result.get("evidence_snippet"):
                    lines.append(f"  - Evidence: {result['evidence_snippet'][:150]}")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Unverifiable claims section
        if insufficient:
            lines.append("## ❓ UNVERIFIABLE CLAIMS")
            lines.append("")

            for result in insufficient:
                lines.append(f"- ❓ \"{result['claim']}\"")
                if result.get("evidence_snippet") and result["evidence_snippet"] != "No evidence found":
                    lines.append(f"  - Note: {result['evidence_snippet'][:150]}")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")

        if contradicted:
            lines.append(f"1. **Fix {len(contradicted)} factual error(s)** using the Find/Replace corrections above")
            lines.append("2. **Verify corrections** against the provided source URLs")
            lines.append("3. **Re-run fact-check** after applying fixes to confirm accuracy")
        else:
            lines.append("All checked claims appear accurate based on available evidence.")

        if insufficient:
            lines.append(f"\n**Note:** {len(insufficient)} claim(s) could not be verified — consider adding citations or rephrasing as qualified statements.")

        lines.append("")

        return "\n".join(lines)
