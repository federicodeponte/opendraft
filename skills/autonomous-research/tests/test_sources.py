import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "sources.py"
SPEC = importlib.util.spec_from_file_location("opendraft_sources", SCRIPT)
SOURCES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCES)


class VerifyTests(unittest.TestCase):
    def test_empty_doi_is_invalid_without_network_call(self):
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("   ")

        get.assert_not_called()
        self.assertEqual(
            result,
            {
                "doi": "",
                "status": "invalid",
                "agency": None,
                "error": "DOI is empty",
            },
        )

    def test_empty_doi_command_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "   "],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn('"status": "invalid"', result.stdout)


class MalformedDoiTests(unittest.TestCase):
    """A malformed DOI is a transcription error ("check what you typed"),
    which is different advice than "absent" ("the registries were asked and
    it does not exist, drop the citation"). Before this check, anything that
    was not an empty string went over the network to Crossref then DataCite
    and came back "absent" regardless of whether it could ever have been a
    real DOI, so agents/04-citation-manager.md's advice for "invalid" never
    fired. These prove the shape check rejects garbage before any network
    call, and does not reject a real DOI merely because its suffix looks
    unusual.
    """

    def test_garbage_string_is_invalid_without_network_call(self):
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("not-a-doi-at-all")

        get.assert_not_called()
        self.assertEqual(result["status"], "invalid")
        self.assertIn("not-a-doi-at-all", result["error"])

    def test_missing_prefix_is_invalid_without_network_call(self):
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("just some text")

        get.assert_not_called()
        self.assertEqual(result["status"], "invalid")

    def test_empty_suffix_is_invalid_without_network_call(self):
        # "10.1000/" has the DOI prefix and a registrant code but nothing
        # after the slash: exactly the shape a truncated paste produces.
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("10.1000/")

        get.assert_not_called()
        self.assertEqual(result["status"], "invalid")
        self.assertIn("10.1000/", result["error"])

    def test_missing_slash_is_invalid_without_network_call(self):
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("10.1000")

        get.assert_not_called()
        self.assertEqual(result["status"], "invalid")

    def test_non_numeric_registrant_is_invalid_without_network_call(self):
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("10.abc/suffix")

        get.assert_not_called()
        self.assertEqual(result["status"], "invalid")

    def test_empty_string_behavior_is_unchanged(self):
        # The pre-existing empty-DOI branch must still fire first, with its
        # own message, not get relabeled by the new shape check.
        with patch.object(SOURCES, "_get") as get:
            result = SOURCES.verify("   ")

        get.assert_not_called()
        self.assertEqual(
            result,
            {"doi": "", "status": "invalid", "agency": None, "error": "DOI is empty"},
        )

    def test_well_formed_doi_still_reaches_the_network(self):
        fake_response = {
            "message": {
                "title": ["A perfectly normal paper"],
                "author": [{"family": "Doe", "given": "Jane"}],
                "type": "journal-article",
                "published": {"date-parts": [[2021]]},
                "container-title": ["Journal of Examples"],
            }
        }
        with patch.object(SOURCES, "_get", return_value=fake_response) as get:
            result = SOURCES.verify("10.1038/s41586-021-03819-2")

        get.assert_called()
        self.assertEqual(result["status"], "resolved")

    def test_awkward_but_real_doi_is_not_rejected_by_shape(self):
        # DOI suffixes may legitimately contain parentheses, colons, angle
        # brackets and semicolons (ANSI/NISO Z39.84); this is a real DOI
        # shape, not a synthetic edge case.
        awkward = "10.1002/(SICI)1099-1050(199806)7:3<233::AID-HEC343>3.0.CO;2-Y"
        fake_response = {
            "message": {
                "title": ["Health economics with an awkward DOI"],
                "author": [{"family": "Smith", "given": "A."}],
                "type": "journal-article",
                "published": {"date-parts": [[1998]]},
                "container-title": ["Health Economics"],
            }
        }
        with patch.object(SOURCES, "_get", return_value=fake_response) as get:
            result = SOURCES.verify(awkward)

        get.assert_called()
        self.assertNotEqual(result["status"], "invalid")

    def test_doi_with_dot_separated_registrant_subcode_is_not_rejected(self):
        # Older DOIs sometimes carry a dot-separated registrant sub-code,
        # e.g. 10.1000.100/182 style prefixes issued by some agencies.
        with patch.object(SOURCES, "_get") as get:
            get.return_value = {
                "message": {
                    "title": ["Example"],
                    "author": [{"family": "X", "given": "Y"}],
                    "type": "journal-article",
                    "published": {"date-parts": [[2020]]},
                    "container-title": ["Journal"],
                }
            }
            result = SOURCES.verify("10.1000.100/182")

        get.assert_called()
        self.assertNotEqual(result["status"], "invalid")

    def test_malformed_doi_command_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "not-a-doi-at-all"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('"status": "invalid"', result.stdout)


class FindTests(unittest.TestCase):
    def test_openalex_doi_is_not_returned_when_it_does_not_resolve(self):
        openalex_result = {
            "doi": "https://doi.org/10.9999/unverified",
            "title": "Unverified result",
            "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
            "publication_year": 2026,
            "primary_location": {"source": {"display_name": "Example"}},
            "type": "article",
        }
        calls = []

        def fake_get(url, timeout=20):
            calls.append(url)
            if url.startswith("https://api.crossref.org/works?"):
                return {"message": {"items": []}}
            if url.startswith("https://api.openalex.org/works?"):
                return {"results": [openalex_result]}
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            result = SOURCES.find("example", n=1)

        self.assertEqual(result, [])
        self.assertTrue(
            any("api.crossref.org/works/10.9999/unverified" in url for url in calls)
        )
        self.assertTrue(
            any("api.datacite.org/dois/10.9999/unverified" in url for url in calls)
        )


class VerifyFallthroughTests(unittest.TestCase):
    """Finding 6: a non-404 Crossref error must not skip DataCite."""

    def _urls_for(self, crossref_exc):
        calls = []

        def fake_get(url, timeout=20):
            calls.append(url)
            if url.startswith("https://api.crossref.org/works/"):
                raise crossref_exc
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            result = SOURCES.verify("10.1234/abc")
        return result, calls

    def test_crossref_429_still_tries_datacite(self):
        exc = urllib.error.HTTPError(
            "https://api.crossref.org/works/10.1234/abc", 429, "too many", {}, None)
        result, calls = self._urls_for(exc)
        self.assertTrue(any("api.datacite.org/dois/10.1234/abc" in u for u in calls),
                        f"DataCite was never called: {calls}")
        self.assertEqual(result["status"], "unknown")

    def test_crossref_500_still_tries_datacite(self):
        exc = urllib.error.HTTPError(
            "https://api.crossref.org/works/10.1234/abc", 500, "boom", {}, None)
        _, calls = self._urls_for(exc)
        self.assertTrue(any("api.datacite.org" in u for u in calls))

    def test_crossref_transport_error_still_tries_datacite(self):
        _, calls = self._urls_for(urllib.error.URLError("connection refused"))
        self.assertTrue(any("api.datacite.org" in u for u in calls))

    def test_crossref_429_then_datacite_resolves(self):
        calls = []

        def fake_get(url, timeout=20):
            calls.append(url)
            if url.startswith("https://api.crossref.org/works/"):
                raise urllib.error.HTTPError(url, 429, "too many", {}, None)
            return {"data": {"attributes": {"titles": [{"title": "A Preprint"}]}}}

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            result = SOURCES.verify("10.48550/arxiv.2301.00001")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["agency"], "datacite")

    def test_crossref_429_and_datacite_404_is_unknown_never_absent(self):
        result, _ = self._urls_for(urllib.error.HTTPError(
            "https://api.crossref.org/works/10.1234/abc", 429, "too many", {}, None))
        self.assertEqual(result["status"], "unknown")

    def test_both_agencies_404_is_absent(self):
        def fake_get(url, timeout=20):
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            result = SOURCES.verify("10.1234/abc")
        self.assertEqual(result["status"], "absent")

    def test_retries_back_off(self):
        delays = []

        def fake_get(url, timeout=20):
            raise urllib.error.HTTPError(url, 429, "too many", {}, None)

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", side_effect=delays.append
        ):
            SOURCES.verify("10.1234/abc")
        self.assertTrue(delays, "expected at least one backoff sleep")
        self.assertGreater(max(delays), min(delays),
                           f"delays are flat, no backoff: {delays}")


class FindFailureExitTests(unittest.TestCase):
    """Finding 5: `find` exiting 0 with both APIs down tells the orchestrating
    model that stage 1 succeeded with zero sources."""

    def test_find_reports_hard_failure_when_every_api_raises(self):
        def fake_get(url, timeout=20):
            raise urllib.error.URLError("blackholed")

        status = {}
        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            results = SOURCES.find("anything", n=5, status=status)
        self.assertEqual(results, [])
        self.assertEqual(sorted(status["failed"]), ["crossref", "openalex"])
        self.assertEqual(sorted(status["attempted"]), ["crossref", "openalex"])

    def test_find_cli_exits_nonzero_when_every_api_raises(self):
        def fake_get(url, timeout=20):
            raise urllib.error.URLError("blackholed")

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            code = SOURCES.main(["find", "anything", "--n", "3"])
        self.assertEqual(code, 1)

    def test_find_cli_exits_zero_when_the_apis_answer_with_nothing(self):
        def fake_get(url, timeout=20):
            if url.startswith("https://api.crossref.org/works?"):
                return {"message": {"items": []}}
            if url.startswith("https://api.openalex.org/works?"):
                return {"results": []}
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            code = SOURCES.main(["find", "anything", "--n", "3"])
        self.assertEqual(code, 0)

    def test_find_cli_exits_zero_when_one_api_answers(self):
        real_item = {
            "DOI": "10.1007/979-8-8688-1808-0_1",
            "title": ["Introduction to Retrieval-Augmented Generation (RAG)"],
            "author": [{"family": "Bose", "given": "Ranajoy"}],
            "issued": {"date-parts": [[2025]]},
            "container-title": ["Mastering Retrieval-Augmented Generation"],
            "type": "book-chapter",
            "publisher": "Apress",
        }

        def fake_get(url, timeout=20):
            if url.startswith("https://api.crossref.org/works?"):
                return {"message": {"items": [real_item]}}
            raise urllib.error.URLError("openalex down")

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            code = SOURCES.main(["find", "anything", "--n", "3"])
        self.assertEqual(code, 0)


class OpenAlexDropVisibilityTests(unittest.TestCase):
    """Finding 7: an `unknown` verification must not silently erase a hit."""

    def test_dropped_openalex_hit_is_announced_on_stderr(self):
        openalex_result = {
            "doi": "https://doi.org/10.9999/unverified",
            "title": "Unverified result",
            "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
            "publication_year": 2026,
            "primary_location": {"source": {"display_name": "Example"}},
            "type": "article",
        }

        def fake_get(url, timeout=20):
            if url.startswith("https://api.crossref.org/works?"):
                return {"message": {"items": []}}
            if url.startswith("https://api.openalex.org/works?"):
                return {"results": [openalex_result]}
            raise urllib.error.HTTPError(url, 429, "too many", {}, None)

        stderr = io.StringIO()
        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ), contextlib.redirect_stderr(stderr):
            result = SOURCES.find("example", n=1)

        self.assertEqual(result, [])
        message = stderr.getvalue()
        self.assertIn("10.9999/unverified", message)
        self.assertIn("unknown", message)


class QualityFilterTests(unittest.TestCase):
    """Offline tests for the Rogue-Scholar-style blog-post rejection rule."""

    def test_rogue_scholar_front_matter_hit_is_rejected(self):
        # Real shape of 10.59350/q2pq3-0fv85 from Crossref: one author with a
        # given name on record, empty container-title, publisher "Front Matter".
        authors = [{"family": "Pi", "given": "Wenyi"}]
        self.assertTrue(SOURCES._is_low_quality(authors, "", "Front Matter"))

    def test_mononym_single_author_empty_venue_is_rejected(self):
        authors = [{"family": "Pi", "given": ""}]
        self.assertTrue(SOURCES._is_low_quality(authors, "", ""))

    def test_multi_author_empty_venue_is_kept(self):
        # Real shape of the SSRN preprint 10.2139/ssrn.5316632: four named
        # authors, empty container-title (SSRN doesn't set one), Elsevier BV.
        authors = [
            {"family": "Xue", "given": "Xingzhuo"},
            {"family": "Zhang", "given": "Guowei"},
            {"family": "Jiang", "given": "Liming"},
            {"family": "Liu", "given": "Chunyuan"},
        ]
        self.assertFalse(SOURCES._is_low_quality(authors, "", "Elsevier BV"))

    def test_single_author_with_given_name_and_empty_venue_is_kept(self):
        # A legitimate solo-author report (Iowa State, doi 10.31274/...):
        # given name on record, no blog-minting publisher.
        authors = [{"family": "Mutyala", "given": "Shalini"}]
        self.assertFalse(SOURCES._is_low_quality(authors, "", "Iowa State University"))

    def test_nonempty_venue_always_clears(self):
        authors = [{"family": "Pi", "given": ""}]
        self.assertFalse(SOURCES._is_low_quality(authors, "Some Journal", "Front Matter"))

    def test_find_drops_rogue_scholar_and_keeps_real_venue(self):
        rogue_scholar_item = {
            "DOI": "10.59350/q2pq3-0fv85",
            "title": ["Efficient Information Retrieval and Response Generation with RAG"],
            "author": [{"family": "Pi", "given": "Wenyi"}],
            "issued": {"date-parts": [[2024]]},
            "container-title": [],
            "type": "posted-content",
            "publisher": "Front Matter",
        }
        real_item = {
            "DOI": "10.1007/979-8-8688-1808-0_1",
            "title": ["Introduction to Retrieval-Augmented Generation (RAG)"],
            "author": [{"family": "Bose", "given": "Ranajoy"}],
            "issued": {"date-parts": [[2025]]},
            "container-title": ["Mastering Retrieval-Augmented Generation"],
            "type": "book-chapter",
            "publisher": "Apress",
        }

        def fake_get(url, timeout=20):
            if url.startswith("https://api.crossref.org/works?"):
                return {"message": {"items": [rogue_scholar_item, real_item]}}
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)

        with patch.object(SOURCES, "_get", side_effect=fake_get), patch.object(
            SOURCES.time, "sleep", return_value=None
        ):
            result = SOURCES.find("retrieval augmented generation", n=5)

        dois = [r["doi"] for r in result]
        self.assertNotIn("10.59350/q2pq3-0fv85", dois)
        self.assertIn("10.1007/979-8-8688-1808-0_1", dois)
        self.assertTrue(all(r["venue"] for r in result))


class NearDuplicateTests(unittest.TestCase):
    """One work deposited twice under different DOIs survives DOI dedupe.

    Live Crossref returns exactly this: an SSRN preprint posted twice, same
    title and authors, DOIs 10.2139/ssrn.5316632 and 10.2139/ssrn.5253805.
    """

    TITLE = "A Comparative Study of Retrieval-Augmented Generation"

    def _rec(self, doi, type_="posted-content", venue="", title=None):
        return {"doi": doi, "title": title if title is not None else self.TITLE,
                "authors": [{"family": "Xue", "given": "Xingzhuo"}],
                "year": 2025, "venue": venue, "type": type_, "source": "crossref"}

    def test_title_key_ignores_case_punctuation_and_spacing(self):
        self.assertEqual(
            SOURCES._title_key("Retrieval-Augmented Generation: A Study"),
            SOURCES._title_key("retrieval augmented generation a study"))

    def test_second_deposit_of_same_title_is_not_appended(self):
        out, by_title = [], {}
        SOURCES._absorb(out, by_title, self._rec("10.2139/ssrn.5316632"))
        SOURCES._absorb(out, by_title, self._rec("10.2139/ssrn.5253805"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["doi"], "10.2139/ssrn.5316632")

    def test_published_version_replaces_the_preprint_it_duplicates(self):
        out, by_title = [], {}
        SOURCES._absorb(out, by_title, self._rec("10.2139/ssrn.5316632"))
        SOURCES._absorb(out, by_title, self._rec(
            "10.1000/journal.1", type_="journal-article", venue="Fire Safety Journal"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["type"], "journal-article")
        self.assertEqual(out[0]["venue"], "Fire Safety Journal")

    def test_preprint_does_not_displace_the_published_version(self):
        out, by_title = [], {}
        SOURCES._absorb(out, by_title, self._rec(
            "10.1000/journal.1", type_="journal-article", venue="Fire Safety Journal"))
        SOURCES._absorb(out, by_title, self._rec("10.2139/ssrn.5316632"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["doi"], "10.1000/journal.1")

    def test_distinct_titles_are_both_kept(self):
        out, by_title = [], {}
        SOURCES._absorb(out, by_title, self._rec("10.1000/a", title="Chapter One"))
        SOURCES._absorb(out, by_title, self._rec("10.1000/b", title="Chapter Two"))
        self.assertEqual(len(out), 2)

    def test_untitled_records_are_never_collapsed_together(self):
        """An empty title is missing metadata, not evidence of a shared work."""
        out, by_title = [], {}
        SOURCES._absorb(out, by_title, self._rec("10.1000/a", title=""))
        SOURCES._absorb(out, by_title, self._rec("10.1000/b", title=""))
        self.assertEqual(len(out), 2)


@unittest.skipUnless(
    os.environ.get("OPENDRAFT_RUN_NETWORK_TESTS"),
    "network test: set OPENDRAFT_RUN_NETWORK_TESTS=1 to run against live Crossref/OpenAlex",
)
class LiveNetworkTests(unittest.TestCase):
    def test_rag_query_returns_no_rogue_scholar_hits(self):
        result = SOURCES.find("retrieval augmented generation", n=10)
        dois = [r["doi"] for r in result]
        self.assertTrue(result, "expected at least one result from live Crossref/OpenAlex")
        self.assertFalse(any(d.startswith("10.59350") for d in dois))
        self.assertTrue(any(r["venue"] for r in result), "expected at least one real venue")

    def test_live_results_contain_no_repeated_title(self):
        result = SOURCES.find("retrieval augmented generation", n=10)
        keys = [SOURCES._title_key(r["title"]) for r in result]
        self.assertEqual(len(keys), len(set(keys)), "same work returned twice")


if __name__ == "__main__":
    unittest.main()
