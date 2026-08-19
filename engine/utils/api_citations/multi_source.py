#!/usr/bin/env python3
"""
ABOUTME: Independent multi-source confirmation of a citation across scholarly databases
ABOUTME: Turns "first responder wins" fallback into "N of {Crossref, OpenAlex, Semantic Scholar} agree"
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =========================================================================
# Verification vocabulary
#
# These strings are written into the citation record and persisted to
# bibliography.json, so a downstream reader can tell HOW a citation was
# established. A citation with no verification_status at all predates this
# feature and was not checked by it. Do not reuse or repurpose the values.
# =========================================================================

# Confirmed by >= min_confirming_sources distinct scholarly databases.
VERIFICATION_MULTI_SOURCE = "multi_source_confirmed"

# Exactly one scholarly database holds a record for this DOI. The work is
# real as far as that one database is concerned; no second database agreed.
VERIFICATION_SINGLE_SOURCE = "single_source"

# NO scholarly database holds a record for this DOI. Kept distinct from
# VERIFICATION_SINGLE_SOURCE, which positively asserts that one database does.
# Reachable when a candidate carries a DOI but came from a non-scholarly source
# (web search) and no database recognises that DOI.
VERIFICATION_UNCONFIRMED = "unconfirmed"

# Found by web search (Gemini Grounded / Serper). Not a scholarly database
# record; typically has no DOI, so scholarly confirmation is not applicable.
VERIFICATION_WEB_SEARCH = "web_search_unconfirmed"

# Asserted by the LLM with no external lookup of any kind. Nothing checked
# that this work exists. Never treat this as equivalent to the above.
VERIFICATION_LLM_UNVERIFIED = "llm_unverified"

# Confirmation was not run (require_multi_source disabled and no tagging pass).
VERIFICATION_NOT_CHECKED = "not_checked"

# The three independent scholarly databases used for confirmation.
# Source names must match the strings the orchestrator records in valid_results.
SCHOLARLY_SOURCES = ("Crossref", "OpenAlex", "Semantic Scholar")

# Minimum normalized-token overlap between the title we already have and the
# title the confirming database returns for the same DOI.
#
# A DOI is a unique identifier, so a hit is strong evidence on its own. This
# guard only exists to catch a database returning an unrelated record (a bad
# redirect, a parsing bug). It is deliberately lenient: real records differ in
# spelling and hyphenation across databases. Measured example, DOI
# 10.1038/nature12373: Crossref says "Nanometre-scale thermometry in a living
# cell", Semantic Scholar says "Nanometer scale thermometry in a living cell",
# which scores 0.80 under this metric (after stop-word removal).
TITLE_SIMILARITY_THRESHOLD = 0.5


def normalize_doi(doi: Optional[str]) -> str:
    """
    Reduce a DOI to its bare, comparable form.

    Strips URL prefixes and the "doi:" scheme, and lowercases (DOIs are
    case-insensitive by specification).

    Args:
        doi: DOI in any common form, or None

    Returns:
        Bare lowercase DOI, or "" if there is nothing usable
    """
    if not doi:
        return ""
    value = str(doi).strip()
    # Accept the schemeless form ("doi.org/10.x/y") and the www. host as well as
    # dx. — a DOI scraped off a page arrives in all of these. Missing one used to
    # produce a lookup miss in every database, which then read as "no database
    # has this work" and silently dropped a real citation.
    value = re.sub(r'^(https?://)?(dx\.|www\.)?doi\.org/', '', value, flags=re.IGNORECASE)
    value = re.sub(r'^doi:\s*', '', value, flags=re.IGNORECASE)
    # Trailing sentence punctuation from scraped text is not part of the DOI.
    value = value.strip().rstrip('.,;)')
    return value.strip().lower()


# Words carrying no discriminating power in a title comparison. Without this,
# two unrelated papers sharing only "the/of/a" score as a match.
_TITLE_STOP_WORDS = frozenset({
    "a", "an", "the", "of", "on", "in", "for", "and", "or", "to", "with",
    "is", "are", "at", "by", "from", "as", "its", "it", "this", "that",
})


def _title_tokens(title: Optional[str]) -> Set[str]:
    """Split a title into lowercase alphanumeric tokens, minus stop words."""
    if not title:
        return set()
    tokens = set(re.findall(r'[a-z0-9]+', str(title).lower()))
    meaningful = tokens - _TITLE_STOP_WORDS
    # A title made entirely of stop words still has to compare as something.
    return meaningful or tokens


def title_similarity(left: Optional[str], right: Optional[str]) -> float:
    """
    Overlap between two titles as a fraction of the smaller token set.

    Using the smaller set as denominator keeps a subtitle-truncated record from
    being scored as a mismatch: databases routinely hold "Title" where another
    holds "Title: A Longer Subtitle".

    KNOWN WEAKNESS, stated because the guard is easy to over-trust. That same
    choice of denominator means a very short title is almost always "similar" to
    a longer one that contains its words. Measured, after stop-word removal:

        'Attention'  vs 'Attention Is All You Need'          -> 1.00
        'A Study'    vs 'A Study of Beekeeping in Bavaria'    -> 1.00

    So for one- or two-word titles this check cannot meaningfully fire. It is a
    secondary sanity guard only; the DOI is the identity key, and this exists
    solely to catch a database returning a clearly unrelated record. It is
    deliberately biased towards accepting, because a false rejection deletes a
    real citation while a false acceptance only keeps one whose DOI already
    matched.

    Returns:
        0.0 to 1.0; 0.0 if either title is empty
    """
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))


@dataclass
class ConfirmationResult:
    """
    Outcome of confirming one candidate citation across scholarly databases.

    The distinction between the two source lists is deliberate:

    - ``confirming_sources`` includes the finder, i.e. the database that
      returned this candidate in the first place. In the real pipeline the
      finder genuinely holds the record, so counting it is correct.
    - ``independently_confirmed_by`` lists only databases this class looked up
      itself. It never contains the finder's own assertion.

    When auditing output, ``independently_confirmed_by`` is the list that was
    actually re-checked here.

    ``failed_sources`` is equally load-bearing: a database that errored out did
    NOT say the work is absent, it said nothing at all. "We could not reach it"
    and "it is not there" must never be recorded as the same thing.
    """

    status: str
    confirming_sources: List[str] = field(default_factory=list)
    independently_confirmed_by: List[str] = field(default_factory=list)
    checked_sources: List[str] = field(default_factory=list)
    failed_sources: List[str] = field(default_factory=list)
    doi: str = ""
    notes: str = ""

    @property
    def is_multi_source_confirmed(self) -> bool:
        return self.status == VERIFICATION_MULTI_SOURCE

    @property
    def source_count(self) -> int:
        return len(self.confirming_sources)

    @property
    def had_lookup_failures(self) -> bool:
        """True if any database was unreachable, making this verdict provisional."""
        return bool(self.failed_sources)


class MultiSourceConfirmer:
    """
    Confirms a candidate citation against several scholarly databases by DOI.

    The orchestrator's fallback chain answers "did anyone find something for
    this query", which one database can satisfy alone. This class answers a
    different and stricter question: "does this exact work, identified by DOI,
    independently exist in more than one scholarly database".

    Confirmation is an identity lookup, not a relevance search. A hit means the
    database holds a record for that DOI. It does NOT mean the database agrees
    the work supports any particular claim; that is what CitationClaimVerifier
    is for.

    Scope and limits:
    - Only works with a DOI can be confirmed. Web sources (Gemini Grounded /
      Serper) generally have no DOI and are reported as
      VERIFICATION_WEB_SEARCH, not as confirmed and not as refuted.
    - The three databases are not fully independent in the strict sense:
      OpenAlex and Semantic Scholar both ingest Crossref metadata. Agreement
      across them is meaningful evidence that a DOI is registered and indexed,
      but it is not three separately sourced attestations of the same facts.
      Do not describe it as more than it is.
    """

    def __init__(
        self,
        crossref_client: Optional[Any] = None,
        openalex_client: Optional[Any] = None,
        semantic_scholar_client: Optional[Any] = None,
        min_confirming_sources: int = 2,
        title_similarity_threshold: float = TITLE_SIMILARITY_THRESHOLD,
        max_workers: int = 3,
    ):
        """
        Initialize the confirmer.

        Args:
            crossref_client: CrossrefClient, or None if Crossref is disabled
            openalex_client: OpenAlexClient, or None if OpenAlex is disabled
            semantic_scholar_client: SemanticScholarClient, or None if disabled
            min_confirming_sources: How many distinct databases must hold the
                DOI for VERIFICATION_MULTI_SOURCE (default 2)
            title_similarity_threshold: Minimum token overlap for a returned
                record to count as the same work
            max_workers: Parallel confirmation lookups
        """
        self._clients: Dict[str, Any] = {}
        if crossref_client is not None:
            self._clients["Crossref"] = crossref_client
        if openalex_client is not None:
            self._clients["OpenAlex"] = openalex_client
        if semantic_scholar_client is not None:
            self._clients["Semantic Scholar"] = semantic_scholar_client

        # Fewer than 2 is not multi-source by definition. Honouring a 1 (or
        # silently clamping it) would stamp multi_source_confirmed onto a
        # citation only one database knows about, which is exactly the
        # overstatement this class exists to prevent.
        if min_confirming_sources < 2:
            raise ValueError(
                f"min_confirming_sources must be at least 2, got {min_confirming_sources}. "
                f"Confirmation by a single database is not multi-source confirmation. "
                f"To accept single-source citations, set require_multi_source=False on "
                f"CitationResearcher; those citations are then tagged "
                f"'{VERIFICATION_NOT_CHECKED}' instead of being labelled confirmed."
            )

        self.min_confirming_sources = min_confirming_sources
        self.title_similarity_threshold = title_similarity_threshold
        self.max_workers = max_workers

        # Cache keyed by (source, normalized doi) so the same DOI is not looked
        # up repeatedly within a run.
        self._lookup_cache: Dict[tuple, Optional[Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

    @property
    def available_sources(self) -> List[str]:
        """Scholarly databases actually wired up, in canonical order."""
        return [name for name in SCHOLARLY_SOURCES if name in self._clients]

    @property
    def can_reach_threshold(self) -> bool:
        """
        Whether enough databases are enabled to ever reach the threshold.

        If this is False, requiring multi-source confirmation would reject
        every citation, which is a configuration error rather than a finding.
        """
        return len(self.available_sources) >= self.min_confirming_sources

    def _lookup(self, source: str, doi: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Look up a DOI in one database, with per-run caching.

        Returns:
            (record, reachable). record is None both when the database has no
            such DOI and when the lookup failed, so the second element carries
            the difference. A failed lookup is NOT evidence of absence, and the
            caller must not record it as such.
        """
        cache_key = (source, doi)
        with self._cache_lock:
            if cache_key in self._lookup_cache:
                return self._lookup_cache[cache_key]

        client = self._clients.get(source)
        result: Optional[Dict[str, Any]] = None
        reachable = True
        if client is not None:
            try:
                result = client.get_paper_by_doi(doi)
            except Exception as e:
                # A network or parsing failure is not a refutation.
                logger.warning(f"{source}: DOI confirmation lookup failed for '{doi}': {e}")
                result = None
                reachable = False

        with self._cache_lock:
            self._lookup_cache[cache_key] = (result, reachable)
        return (result, reachable)

    def confirm(
        self,
        metadata: Dict[str, Any],
        found_by: Optional[str] = None,
    ) -> ConfirmationResult:
        """
        Confirm one candidate citation across the enabled scholarly databases.

        Args:
            metadata: Candidate metadata dict (needs "doi" and "title")
            found_by: Name of the source that originally produced this
                candidate. Counts toward confirmation only if it is one of
                SCHOLARLY_SOURCES.

        Returns:
            ConfirmationResult describing what was checked and what agreed
        """
        doi = normalize_doi(metadata.get("doi"))
        title = metadata.get("title", "")

        if not doi:
            # No DOI means no identity to look up. Web-search results land here.
            # confirming_sources stays empty: the finder is not a scholarly
            # database, so listing it there would overstate what was checked.
            finder_note = f" Found by {found_by}." if found_by else ""
            return ConfirmationResult(
                status=VERIFICATION_WEB_SEARCH,
                confirming_sources=[],
                independently_confirmed_by=[],
                checked_sources=[],
                doi="",
                notes=(
                    "No DOI on the candidate, so no scholarly database was queried for it. "
                    "Zero scholarly databases confirmed this source." + finder_note
                ),
            )

        confirming: Set[str] = set()
        finder: Optional[str] = None
        if found_by in SCHOLARLY_SOURCES and found_by in self._clients:
            # The database that returned this record already holds it. This is
            # the finder's own assertion, not something re-checked here.
            confirming.add(found_by)
            finder = found_by

        independently_confirmed: Set[str] = set()
        failed: Set[str] = set()
        to_check = [s for s in self.available_sources if s not in confirming]

        if to_check:
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(to_check))) as executor:
                futures = {executor.submit(self._lookup, source, doi): source for source in to_check}
                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        record, reachable = future.result()
                    except Exception as e:
                        logger.warning(f"{source}: confirmation future failed for '{doi}': {e}")
                        failed.add(source)
                        continue
                    if not reachable:
                        # Unreachable, so this database expressed no opinion.
                        failed.add(source)
                        continue
                    if not record:
                        continue

                    similarity = title_similarity(title, record.get("title"))
                    if similarity >= self.title_similarity_threshold:
                        confirming.add(source)
                        independently_confirmed.add(source)
                    else:
                        # Same DOI, materially different title. Do not count it,
                        # and leave a trace, because this usually means one side
                        # returned the wrong record.
                        logger.warning(
                            f"{source}: DOI '{doi}' resolved to a title that does not match "
                            f"(similarity {similarity:.2f} < {self.title_similarity_threshold:.2f}): "
                            f"'{str(record.get('title'))[:80]}' vs '{str(title)[:80]}'"
                        )

        ordered_failed = [s for s in SCHOLARLY_SOURCES if s in failed]
        # A database that errored was NOT checked. Excluding it here keeps
        # checked_sources from claiming a lookup that never returned an answer.
        checked = sorted((set(self.available_sources) - failed) | confirming)
        ordered_confirming = [s for s in SCHOLARLY_SOURCES if s in confirming]
        ordered_independent = [s for s in SCHOLARLY_SOURCES if s in independently_confirmed]

        # "No record" must be phrased so it only covers databases that actually
        # answered. Anything unreachable is reported separately as unknown.
        absent_phrase = (
            "no other reachable scholarly database returned a record for this DOI"
            if ordered_failed else
            "no other scholarly database returned a record for this DOI"
        )

        # Describe the finder separately so the note never implies this class
        # re-checked a source it only took on trust.
        if finder:
            provenance = f"found by {finder}"
            if ordered_independent:
                provenance += f"; independently confirmed by {', '.join(ordered_independent)}"
            else:
                provenance += f"; {absent_phrase}"
        elif ordered_independent:
            provenance = f"independently confirmed by {', '.join(ordered_independent)}"
        else:
            provenance = absent_phrase

        if ordered_failed:
            provenance += (
                f"; NOT REACHED (lookup failed, verdict provisional): "
                f"{', '.join(ordered_failed)}"
            )

        if len(ordered_confirming) >= self.min_confirming_sources:
            status = VERIFICATION_MULTI_SOURCE
            notes = (
                f"DOI held by {len(ordered_confirming)} scholarly databases "
                f"({', '.join(ordered_confirming)}): {provenance}."
            )
        elif ordered_confirming:
            status = VERIFICATION_SINGLE_SOURCE
            notes = (
                f"DOI held by exactly 1 scholarly database "
                f"({', '.join(ordered_confirming)}): {provenance}."
            )
        else:
            # Zero databases. This must NOT be reported as single_source, which
            # positively asserts that one database holds the record.
            status = VERIFICATION_UNCONFIRMED
            notes = f"DOI held by 0 scholarly databases: {provenance}."

        return ConfirmationResult(
            status=status,
            confirming_sources=ordered_confirming,
            independently_confirmed_by=ordered_independent,
            checked_sources=checked,
            failed_sources=ordered_failed,
            doi=doi,
            notes=notes,
        )

    def close(self) -> None:
        """Close nothing; clients are owned by the orchestrator that built them."""
        return None
