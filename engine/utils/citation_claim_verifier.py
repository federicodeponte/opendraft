#!/usr/bin/env python3
"""
ABOUTME: Claim-level citation verification — does a citation actually support the claim it is attached to
ABOUTME: Complements existence checking (MultiSourceConfirmer), which only proves a work is real

Two different questions, and the project needs both answered:

1. "Is this a real paper?"  -> utils.api_citations.multi_source.MultiSourceConfirmer
   Confirms a DOI is registered and indexed in several scholarly databases.

2. "Does this paper support THIS sentence?"  -> this module
   A real, correctly cited, multi-source-confirmed paper can still be attached
   to a claim it says nothing about. Existence checking cannot detect that.

Ported from the OpenPaper backend (CitationClaimVerifier). Adapted to this
repository: it drives the shared GenerativeModel wrapper rather than a
hand-rolled REST client, and reuses the FIFOCache and strip_json_fences already
present in utils.factcheck_verifier instead of duplicating them.

This module makes LLM judgements. A verdict is an opinion from a language model
about topical relevance, not a proof. UNCERTAIN is a first-class outcome and is
reported as such rather than being rounded up to RELEVANT.
"""

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from utils.factcheck_verifier import FIFOCache, strip_json_fences

logger = logging.getLogger(__name__)


# =========================================================================
# Verdicts
# =========================================================================

VERDICT_RELEVANT = "RELEVANT"
VERDICT_IRRELEVANT = "IRRELEVANT"
VERDICT_UNCERTAIN = "UNCERTAIN"
VALID_CLAIM_VERDICTS = {VERDICT_RELEVANT, VERDICT_IRRELEVANT, VERDICT_UNCERTAIN}


# =========================================================================
# Data Classes
# =========================================================================

@dataclass
class ClaimCitationPair:
    """A claim with its attached citation(s)."""
    claim: str
    citation_ids: List[str]
    section: str = ""
    context: str = ""


@dataclass
class CitationClaimVerdict:
    """Verdict for a claim+citation semantic match."""
    claim: str
    citation_id: str
    citation_title: str
    verdict: Literal["RELEVANT", "IRRELEVANT", "UNCERTAIN"]
    confidence: float = 0.0
    reasoning: str = ""
    claim_topic: str = ""
    citation_topic: str = ""
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persisting alongside the citation database."""
        return {
            "claim": self.claim,
            "citation_id": self.citation_id,
            "citation_title": self.citation_title,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "claim_topic": self.claim_topic,
            "citation_topic": self.citation_topic,
            "suggested_fix": self.suggested_fix,
        }


# =========================================================================
# Prompts
# =========================================================================

EXTRACTION_PROMPT = """# CITATION-CLAIM EXTRACTOR

## Role
Extract claims from the text that have explicit {cite_XXX} markers attached.

## Input
Academic draft text with inline citations in format {cite_XXX}.

## Output Format
Return a JSON array:
```json
[
  {
    "claim": "The exact assertion being made (1-2 sentences max)",
    "citation_ids": ["cite_001"],
    "section": "Section name if identifiable",
    "context": "Brief surrounding context (10-20 words)"
  }
]
```

## Rules
1. Only extract claims with explicit {cite_XXX} markers
2. The claim should be the assertion being supported, not the entire sentence
3. If multiple citations support one claim, include all citation IDs
4. Extract max 25 claim-citation pairs (prioritize different sections)
5. Skip trivial claims like "X et al. studied this topic"
6. Include substantive claims that make factual assertions

## Example
Input: "Deep learning models consistently outperform traditional methods {cite_003}, achieving 95% accuracy on benchmark datasets."
Output: [{"claim": "Deep learning models consistently outperform traditional methods", "citation_ids": ["cite_003"], "section": "Results", "context": "achieving 95% accuracy on benchmark datasets"}]

## Text to Analyze
"""


JUDGE_PROMPT_TEMPLATE = """# CITATION RELEVANCE JUDGE

## Your Task
Determine if a citation semantically supports the claim it's attached to.

## Input
- **CLAIM**: "{claim}"
- **CITATION TITLE**: "{title}"
- **CITATION ABSTRACT**: "{abstract}"

## Output Format
Return ONLY valid JSON:
```json
{{
  "verdict": "RELEVANT" or "IRRELEVANT" or "UNCERTAIN",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 sentence explanation with specific details from both claim and citation",
  "claim_topic": "What the claim is about (3-5 words)",
  "citation_topic": "What the citation is about (3-5 words)",
  "suggested_fix": "If IRRELEVANT: what type of citation would be appropriate (or null if RELEVANT/UNCERTAIN)"
}}
```

## Verdict Rules
- **RELEVANT**: The citation topic clearly relates to the claim topic. The citation could plausibly support this type of claim.
- **IRRELEVANT**: The topics are completely unrelated (e.g., psychology paper cited for satellite imagery claim).
- **UNCERTAIN**: Cannot determine relevance. Use this when:
  - The claim is too vague to judge (e.g., "recent studies show promising results")
  - Abstract is unavailable or uninformative
  - Topics are adjacent but connection is unclear
  - The claim doesn't make a specific factual assertion

## Confidence Calibration (IMPORTANT)
Do NOT default to 100% confidence. Use the full range:
- **95-100%**: Absolutely clear-cut case (child psychology cited for satellite imagery)
- **80-94%**: Strong match/mismatch with minor ambiguity
- **60-79%**: Moderate confidence, some reasonable doubt exists
- **40-59%**: Uncertain, could go either way
- **Below 40%**: Very uncertain, lean toward UNCERTAIN verdict

## Reasoning Requirements
Your reasoning MUST be 2-3 sentences and include:
1. What specific topic the claim addresses
2. What specific topic the citation covers
3. Why they do or don't align (with concrete details)

## Important
- Focus on TOPIC RELEVANCE, not whether the citation proves the specific claim
- A machine learning paper can be RELEVANT to a claim about AI accuracy even if specifics differ
- A child psychology paper is IRRELEVANT to a claim about satellite image classification
- Vague claims like "studies show X" without specifics should be UNCERTAIN
- When the claim lacks substance, use UNCERTAIN not RELEVANT
"""


# =========================================================================
# Citation-Claim Verifier
# =========================================================================

class CitationClaimVerifier:
    """
    Judges whether citations semantically match the claims they are attached to.

    Scope, stated plainly because it is easy to overclaim:
    - This checks TOPICAL RELEVANCE between a claim and a citation's title and
      abstract. It does not read the cited paper's full text and it does not
      establish that the paper proves the claim.
    - A verdict is a language-model judgement. It is evidence for a human
      reviewer, not a certification.
    - When the abstract is missing, the judge is working from the title alone.
      That is exactly the situation the UNCERTAIN verdict exists for.
    """

    def __init__(
        self,
        model: Any,
        citation_database: Any,
        max_pairs: int = 25,
    ):
        """
        Initialize the verifier.

        Args:
            model: GenerativeModel-compatible object (see utils.gemini_client).
                Must expose generate_content(prompt, generation_config=...).
            citation_database: CitationDatabase, or any object with a
                .citations list of Citation-like objects
            max_pairs: Upper bound on claim-citation pairs to extract
        """
        self.model = model
        self.citation_database = citation_database
        self.max_pairs = max_pairs
        self._cache = FIFOCache(max_size=100, ttl_seconds=3600)

        # Build citation lookup
        self._citation_lookup: Dict[str, Any] = {}
        if hasattr(citation_database, 'citations'):
            for c in citation_database.citations:
                self._citation_lookup[c.id] = c

        # Usage tracking
        self._llm_calls = 0
        self._failed_calls = 0

    # ------------------------------------------------------------------
    # LLM plumbing
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        """
        Call the configured model and return its text, or "" on any failure.

        Returning "" rather than raising keeps one bad pair from aborting a
        whole verification run; the caller turns "" into an UNCERTAIN verdict,
        which is the honest outcome when the judge did not answer.
        """
        if self.model is None:
            logger.warning("CitationClaimVerifier has no model; cannot verify")
            return ""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
        except Exception as e:
            self._failed_calls += 1
            logger.warning(f"Citation-claim LLM call failed: {e}")
            return ""

        self._llm_calls += 1

        try:
            text = response.text
        except (AttributeError, ValueError) as e:
            # response.text raises ValueError when a safety filter left no
            # usable part on the candidate.
            self._failed_calls += 1
            logger.warning(f"Citation-claim LLM response had no usable text: {e}")
            return ""

        return (text or "").strip()

    def _parse_json_array_response(
        self, response_text: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Parse an LLM response into a JSON array.

        Handles plain JSON arrays, fenced JSON blocks, and arrays wrapped in
        surrounding prose.
        """
        if not response_text:
            return None

        cleaned = strip_json_fences(response_text).strip()
        candidates = [cleaned]

        # Recover arrays embedded in surrounding prose
        bracket_match = re.search(r"\[[\s\S]*\]", cleaned)
        if bracket_match:
            candidates.append(bracket_match.group(0))

        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return parsed
        return None

    @staticmethod
    def _cache_key(claim: str, citation_id: str) -> str:
        """Stable key for the shared FIFOCache, which is keyed by one string."""
        return hashlib.md5(f"{claim}::{citation_id}".encode()).hexdigest()

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract_claims_with_citations(self, text: str) -> List[ClaimCitationPair]:
        """
        Extract claims from draft text that carry {cite_XXX} markers.

        Returns an empty list if the text has no citation markers at all, which
        is checked cheaply before spending an LLM call.
        """
        if not re.search(r'\{cite_\d+\}', text or ""):
            return []

        # Truncate very long drafts, keeping the head and tail
        if len(text) > 50000:
            text = text[:25000] + "\n\n[...truncated...]\n\n" + text[-25000:]

        prompt = EXTRACTION_PROMPT + text
        strict_json_suffix = (
            "\n\nReturn ONLY valid JSON array output. No markdown fences. "
            "No explanation text before or after the JSON."
        )

        for attempt in range(2):
            response = self._call_llm(
                prompt + (strict_json_suffix if attempt == 1 else ""),
                max_tokens=4096,
                temperature=0.0,
            )
            parsed = self._parse_json_array_response(response)
            if parsed is None:
                continue

            pairs: List[ClaimCitationPair] = []
            for item in parsed[:self.max_pairs]:
                if not isinstance(item, dict):
                    continue
                claim = item.get("claim", "")
                citation_ids = item.get("citation_ids", [])

                if not claim or not citation_ids:
                    continue

                # Keep only IDs that exist in the database. An ID the model
                # invented is not a claim-citation pair, it is a hallucination.
                valid_ids = [cid for cid in citation_ids if cid in self._citation_lookup]
                if valid_ids:
                    pairs.append(
                        ClaimCitationPair(
                            claim=claim,
                            citation_ids=valid_ids,
                            section=item.get("section", ""),
                            context=item.get("context", ""),
                        )
                    )

            if pairs:
                return pairs

        logger.warning("Failed to parse claim extraction response")
        return []

    # ------------------------------------------------------------------
    # Judging
    # ------------------------------------------------------------------

    def _verify_single_pair(self, claim: str, citation_id: str) -> CitationClaimVerdict:
        """Judge one claim-citation pair."""
        citation = self._citation_lookup.get(citation_id)
        if not citation:
            return CitationClaimVerdict(
                claim=claim,
                citation_id=citation_id,
                citation_title="[Not found]",
                verdict=VERDICT_UNCERTAIN,
                confidence=0.0,
                reasoning="Citation not found in database",
            )

        cache_key = self._cache_key(claim, citation_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        title = getattr(citation, 'title', str(citation))
        abstract = getattr(citation, 'abstract', None) or "Not available"

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            claim=claim[:500],
            title=title[:200],
            abstract=abstract[:1000] if abstract else "Not available",
        )

        response = self._call_llm(prompt, max_tokens=1024)

        try:
            parsed = json.loads(strip_json_fences(response))
            if not isinstance(parsed, dict):
                raise json.JSONDecodeError("not an object", response or "", 0)

            verdict_str = str(parsed.get("verdict", VERDICT_UNCERTAIN)).upper()
            if verdict_str not in VALID_CLAIM_VERDICTS:
                verdict_str = VERDICT_UNCERTAIN

            confidence = parsed.get("confidence", 0.5)
            if not isinstance(confidence, (int, float)):
                confidence = 0.5
            confidence = max(0.0, min(1.0, float(confidence)))

            result = CitationClaimVerdict(
                claim=claim,
                citation_id=citation_id,
                citation_title=title,
                verdict=verdict_str,
                confidence=confidence,
                reasoning=parsed.get("reasoning", "") or "",
                claim_topic=parsed.get("claim_topic", "") or "",
                citation_topic=parsed.get("citation_topic", "") or "",
                suggested_fix=parsed.get("suggested_fix", "") or "",
            )

        except (json.JSONDecodeError, TypeError, ValueError):
            # The judge did not return usable JSON. That is not evidence the
            # citation is fine, so it must not become RELEVANT.
            result = CitationClaimVerdict(
                claim=claim,
                citation_id=citation_id,
                citation_title=title,
                verdict=VERDICT_UNCERTAIN,
                confidence=0.0,
                reasoning="Failed to parse LLM response",
            )

        self._cache.put(cache_key, result)
        return result

    def verify_pairs(
        self,
        pairs: List[ClaimCitationPair],
        max_workers: int = 10,
    ) -> List[CitationClaimVerdict]:
        """Judge all claim-citation pairs in parallel."""
        tasks = []
        for pair in pairs:
            for citation_id in pair.citation_ids:
                tasks.append((pair.claim, citation_id))

        if not tasks:
            return []

        results: List[CitationClaimVerdict] = []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as executor:
            future_to_task = {
                executor.submit(self._verify_single_pair, claim, cid): (claim, cid)
                for claim, cid in tasks
            }

            for future in as_completed(future_to_task):
                try:
                    results.append(future.result())
                except Exception as e:
                    claim, cid = future_to_task[future]
                    logger.warning(f"Verification failed for {cid}: {e}")
                    results.append(CitationClaimVerdict(
                        claim=claim,
                        citation_id=cid,
                        citation_title="[Error]",
                        verdict=VERDICT_UNCERTAIN,
                        confidence=0.0,
                        reasoning=f"Verification error: {str(e)[:100]}",
                    ))

        return results

    def verify_citations_against_topic(
        self,
        topic: str,
        citations: Optional[List[Any]] = None,
        max_workers: int = 10,
    ) -> List[CitationClaimVerdict]:
        """
        Judge every citation against the paper topic.

        Used by the citation-management phase, which runs BEFORE any draft text
        exists. At that point the only claim available is the paper's topic, so
        this answers "is this source on-topic for the paper it was gathered
        for", not "does this source support sentence N". Sentence-level
        verification needs draft text and is what verify_pairs does.

        Args:
            topic: Paper topic, used as the claim under test
            citations: Citations to judge; defaults to the whole database
            max_workers: Parallel judge calls

        Returns:
            One verdict per citation
        """
        if not topic:
            return []

        pool = citations if citations is not None else list(self._citation_lookup.values())
        pairs = [
            ClaimCitationPair(claim=topic, citation_ids=[c.id], section="", context="")
            for c in pool
            if getattr(c, "id", None) in self._citation_lookup
        ]
        return self.verify_pairs(pairs, max_workers=max_workers)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def format_report(self, results: List[CitationClaimVerdict]) -> str:
        """Format verification results as a markdown report."""
        if not results:
            return (
                "# Citation-Claim Verification Report\n\n"
                "**No claim-citation pairs found to verify.**\n"
            )

        relevant = [r for r in results if r.verdict == VERDICT_RELEVANT]
        irrelevant = [r for r in results if r.verdict == VERDICT_IRRELEVANT]
        uncertain = [r for r in results if r.verdict == VERDICT_UNCERTAIN]

        total = len(results)

        lines = [
            "# Citation-Claim Verification Report",
            "",
            "Judges whether each citation is topically relevant to the claim it "
            "is attached to, using the citation's title and abstract. This is an "
            "LLM judgement, not a proof, and it does not read the cited paper's "
            "full text.",
            "",
            f"**Pairs Checked:** {total}",
            f"**Relevant:** {len(relevant)} ({len(relevant)/total*100:.0f}%)",
            f"**Mismatched:** {len(irrelevant)} ({len(irrelevant)/total*100:.0f}%)",
            f"**Uncertain:** {len(uncertain)} ({len(uncertain)/total*100:.0f}%)",
            "",
        ]

        if irrelevant:
            lines.extend(["---", "", "## MISMATCHED CITATIONS", ""])
            for i, v in enumerate(irrelevant, 1):
                lines.extend([
                    f"**Issue {i}: Irrelevant Citation**",
                    f"- **Claim:** \"{v.claim[:100]}{'...' if len(v.claim) > 100 else ''}\"",
                    f"- **Citation:** {v.citation_id} - \"{v.citation_title[:80]}{'...' if len(v.citation_title) > 80 else ''}\"",
                    f"- **Problem:** {v.reasoning}",
                    f"- **Claim topic:** {v.claim_topic}",
                    f"- **Citation topic:** {v.citation_topic}",
                    f"- **Confidence:** {v.confidence * 100:.0f}%",
                ])
                if v.suggested_fix:
                    lines.append(f"- **Suggested fix:** {v.suggested_fix}")
                lines.append("")

        if uncertain:
            lines.extend([
                "---", "", "## UNCERTAIN CITATIONS", "",
                "*These citations could NOT be verified either way. Treat them as "
                "unchecked, not as passing.*", "",
            ])
            for v in uncertain[:10]:
                lines.append(f"- {v.citation_id}: \"{v.citation_title[:60]}...\" ({v.reasoning[:50]})")
            if len(uncertain) > 10:
                lines.append(f"- ... and {len(uncertain) - 10} more")
            lines.append("")

        if relevant:
            lines.extend(["---", "", "## TOPICALLY RELEVANT CITATIONS", ""])
            for v in relevant[:15]:
                lines.append(f"- {v.citation_id}: \"{v.citation_title[:60]}...\" supports \"{v.claim[:50]}...\"")
            if len(relevant) > 15:
                lines.append(f"- ... and {len(relevant) - 15} more")
            lines.append("")

        lines.extend([
            "---", "",
            "## Verification Statistics", "",
            f"- Judge LLM calls: {self._llm_calls}",
            f"- Failed/unanswered calls: {self._failed_calls}",
        ])

        return "\n".join(lines)


def summarize_verdicts(verdicts: List[CitationClaimVerdict]) -> Dict[str, int]:
    """Count verdicts by type. Shared by the phase wiring and the report."""
    return {
        'total_pairs': len(verdicts),
        'relevant': sum(1 for v in verdicts if v.verdict == VERDICT_RELEVANT),
        'irrelevant': sum(1 for v in verdicts if v.verdict == VERDICT_IRRELEVANT),
        'uncertain': sum(1 for v in verdicts if v.verdict == VERDICT_UNCERTAIN),
    }


def run_citation_claim_verification(
    draft_text: str,
    citation_database: Any,
    model: Any,
    max_pairs: int = 25,
) -> Dict[str, Any]:
    """
    Run the full sentence-level verification pipeline over draft text.

    Requires draft text containing {cite_XXX} markers, so it can only run after
    composition. For the citation-management phase, which runs before any draft
    exists, see CitationClaimVerifier.verify_citations_against_topic.

    Returns:
        Dict with keys: report (str), stats (dict), verdicts (list)
    """
    verifier = CitationClaimVerifier(
        model=model,
        citation_database=citation_database,
        max_pairs=max_pairs,
    )

    pairs = verifier.extract_claims_with_citations(draft_text)

    if not pairs:
        return {
            'report': (
                "# Citation-Claim Verification Report\n\n"
                "**No claim-citation pairs found.**\n"
            ),
            'stats': {'total_pairs': 0, 'relevant': 0, 'irrelevant': 0, 'uncertain': 0},
            'verdicts': [],
        }

    verdicts = verifier.verify_pairs(pairs)
    report = verifier.format_report(verdicts)

    return {
        'report': report,
        'stats': summarize_verdicts(verdicts),
        'verdicts': verdicts,
    }
