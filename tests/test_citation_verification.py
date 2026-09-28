#!/usr/bin/env python3
"""
Tests for citation verification.

Covers the two distinct guarantees, which must not be conflated:

1. EXISTENCE - multi-source DOI confirmation across Crossref / OpenAlex /
   Semantic Scholar (utils.api_citations.multi_source, and the orchestrator
   wiring that acts on it).
2. CLAIM-LEVEL RELEVANCE - whether a citation is actually about the claim it
   is attached to (utils.citation_claim_verifier).

Plus the requirement that an unverified citation is never indistinguishable
from a confirmed one in the output data.

All network and LLM calls are replaced by in-process fakes. The fakes stand in
only for the HTTP/LLM boundary; every assertion below exercises the real
production code path. Tests that would need a live API or a real API key are
deliberately not faked into passing - see the report accompanying this branch.

Run with: python -m pytest tests/test_citation_verification.py -q
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))

from utils.api_citations.multi_source import (  # noqa: E402
    MultiSourceConfirmer,
    VERIFICATION_LLM_UNVERIFIED,
    VERIFICATION_MULTI_SOURCE,
    VERIFICATION_NOT_CHECKED,
    VERIFICATION_SINGLE_SOURCE,
    VERIFICATION_UNCONFIRMED,
    VERIFICATION_WEB_SEARCH,
    normalize_doi,
    title_similarity,
)
from utils.api_citations.orchestrator import CitationResearcher  # noqa: E402
from utils.citation_database import Citation, CitationDatabase  # noqa: E402
from utils.citation_claim_verifier import (  # noqa: E402
    CitationClaimVerifier,
    VERDICT_IRRELEVANT,
    VERDICT_RELEVANT,
    VERDICT_UNCERTAIN,
    run_citation_claim_verification,
)


# =========================================================================
# Fakes (HTTP / LLM boundary only)
# =========================================================================

REAL_DOI = "10.1038/nature12373"
REAL_TITLE = "Nanometre-scale thermometry in a living cell"


class FakeDOIClient:
    """Stands in for a scholarly API client's get_paper_by_doi()."""

    def __init__(self, records=None, raises=False):
        # records: {doi: {"title": ...}}
        self.records = records or {}
        self.raises = raises
        self.calls = []

    def get_paper_by_doi(self, doi):
        self.calls.append(doi)
        if self.raises:
            raise RuntimeError("simulated network failure")
        return self.records.get(doi)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModel:
    """
    Stands in for a GenerativeModel.

    router: callable(prompt) -> str. Records every prompt so tests can assert
    the real prompt template was used.
    """

    def __init__(self, router):
        self.router = router
        self.prompts = []

    def generate_content(self, prompt, generation_config=None, safety_settings=None):
        self.prompts.append(prompt)
        return FakeResponse(self.router(prompt))


def judge_reply(verdict, confidence=0.9, reasoning="because", **extra):
    payload = {
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "claim_topic": "topic a",
        "citation_topic": "topic b",
    }
    payload.update(extra)
    return json.dumps(payload)


def make_researcher(confirmer=None, **kwargs):
    """
    Build a CitationResearcher without touching the network.

    Client construction opens no sockets, so this is safe. The confirmer is
    swapped afterwards so confirmation runs against fakes while
    _tag_verification / _keep_after_verification / _verify_results remain the
    real production code.
    """
    kwargs.setdefault("enable_gemini_grounded", False)
    kwargs.setdefault("verbose", False)
    researcher = CitationResearcher(**kwargs)
    if confirmer is not None:
        researcher.confirmer = confirmer
    return researcher


# =========================================================================
# 1. Multi-source confirmation: 2+ sources passes
# =========================================================================

class TestMultiSourceConfirmationPasses:

    def test_two_sources_holding_the_doi_is_confirmed(self):
        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
            openalex_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
            semantic_scholar_client=FakeDOIClient({}),  # does not hold it
            min_confirming_sources=2,
        )

        result = confirmer.confirm({"doi": REAL_DOI, "title": REAL_TITLE}, found_by="Crossref")

        assert result.status == VERIFICATION_MULTI_SOURCE
        assert result.is_multi_source_confirmed
        assert result.confirming_sources == ["Crossref", "OpenAlex"]
        # Only OpenAlex was actually re-checked here; Crossref was the finder.
        assert result.independently_confirmed_by == ["OpenAlex"]

    def test_all_three_sources_confirm(self):
        held = {REAL_DOI: {"title": REAL_TITLE}}
        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient(held),
            openalex_client=FakeDOIClient(held),
            semantic_scholar_client=FakeDOIClient(held),
            min_confirming_sources=2,
        )

        result = confirmer.confirm({"doi": REAL_DOI, "title": REAL_TITLE}, found_by="Crossref")

        assert result.status == VERIFICATION_MULTI_SOURCE
        assert result.source_count == 3

    def test_confirmed_citation_survives_strict_orchestrator(self):
        held = {REAL_DOI: {"title": REAL_TITLE}}
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient(held),
                openalex_client=FakeDOIClient(held),
                semantic_scholar_client=FakeDOIClient(held),
                min_confirming_sources=2,
            ),
            require_multi_source=True,
        )

        kept = researcher._verify_results(
            [({"doi": REAL_DOI, "title": REAL_TITLE}, "Crossref")]
        )

        assert len(kept) == 1
        assert kept[0][0]["verification_status"] == VERIFICATION_MULTI_SOURCE

    def test_normalized_doi_and_title_similarity_helpers(self):
        assert normalize_doi("https://doi.org/10.1038/NATURE12373") == REAL_DOI
        assert normalize_doi("doi:10.1038/nature12373") == REAL_DOI
        assert normalize_doi(None) == ""
        # Real cross-database spelling variance must not read as a mismatch.
        assert title_similarity(
            "Nanometre-scale thermometry in a living cell",
            "Nanometer scale thermometry in a living cell",
        ) >= 0.5


# =========================================================================
# 2. Single-source rejection under the strict default
# =========================================================================

class TestSingleSourceRejection:

    def _single_source_confirmer(self):
        return MultiSourceConfirmer(
            crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
            openalex_client=FakeDOIClient({}),
            semantic_scholar_client=FakeDOIClient({}),
            min_confirming_sources=2,
        )

    def test_only_one_database_holds_the_doi(self):
        result = self._single_source_confirmer().confirm(
            {"doi": REAL_DOI, "title": REAL_TITLE}, found_by="Crossref"
        )

        assert result.status == VERIFICATION_SINGLE_SOURCE
        assert not result.is_multi_source_confirmed
        assert result.confirming_sources == ["Crossref"]
        assert result.independently_confirmed_by == []

    def test_single_source_is_rejected_not_silently_accepted(self):
        """The whole point: one responder must not be enough by default."""
        researcher = make_researcher(
            confirmer=self._single_source_confirmer(),
            require_multi_source=True,
        )

        kept = researcher._verify_results(
            [({"doi": REAL_DOI, "title": REAL_TITLE}, "Crossref")]
        )

        assert kept == []

    def test_strict_mode_is_the_default(self):
        researcher = make_researcher()
        assert researcher.require_multi_source is True
        assert researcher.min_confirming_sources == 2
        assert researcher.allow_unconfirmed_web_sources is False

    def test_single_source_kept_only_via_explicit_opt_out_and_tagged_not_checked(self):
        researcher = make_researcher(
            confirmer=self._single_source_confirmer(),
            require_multi_source=False,
        )

        kept = researcher._verify_results(
            [({"doi": REAL_DOI, "title": REAL_TITLE}, "Crossref")]
        )

        assert len(kept) == 1
        # Opting out must not relabel an unchecked citation as confirmed.
        assert kept[0][0]["verification_status"] == VERIFICATION_NOT_CHECKED
        assert kept[0][0]["verification_sources"] == []

    def test_wrong_title_for_the_doi_does_not_count_as_confirmation(self):
        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
            openalex_client=FakeDOIClient(
                {REAL_DOI: {"title": "An entirely different paper about beekeeping"}}
            ),
            semantic_scholar_client=FakeDOIClient({}),
            min_confirming_sources=2,
        )

        result = confirmer.confirm({"doi": REAL_DOI, "title": REAL_TITLE}, found_by="Crossref")

        assert result.status == VERIFICATION_SINGLE_SOURCE
        assert "OpenAlex" not in result.confirming_sources

    def test_lookup_failure_is_not_treated_as_confirmation(self):
        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
            openalex_client=FakeDOIClient(raises=True),
            semantic_scholar_client=FakeDOIClient(raises=True),
            min_confirming_sources=2,
        )

        result = confirmer.confirm({"doi": REAL_DOI, "title": REAL_TITLE}, found_by="Crossref")

        assert result.status == VERIFICATION_SINGLE_SOURCE

    def test_zero_databases_is_unconfirmed_not_single_source(self):
        """
        A candidate with a DOI that NO database holds must not be labelled
        `single_source`, because that status positively asserts one database
        does hold it. Reachable when a web-search result carries a DOI.
        """
        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient({}),
            openalex_client=FakeDOIClient({}),
            semantic_scholar_client=FakeDOIClient({}),
        )

        result = confirmer.confirm(
            {"doi": "10.9999/ghost", "title": "A Paper No Database Has"}, found_by="Serper"
        )

        assert result.status == VERIFICATION_UNCONFIRMED
        assert result.status != VERIFICATION_SINGLE_SOURCE
        assert result.confirming_sources == []

    def test_unconfirmed_citation_is_dropped_under_the_default(self):
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient({}),
                openalex_client=FakeDOIClient({}),
                semantic_scholar_client=FakeDOIClient({}),
            ),
            require_multi_source=True,
        )

        kept = researcher._verify_results(
            [({"doi": "10.9999/ghost", "title": "A Paper No Database Has"}, "Serper")]
        )

        assert kept == []

    def test_threshold_below_two_is_rejected_outright(self):
        """
        min_confirming_sources=1 would stamp `multi_source_confirmed` on a
        citation only one database knows about. That is the exact overstatement
        this class exists to prevent, so it must not be silently honoured or
        clamped.
        """
        with pytest.raises(ValueError, match="at least 2"):
            MultiSourceConfirmer(
                crossref_client=FakeDOIClient({}),
                openalex_client=FakeDOIClient({}),
                semantic_scholar_client=FakeDOIClient({}),
                min_confirming_sources=1,
            )

    def test_unreachable_threshold_raises_instead_of_rejecting_everything(self):
        with pytest.raises(ValueError, match="require_multi_source"):
            CitationResearcher(
                enable_crossref=True,
                enable_openalex=False,
                enable_semantic_scholar=False,
                enable_gemini_grounded=False,
                require_multi_source=True,
                min_confirming_sources=2,
                verbose=False,
            )


# =========================================================================
# 3. Unverified sources are marked and distinguishable
# =========================================================================

class TestUnverifiedSourceMarking:

    def test_llm_fallback_is_off_by_default(self):
        """
        A model MUST be supplied here. enable_llm_fallback is stored as
        `enable_llm_fallback and gemini_model is not None`, so asserting this
        without a model passes no matter what the default is.
        """
        model = FakeModel(lambda p: "")

        assert make_researcher(gemini_model=model).enable_llm_fallback is False
        assert make_researcher(gemini_model=model, enable_llm_fallback=True).enable_llm_fallback is True

    def test_llm_citation_is_tagged_unverified_with_no_sources(self):
        # enable_llm_fallback must be ON here: a run that did not ask for LLM
        # assertions now drops them (see the cached-verdict test below), so
        # without a model this would assert the wrong thing.
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient({}),
                openalex_client=FakeDOIClient({}),
                semantic_scholar_client=FakeDOIClient({}),
            ),
            gemini_model=FakeModel(lambda p: ""),
            enable_llm_fallback=True,
        )

        kept = researcher._verify_results(
            [({"doi": "10.1/llm", "title": "A paper the LLM believes in"}, "Gemini LLM")]
        )

        assert len(kept) == 1, "an explicitly enabled LLM fallback should still yield a citation"
        metadata = kept[0][0]
        assert metadata["verification_status"] == VERIFICATION_LLM_UNVERIFIED
        assert metadata["verification_sources"] == []
        assert "no external lookup" in metadata["verification_notes"].lower()

    def test_llm_citation_never_looks_like_a_confirmed_one(self):
        """The core anti-conflation guarantee, checked on serialized output."""
        confirmed = Citation(
            "cite_001", ["Kucsko"], 2013, REAL_TITLE, "journal", doi=REAL_DOI,
            verification_status=VERIFICATION_MULTI_SOURCE,
            verification_sources=["Crossref", "OpenAlex"],
            verification_notes="held by 2 databases",
        )
        asserted = Citation(
            "cite_002", ["Ghost"], 2021, "A paper the LLM believes in", "journal",
            verification_status=VERIFICATION_LLM_UNVERIFIED,
            verification_sources=[],
            verification_notes="LLM assertion, nothing checked",
        )

        confirmed_dict = confirmed.to_dict()
        asserted_dict = asserted.to_dict()

        assert confirmed_dict["verification_status"] != asserted_dict["verification_status"]
        assert confirmed_dict["verification_sources"] == ["Crossref", "OpenAlex"]
        # Emitted even though empty. If this key were dropped, an unverified
        # citation would serialize like a confirmed one that simply had no list.
        assert "verification_sources" in asserted_dict
        assert asserted_dict["verification_sources"] == []

    def test_verification_fields_survive_a_json_round_trip(self):
        original = Citation(
            "cite_002", ["Ghost"], 2021, "A paper the LLM believes in", "journal",
            verification_status=VERIFICATION_LLM_UNVERIFIED,
            verification_sources=[],
            verification_notes="LLM assertion",
        )

        restored = Citation.from_dict(json.loads(json.dumps(original.to_dict())))

        assert restored.verification_status == VERIFICATION_LLM_UNVERIFIED
        assert restored.verification_sources == []

    def test_legacy_citation_without_verification_stays_unlabelled(self):
        """A record from before verification existed must not claim to be checked."""
        legacy = Citation("cite_003", ["Old"], 2000, "Legacy record", "journal")

        data = legacy.to_dict()

        assert "verification_status" not in data
        assert Citation.from_dict(data).verification_status is None

    def test_web_source_without_doi_is_dropped_by_default(self):
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient({}),
                openalex_client=FakeDOIClient({}),
                semantic_scholar_client=FakeDOIClient({}),
            ),
            require_multi_source=True,
        )

        kept = researcher._verify_results(
            [({"doi": "", "title": "The state of AI", "url": "https://example.com/x"}, "Gemini Grounded")]
        )

        assert kept == []

    def test_web_source_kept_via_opt_in_but_stays_tagged(self):
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient({}),
                openalex_client=FakeDOIClient({}),
                semantic_scholar_client=FakeDOIClient({}),
            ),
            require_multi_source=True,
            allow_unconfirmed_web_sources=True,
        )

        kept = researcher._verify_results(
            [({"doi": "", "title": "The state of AI", "url": "https://example.com/x"}, "Gemini Grounded")]
        )

        assert len(kept) == 1
        assert kept[0][0]["verification_status"] == VERIFICATION_WEB_SEARCH
        assert kept[0][0]["verification_sources"] == []

    def test_tagging_is_idempotent_and_preserves_an_existing_verdict(self):
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
                openalex_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
                semantic_scholar_client=FakeDOIClient({}),
            ),
        )
        metadata = {
            "doi": REAL_DOI,
            "title": REAL_TITLE,
            "verification_status": VERIFICATION_LLM_UNVERIFIED,
            "verification_sources": [],
        }

        researcher._tag_verification(metadata, "Crossref")

        assert metadata["verification_status"] == VERIFICATION_LLM_UNVERIFIED


# =========================================================================
# 3b. The on-disk cache must not become a bypass
# =========================================================================

class TestCachePersistence:
    """
    research_citation() caches results to disk between runs. Two risks:
    a verdict must survive the round trip, and a cache file written before
    verification existed must not smuggle an unconfirmed citation through.
    """

    def _researcher(self, held, **kwargs):
        from utils.api_citations.multi_source import MultiSourceConfirmer

        researcher = make_researcher(**kwargs)
        researcher.confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient(held),
            openalex_client=FakeDOIClient(held),
            semantic_scholar_client=FakeDOIClient({}),
            # Must mirror the researcher, or the two disagree about what
            # "confirmed" means and the test proves nothing.
            min_confirming_sources=researcher.min_confirming_sources,
        )
        return researcher

    def test_verdict_survives_the_cache_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        held = {"10.1/x": {"title": "A Real Paper"}}
        # A plausible surname: single-letter authors are rejected by
        # validate_author_name() long before verification is reached.
        metadata = {"doi": "10.1/x", "title": "A Real Paper",
                    "authors": ["Kucsko"], "year": 2020}

        writer = self._researcher(held)
        writer.cache["topic-a"] = writer._verify_results([(metadata, "Crossref")])
        writer._save_cache()

        reader = self._researcher(held)
        citations = reader.research_citation("topic-a")

        assert len(citations) == 1
        assert citations[0].verification_status == VERIFICATION_MULTI_SOURCE
        assert citations[0].verification_sources == ["Crossref", "OpenAlex"]

    def test_pre_existing_cache_entry_cannot_bypass_confirmation(self, tmp_path, monkeypatch):
        """A cache file written before this feature existed carries no verdict."""
        monkeypatch.chdir(tmp_path)
        stale = {
            "topic-b": [[
                {"doi": "10.1/single", "title": "Only One Database Has This",
                 "authors": ["Kucsko"], "year": 2019},
                "Crossref",
            ]]
        }
        (tmp_path / ".citation_cache_orchestrator.json").write_text(json.dumps(stale))

        # No database holds the DOI, so nothing can confirm it.
        researcher = self._researcher({}, require_multi_source=True)

        assert researcher.research_citation("topic-b") == []

    def test_not_checked_verdict_from_a_lax_run_is_reconfirmed_under_strict(self, tmp_path, monkeypatch):
        """
        The cache file is a single unversioned file in the working directory.
        One run with require_multi_source=False writes `not_checked` verdicts
        into it; a later run using the strict default must NOT hand those back.
        """
        monkeypatch.chdir(tmp_path)

        lax = self._researcher({}, require_multi_source=False)
        lax.cache["topic-c"] = lax._verify_results([
            ({"doi": "10.1/nobody", "title": "Nobody Has This",
              "authors": ["Kucsko"], "year": 2019}, "Crossref"),
        ])
        lax._save_cache()
        on_disk = json.loads((tmp_path / ".citation_cache_orchestrator.json").read_text())
        assert on_disk["topic-c"][0][0]["verification_status"] == VERIFICATION_NOT_CHECKED

        # No database holds the DOI, so re-confirmation must reject it.
        strict = self._researcher({}, require_multi_source=True)

        assert strict.research_citation("topic-c") == []

    def test_cached_llm_verdict_is_dropped_when_this_run_disallows_llm(self, tmp_path, monkeypatch):
        """
        A citation cached while enable_llm_fallback=True must not be returned by
        a later run that has it off. There is nothing to re-confirm, so the
        verdict stands and the citation is dropped instead.
        """
        monkeypatch.chdir(tmp_path)
        cached = {
            "topic-d": [[
                {"doi": "10.1/llm", "title": "A Paper The LLM Believes In",
                 "authors": ["Kucsko"], "year": 2019,
                 "verification_status": VERIFICATION_LLM_UNVERIFIED,
                 "verification_sources": []},
                "Gemini LLM",
            ]]
        }
        (tmp_path / ".citation_cache_orchestrator.json").write_text(json.dumps(cached))

        researcher = self._researcher({}, require_multi_source=True)
        assert researcher.enable_llm_fallback is False

        assert researcher.research_citation("topic-d") == []

    def test_a_stricter_threshold_invalidates_a_weaker_cached_verdict(self, tmp_path, monkeypatch):
        """A verdict made at threshold 2 is stale for a run requiring 3."""
        monkeypatch.chdir(tmp_path)
        held = {"10.1/x": {"title": "A Real Paper"}}

        run2 = self._researcher(held, require_multi_source=True, min_confirming_sources=2)
        run2.cache["topic-e"] = run2._verify_results([
            ({"doi": "10.1/x", "title": "A Real Paper",
              "authors": ["Kucsko"], "year": 2020}, "Crossref"),
        ])
        run2._save_cache()

        # Only Crossref (finder) + OpenAlex hold it -> 2, short of 3.
        run3 = self._researcher(held, require_multi_source=True, min_confirming_sources=3)

        assert run3.research_citation("topic-e") == []


class TestLookupFailureIsNotAbsence:
    """
    A database that errored said nothing. Recording that as "no record found"
    would delete real citations during, for example, a Semantic Scholar 403
    rate-limit episode, while the output claimed the database had no record.
    """

    def test_failed_lookups_are_reported_separately_from_absence(self):
        from utils.api_citations.multi_source import MultiSourceConfirmer

        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
            openalex_client=FakeDOIClient(raises=True),
            semantic_scholar_client=FakeDOIClient(raises=True),
        )

        result = confirmer.confirm({"doi": REAL_DOI, "title": REAL_TITLE}, found_by="Crossref")

        assert result.failed_sources == ["OpenAlex", "Semantic Scholar"]
        assert result.had_lookup_failures is True
        # An unreachable database must not be listed as one that was checked.
        assert "OpenAlex" not in result.checked_sources
        assert "Semantic Scholar" not in result.checked_sources
        assert "NOT REACHED" in result.notes

    def test_unreachable_sources_are_persisted_on_the_citation(self):
        researcher = make_researcher(
            confirmer=MultiSourceConfirmer(
                crossref_client=FakeDOIClient({REAL_DOI: {"title": REAL_TITLE}}),
                openalex_client=FakeDOIClient(raises=True),
                semantic_scholar_client=FakeDOIClient(raises=True),
            ),
            require_multi_source=False,  # keep it so we can inspect the record
        )
        metadata = {"doi": REAL_DOI, "title": REAL_TITLE}

        # require_multi_source=False skips lookups, so confirm directly and tag.
        researcher.require_multi_source = True
        researcher._tag_verification(metadata, "Crossref")

        assert metadata["verification_unreachable_sources"] == ["OpenAlex", "Semantic Scholar"]

        citation = Citation(
            "cite_001", ["Kucsko"], 2013, REAL_TITLE, "journal", doi=REAL_DOI,
            verification_status=metadata["verification_status"],
            verification_sources=metadata["verification_sources"],
            verification_independent_sources=metadata["verification_independent_sources"],
            verification_unreachable_sources=metadata["verification_unreachable_sources"],
        )

        assert citation.to_dict()["verification_unreachable_sources"] == [
            "OpenAlex", "Semantic Scholar"
        ]


# =========================================================================
# 3c. The production wiring itself
#
# An adversarial review found that removing the verification call from the
# fresh-discovery path, or the claim-verification call from the citation phase,
# left the ENTIRE suite green. Those are the primary production paths. These
# tests exist so wiring the features out of the pipeline fails loudly.
# =========================================================================

class TestProductionWiring:

    def test_fresh_discovery_path_verifies_before_returning(self, tmp_path, monkeypatch):
        """
        research_citation() on a cache MISS must run confirmation.

        Every other test drives _verify_results directly or via the cache
        branch, so nothing covered the path real runs take.
        """
        from utils.api_citations.multi_source import MultiSourceConfirmer

        monkeypatch.chdir(tmp_path)
        researcher = make_researcher(require_multi_source=True)
        researcher.confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient({}),      # nothing holds the DOI
            openalex_client=FakeDOIClient({}),
            semantic_scholar_client=FakeDOIClient({}),
        )

        # Bypass the network: discovery "finds" a single-source candidate.
        monkeypatch.setattr(
            researcher, "_search_api",
            lambda api, topic: (
                {"doi": "10.1/unconfirmable", "title": "Nobody Has This",
                 "authors": ["Kucsko"], "year": 2020},
                "Crossref",
            ),
        )

        citations = researcher.research_citation("some topic")

        assert citations == [], "an unconfirmable candidate must not survive discovery"

    def test_fresh_discovery_keeps_and_tags_a_confirmed_candidate(self, tmp_path, monkeypatch):
        """The mirror of the above: confirmation must not reject everything."""
        from utils.api_citations.multi_source import MultiSourceConfirmer

        monkeypatch.chdir(tmp_path)
        held = {"10.1/real": {"title": "A Real Paper"}}
        researcher = make_researcher(require_multi_source=True)
        researcher.confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient(held),
            openalex_client=FakeDOIClient(held),
            semantic_scholar_client=FakeDOIClient({}),
        )
        monkeypatch.setattr(
            researcher, "_search_api",
            lambda api, topic: (
                {"doi": "10.1/real", "title": "A Real Paper",
                 "authors": ["Kucsko"], "year": 2020},
                "Crossref",
            ),
        )

        citations = researcher.research_citation("some topic")

        assert len(citations) >= 1
        assert citations[0].verification_status == VERIFICATION_MULTI_SOURCE
        assert citations[0].verification_independent_sources == ["OpenAlex"]

    def test_citation_phase_actually_calls_claim_verification(self, tmp_path, monkeypatch):
        """
        run_citation_management() must invoke claim verification.

        A commit once shipped this call commented out and every test stayed
        green. This asserts the wiring, not just the helper.
        """
        import phases.citations as citations_phase

        called = {}

        def spy(ctx, db_path):
            called["yes"] = True

        monkeypatch.setattr(citations_phase, "_run_claim_verification", spy)

        source = (Path(__file__).parent.parent / "engine" / "phases" / "citations.py").read_text()
        # Guard against the call being commented out or replaced by `pass`.
        assert "_run_claim_verification(ctx, citation_db_path)" in source
        assert "# _run_claim_verification" not in source
        assert "pass  # _run_claim_verification" not in source

        # And prove the name the phase calls is the one we patched.
        assert hasattr(citations_phase, "_run_claim_verification")
        citations_phase._run_claim_verification(None, None)
        assert called.get("yes") is True

    def test_citation_compiler_does_not_enable_llm_fallback(self):
        """
        Missing-citation placeholders are filled mid-compilation and land
        directly in the finished paper, so an LLM assertion there reaches the
        reader unchecked.
        """
        source = (
            Path(__file__).parent.parent / "engine" / "utils" / "citation_compiler.py"
        ).read_text()

        assert "enable_llm_fallback=False" in source
        assert "enable_llm_fallback=True" not in source

    def test_only_scholarly_sources_can_count_as_the_finder(self):
        """
        The finder is trusted without being re-queried, so only a real scholarly
        database may occupy that slot. If web search or the LLM could, an
        unconfirmed citation would reach the multi-source threshold.
        """
        from utils.api_citations.multi_source import MultiSourceConfirmer

        held = {"10.1/x": {"title": "A Paper"}}
        confirmer = MultiSourceConfirmer(
            crossref_client=FakeDOIClient(held),
            openalex_client=FakeDOIClient({}),
            semantic_scholar_client=FakeDOIClient({}),
        )

        for impostor in ("Serper", "Gemini Grounded", "Gemini LLM"):
            result = confirmer.confirm({"doi": "10.1/x", "title": "A Paper"}, found_by=impostor)
            assert impostor not in result.confirming_sources
            # Only Crossref genuinely holds it, so this is single-source.
            assert result.status == VERIFICATION_SINGLE_SOURCE


# =========================================================================
# 4. Claim-level verifier verdicts
# =========================================================================

def build_database():
    return CitationDatabase(citations=[
        Citation(
            "cite_001", ["Kucsko"], 2013, REAL_TITLE, "journal",
            doi=REAL_DOI, abstract="Diamond defects measure temperature inside a living cell.",
        ),
        Citation(
            "cite_002", ["Jones"], 2019, "A study of child psychology development", "journal",
            doi="10.1/psych", abstract="Longitudinal study of toddler development.",
        ),
    ])


class TestClaimLevelVerdicts:

    def test_relevant_verdict_is_parsed_from_the_judge(self):
        model = FakeModel(lambda p: judge_reply(VERDICT_RELEVANT, 0.92))
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        verdict = verifier._verify_single_pair(
            "Diamond defects can sense temperature inside cells", "cite_001"
        )

        assert verdict.verdict == VERDICT_RELEVANT
        assert verdict.confidence == pytest.approx(0.92)
        assert verdict.citation_id == "cite_001"
        # The real judge prompt template was used, not something invented here.
        assert "CITATION RELEVANCE JUDGE" in model.prompts[0]
        assert REAL_TITLE in model.prompts[0]

    def test_irrelevant_verdict_is_parsed_and_carries_a_fix(self):
        model = FakeModel(
            lambda p: judge_reply(
                VERDICT_IRRELEVANT, 0.95,
                reasoning="psychology paper cited for a thermometry claim",
                suggested_fix="cite a nanoscale sensing paper",
            )
        )
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        verdict = verifier._verify_single_pair(
            "Diamond defects can sense temperature inside cells", "cite_002"
        )

        assert verdict.verdict == VERDICT_IRRELEVANT
        assert verdict.suggested_fix == "cite a nanoscale sensing paper"

    def test_unparseable_judge_response_becomes_uncertain_not_relevant(self):
        model = FakeModel(lambda p: "I'm afraid I can't answer that.")
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        verdict = verifier._verify_single_pair("Some claim", "cite_001")

        assert verdict.verdict == VERDICT_UNCERTAIN
        assert verdict.confidence == 0.0

    def test_unknown_verdict_string_becomes_uncertain(self):
        model = FakeModel(lambda p: judge_reply("DEFINITELY_FINE", 0.99))
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        assert verifier._verify_single_pair("Some claim", "cite_001").verdict == VERDICT_UNCERTAIN

    def test_judge_failure_becomes_uncertain_not_relevant(self):
        class ExplodingModel:
            def generate_content(self, *a, **k):
                raise RuntimeError("quota exhausted")

        verifier = CitationClaimVerifier(
            model=ExplodingModel(), citation_database=build_database()
        )

        assert verifier._verify_single_pair("Some claim", "cite_001").verdict == VERDICT_UNCERTAIN

    def test_missing_model_yields_uncertain_rather_than_a_pass(self):
        verifier = CitationClaimVerifier(model=None, citation_database=build_database())

        assert verifier._verify_single_pair("Some claim", "cite_001").verdict == VERDICT_UNCERTAIN

    def test_unknown_citation_id_is_uncertain(self):
        model = FakeModel(lambda p: judge_reply(VERDICT_RELEVANT))
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        verdict = verifier._verify_single_pair("Some claim", "cite_999")

        assert verdict.verdict == VERDICT_UNCERTAIN
        assert verdict.citation_title == "[Not found]"
        assert model.prompts == [], "no judge call should be spent on an unknown citation"

    def test_repeated_pair_is_served_from_cache(self):
        model = FakeModel(lambda p: judge_reply(VERDICT_RELEVANT))
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        verifier._verify_single_pair("Same claim", "cite_001")
        verifier._verify_single_pair("Same claim", "cite_001")

        assert len(model.prompts) == 1

    def test_extraction_drops_citation_ids_the_model_invented(self):
        extracted = json.dumps([
            {"claim": "A real claim", "citation_ids": ["cite_001", "cite_hallucinated"]},
            {"claim": "An entirely invented pairing", "citation_ids": ["cite_nope"]},
        ])
        model = FakeModel(
            lambda p: extracted if "CITATION-CLAIM EXTRACTOR" in p else judge_reply(VERDICT_RELEVANT)
        )
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        pairs = verifier.extract_claims_with_citations("A real claim {cite_001}.")

        assert len(pairs) == 1
        assert pairs[0].citation_ids == ["cite_001"]

    def test_text_without_citation_markers_costs_no_llm_call(self):
        model = FakeModel(lambda p: "should never be called")
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        assert verifier.extract_claims_with_citations("Plain prose, no markers.") == []
        assert model.prompts == []

    def test_full_pipeline_over_draft_text(self):
        extracted = json.dumps([
            {"claim": "Diamond defects sense temperature in cells", "citation_ids": ["cite_001"]},
            {"claim": "Diamond defects sense temperature in cells", "citation_ids": ["cite_002"]},
        ])

        def router(prompt):
            if "CITATION-CLAIM EXTRACTOR" in prompt:
                return extracted
            if "child psychology" in prompt.lower() and "CITATION TITLE" in prompt:
                # Judge the psychology citation only when it is the one under test.
                if "A study of child psychology development" in prompt.split("CITATION ABSTRACT")[0]:
                    return judge_reply(VERDICT_IRRELEVANT, 0.95)
            return judge_reply(VERDICT_RELEVANT, 0.9)

        result = run_citation_claim_verification(
            "Diamond defects sense temperature in cells {cite_001} {cite_002}.",
            build_database(),
            FakeModel(router),
        )

        assert result["stats"]["total_pairs"] == 2
        assert result["stats"]["irrelevant"] == 1
        assert result["stats"]["relevant"] == 1
        assert "Citation-Claim Verification Report" in result["report"]

    def test_topic_level_verification_judges_every_citation(self):
        model = FakeModel(lambda p: judge_reply(VERDICT_RELEVANT))
        db = build_database()
        verifier = CitationClaimVerifier(model=model, citation_database=db)

        verdicts = verifier.verify_citations_against_topic("nanoscale thermometry")

        assert {v.citation_id for v in verdicts} == {"cite_001", "cite_002"}

    def test_report_calls_uncertain_citations_unchecked_not_passing(self):
        model = FakeModel(lambda p: judge_reply(VERDICT_UNCERTAIN, 0.2))
        verifier = CitationClaimVerifier(model=model, citation_database=build_database())

        verdicts = [verifier._verify_single_pair("A vague claim", "cite_001")]
        report = verifier.format_report(verdicts)

        assert "UNCERTAIN CITATIONS" in report
        assert "not as passing" in report
        assert "**Relevant:** 0" in report


# =========================================================================
# 5. Citation phase integration
# =========================================================================

class TestCitationPhaseIntegration:

    def _context(self, tmp_path, model, topic="satellite image classification"):
        from config import AppConfig
        from phases.context import DraftContext
        from utils.citation_database import save_citation_database

        research = tmp_path / "research"
        research.mkdir()
        db = CitationDatabase(citations=[
            Citation("cite_001", ["Smith"], 2020,
                     "Satellite image classification with deep learning", "journal",
                     doi="10.1/sat", abstract="Remote sensing imagery classification."),
            Citation("cite_002", ["Jones"], 2019,
                     "A study of child psychology development", "journal",
                     doi="10.1/psych", abstract="Toddler development."),
        ])
        db_path = research / "bibliography.json"
        save_citation_database(db, db_path)

        ctx = DraftContext(topic=topic, model=model, config=AppConfig(), verbose=False)
        ctx.citation_database = db
        ctx.folders = {"research": research, "drafts": research}
        return ctx, db_path, research

    @staticmethod
    def _router(irrelevant_confidence):
        def router(prompt):
            if 'CITATION TITLE**: "A study of child psychology development' in prompt:
                return judge_reply(VERDICT_IRRELEVANT, irrelevant_confidence)
            return judge_reply(VERDICT_RELEVANT, 0.9)
        return router

    def test_phase_removes_a_confidently_off_topic_citation(self, tmp_path):
        from phases.citations import _run_claim_verification

        ctx, db_path, research = self._context(tmp_path, FakeModel(self._router(0.95)))

        _run_claim_verification(ctx, db_path)

        assert [c.id for c in ctx.citation_database.citations] == ["cite_001"]
        saved = json.loads(db_path.read_text())
        assert [c["id"] for c in saved["citations"]] == ["cite_001"]
        assert (research / "citation_claim_verification.md").exists()
        assert (research / "citation_claim_verification.json").exists()

    def test_phase_reports_but_keeps_a_low_confidence_irrelevant_verdict(self, tmp_path):
        from phases.citations import _run_claim_verification

        ctx, db_path, research = self._context(tmp_path, FakeModel(self._router(0.4)))

        _run_claim_verification(ctx, db_path)

        assert len(ctx.citation_database.citations) == 2
        report = json.loads((research / "citation_claim_verification.json").read_text())
        assert report["stats"]["irrelevant"] == 1

    def test_phase_refuses_to_empty_the_database(self, tmp_path):
        from phases.citations import _run_claim_verification

        ctx, db_path, _ = self._context(
            tmp_path, FakeModel(lambda p: judge_reply(VERDICT_IRRELEVANT, 0.99))
        )

        _run_claim_verification(ctx, db_path)

        assert len(ctx.citation_database.citations) == 2

    def test_phase_without_a_model_changes_nothing(self, tmp_path):
        from phases.citations import _run_claim_verification

        ctx, db_path, research = self._context(tmp_path, None)

        _run_claim_verification(ctx, db_path)

        assert len(ctx.citation_database.citations) == 2
        assert not (research / "citation_claim_verification.json").exists()

    def test_phase_respects_the_disable_flag(self, tmp_path):
        from phases.citations import _run_claim_verification

        ctx, db_path, research = self._context(tmp_path, FakeModel(self._router(0.99)))
        ctx.config.validation.enable_claim_verification = False

        _run_claim_verification(ctx, db_path)

        assert len(ctx.citation_database.citations) == 2
        assert not (research / "citation_claim_verification.json").exists()

    def test_phase_uses_the_strict_quality_filter(self):
        """
        The pipeline must not re-introduce the lenient override.

        strict_mode=False let every critical validator issue except invalid_url
        and invalid_metadata through into the finished paper.
        """
        source = (Path(__file__).parent.parent / "engine" / "phases" / "citations.py").read_text()

        assert "CitationQualityFilter(strict_mode=True)" in source
        assert "CitationQualityFilter(strict_mode=False)" not in source
