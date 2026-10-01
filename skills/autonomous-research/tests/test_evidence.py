"""scripts/evidence.py: verbatim quote checks, the evidence index, the figures.

The evidence stage exists so that every mark on every evidence figure traces to
a sentence a reader can find in the source. These tests pin the three places
that promise can quietly break: a quote that is close to the source but not in
it, an index that counts one trial twice, and figures that change between two
runs on the same input.
"""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EV = _load("opendraft_evidence", "evidence.py")
INTEGRITY = _load("opendraft_integrity_ev", "integrity.py")
CITATIONS = _load("opendraft_citations_ev", "citations.py")
ASSEMBLE = _load("opendraft_assemble_ev", "assemble.py")

DOI_A = "10.1000/trial.one"
DOI_B = "10.1000/trial.two"
DOI_C = "10.1000/survey"

ABSTRACTS = {
    DOI_A: {"abstract": "Reduced hours improved sleep quality and lowered stress. Output was unchanged."},
    DOI_B: {"abstract": "In the same trial, burnout fell by a third among nurses."},
    DOI_C: {"abstract": "Respondents reported “mixed” effects on workload \u2014 some gained, some did not."},
}


def studies():
    return [
        {"doi": DOI_A, "label": "Alpha et al. 2020", "country": "Sweden", "design": "Cluster RCT",
         "tier": 3, "n": 600, "type": "Reduced hours", "trial": "Trial X",
         "outcomes": {"wellbeing": ["+", "Reduced hours improved sleep quality"],
                      "productivity": ["0", "Output was unchanged."]}},
        {"doi": DOI_B, "label": "Beta et al. 2021", "country": "Sweden", "design": "Cluster RCT",
         "tier": 3, "n": 580, "type": "Reduced hours", "trial": "Trial X",
         "outcomes": {"wellbeing": ["+", "burnout fell by a third"]}},
        {"doi": DOI_C, "label": "Gamma 2022", "country": "UK", "design": "Cross-sectional survey",
         "tier": 1, "n": None, "type": "Compressed",
         "outcomes": {"wellbeing": ["~", 'Respondents reported "mixed" effects on workload - some gained']}},
    ]


class QuoteCheckTests(unittest.TestCase):

    def test_real_quotes_pass_including_quote_and_dash_style(self):
        self.assertEqual(EV.schema_problems(studies()), [])
        self.assertEqual(EV.quote_problems(studies(), ABSTRACTS), [])

    def test_a_paraphrase_fails_and_is_named(self):
        s = studies()
        s[0]["outcomes"]["wellbeing"][1] = "Reduced hours improved sleep"  # still a substring
        self.assertEqual(EV.quote_problems(s, ABSTRACTS), [])
        s[0]["outcomes"]["wellbeing"][1] = "Shorter hours improved sleep quality"
        problems = EV.quote_problems(s, ABSTRACTS)
        self.assertEqual(len(problems), 1)
        self.assertIn("Alpha et al. 2020 / wellbeing", problems[0])

    def test_case_and_dropped_words_are_not_verbatim(self):
        s = studies()
        s[0]["outcomes"]["wellbeing"][1] = "reduced hours improved sleep quality"
        self.assertTrue(EV.quote_problems(s, ABSTRACTS))
        s[0]["outcomes"]["wellbeing"][1] = "Reduced hours improved quality"
        self.assertTrue(EV.quote_problems(s, ABSTRACTS))

    def test_no_abstract_means_nothing_to_quote(self):
        abstracts = dict(ABSTRACTS)
        abstracts[DOI_B] = {"abstract": ""}
        problems = EV.quote_problems(studies(), abstracts)
        self.assertEqual(len(problems), 1)
        self.assertIn("no retrieved abstract", problems[0])

    def test_saved_text_stands_in_for_a_missing_abstract_and_for_no_doi(self):
        abstracts = dict(ABSTRACTS)
        abstracts[DOI_B] = {"abstract": ""}
        s = studies()
        s.append({"id": "uk-report", "label": "Report 2023", "country": "UK", "design": "Firm pilot report",
                  "tier": 2, "n": None, "type": "Reduced hours",
                  "outcomes": {"retention": ["+", "resignations fell from 2 to 0.8"]}})
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / EV.text_name(DOI_B)).write_text("In the same trial,\nburnout fell by a third.")
            (Path(tmp) / "uk-report.txt").write_text("Measured this way, resignations fell from 2 to 0.8 overall.")
            self.assertEqual(EV.quote_problems(s, abstracts, tmp), [])
        self.assertEqual(EV.text_name("10.1038/s41562-025-02259-6"), "10.1038_s41562-025-02259-6.txt")

    def test_schema_problems_are_specific(self):
        s = studies()
        s[0]["tier"] = 4
        s[1]["outcomes"]["wellbeing"][0] = "up"
        s[2]["n"] = "about 200"
        s.append(dict(s[0]))
        problems = "\n".join(EV.schema_problems(s))
        self.assertIn("tier must be 1, 2 or 3", problems)
        self.assertIn("must be [one of + ~ 0 -", problems)
        self.assertIn("n must be a positive integer", problems)
        self.assertIn("appears twice", problems)

    def test_every_study_doi_must_be_in_the_citation_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "citations.json"
            db.write_text(json.dumps({"version": 1, "citations": {DOI_A: {"doi": DOI_A}, DOI_B: {"doi": DOI_B}}}))
            problems = EV.citation_problems(studies(), db)
        self.assertEqual(len(problems), 1)
        self.assertIn(DOI_C, problems[0])

    def test_check_cli_exits_nonzero_on_a_miss_and_zero_when_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            ev = Path(tmp) / "evidence.json"
            ab = Path(tmp) / "abstracts.json"
            ab.write_text(json.dumps(ABSTRACTS))
            ev.write_text(json.dumps({"studies": studies()}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(EV.main(["check", str(ev), "--abstracts", str(ab)]), 0)
            bad = studies()
            bad[2]["outcomes"]["wellbeing"][1] = "Respondents loved it"
            ev.write_text(json.dumps({"studies": bad}))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(EV.main(["check", str(ev), "--abstracts", str(ab)]), 1)
            self.assertIn("Gamma 2022", err.getvalue())


class IndexTests(unittest.TestCase):

    def test_reports_from_one_trial_share_one_weight(self):
        index = EV.compute_index(studies(), ["productivity", "wellbeing"])
        wb = index["outcomes"]["wellbeing"]
        weights = {it["label"]: it["w"] for it in wb["items"]}
        self.assertEqual(weights, {"Alpha et al. 2020": 1.5, "Beta et al. 2021": 1.5, "Gamma 2022": 1.0})
        self.assertEqual(wb["M"], 4.0)
        # (1.5*1 + 1.5*1 + 1*0.5) / 4
        self.assertAlmostEqual(wb["S"], 0.875)
        self.assertEqual(wb["k"], 3)
        self.assertEqual(wb["k_tier3"], 2)

    def test_leave_one_out_range(self):
        wb = EV.compute_index(studies(), ["wellbeing"])["outcomes"]["wellbeing"]
        # without Alpha: (1.5 + 0.5) / 2.5 = 0.8; without Beta: same; without Gamma: 1.0
        self.assertAlmostEqual(wb["loo_min"], 0.8)
        self.assertAlmostEqual(wb["loo_max"], 1.0)

    def test_a_single_report_has_no_leave_one_out(self):
        pr = EV.compute_index(studies(), ["productivity"])["outcomes"]["productivity"]
        self.assertEqual(pr["k"], 1)
        self.assertIsNone(pr["loo_min"])
        self.assertEqual(pr["S"], 0.0)

    def test_worse_scores_negative_and_outcomes_are_not_hardcoded(self):
        s = studies()
        s[2]["outcomes"] = {"absenteeism": ["-", "x"]}
        index = EV.compute_index(s, EV.outcome_names(s))
        self.assertEqual(index["outcomes"]["absenteeism"]["S"], -1.0)
        self.assertEqual(index["outcome_order"], ["wellbeing", "productivity", "absenteeism"])

    def test_outcome_order_from_the_file_wins(self):
        self.assertEqual(EV.outcome_names(studies(), ["productivity", "wellbeing"]),
                         ["productivity", "wellbeing"])


class AbstractFetchTests(unittest.TestCase):

    def test_inverted_index_is_rebuilt_in_order(self):
        self.assertEqual(EV.rebuild_abstract({"hours": [1], "Fewer": [0], "helped.": [2]}),
                         "Fewer hours helped.")
        self.assertEqual(EV.rebuild_abstract(None), "")

    def test_fetch_keeps_existing_stores_empty_and_reports_failures(self):
        calls = []

        def fake_get(url):
            calls.append(url)
            if "trial.two" in url:
                return {"title": "T", "publication_year": 2021, "abstract_inverted_index": None}
            if "survey" in url:
                raise urllib.error.URLError("down")
            return {"title": "T", "publication_year": 2020,
                    "abstract_inverted_index": {"Hello": [0]}}

        records = [{"doi": DOI_A}, {"doi": DOI_B}, {"doi": DOI_C}, {"doi": "10.1000/kept"}, {"title": "no doi"}]
        out, failed = EV.fetch_abstracts(records, existing={"10.1000/kept": {"abstract": "old"}},
                                         get=fake_get, sleep=lambda s: None)
        self.assertEqual(out[DOI_A]["abstract"], "Hello")
        self.assertEqual(out[DOI_B]["abstract"], "")
        self.assertEqual(out["10.1000/kept"]["abstract"], "old")
        self.assertNotIn(DOI_C, out)
        self.assertEqual(len(failed), 1)
        self.assertFalse(any("kept" in u for u in calls))


class FigureTests(unittest.TestCase):

    def _research(self, tmp):
        r = Path(tmp) / "research"
        r.mkdir()
        (r / "evidence.json").write_text(json.dumps({"outcome_order": ["productivity", "wellbeing"],
                                                     "studies": studies()}))
        (r / "abstracts.json").write_text(json.dumps(ABSTRACTS))
        (r / "sources.json").write_text(json.dumps([
            {"doi": DOI_A, "year": 2020}, {"doi": DOI_B, "year": 2021},
            {"doi": DOI_C, "year": 2022}, {"doi": "10.1000/old", "year": 1981}]))
        return r

    def test_figures_are_deterministic_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._research(tmp)
            first = EV.build_figures(r, r / "f1")
            EV.build_figures(r, r / "f2")
            self.assertEqual(first, ["captions.json", "evidence-map.svg", "evidence-profile.svg",
                                     "source-flow.svg", "table-ledger.html", "table-studies.html"])
            for name in first:
                self.assertEqual((r / "f1" / name).read_bytes(), (r / "f2" / name).read_bytes(), name)
            flow = (r / "f1" / "source-flow.svg").read_text()
            self.assertIn("4 DOI records resolved", flow)
            self.assertIn("3 abstracts", flow)
            ledger = (r / "f1" / "table-ledger.html").read_text()
            self.assertIn("Output was unchanged.", ledger)
            self.assertEqual(ledger.count("<tr>"), 5)  # header + four findings
            svg = (r / "f1" / "evidence-profile.svg").read_text()
            self.assertTrue(svg.startswith("<svg") and svg.rstrip().endswith("</svg>"))

    def test_a_stale_index_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._research(tmp)
            (r / "index.json").write_text(json.dumps(EV.compute_index(studies()[:2], ["wellbeing"])))
            with self.assertRaises(EV.EvidenceError):
                EV.build_figures(r, r / "f")


class PlaceholderToleranceTests(unittest.TestCase):
    """The placeholder lines pass through every other script untouched."""

    DRAFT = ("# Title\n\n## Abstract\n\nShort abstract.\n\n{figure:evidence-profile}\n\n"
             "## Results\n\nThe map follows {cite_10.1038/s41586-021-03819-2}.\n\n"
             "{figure:evidence-map}\n\n{table:studies}\n\n{equations:evidence-index}\n\nDone.\n")

    def _db(self):
        rec = CITATIONS._normalize_record({"doi": "10.1038/s41586-021-03819-2", "title": "AlphaFold",
                                           "authors": [{"family": "Jumper", "given": "John"}],
                                           "year": 2021, "venue": "Nature", "type": "journal-article"})
        rec["verified"] = "resolved"
        return {"version": 1, "citations": {rec["doi"]: rec}}

    def test_compile_keeps_them_and_the_gate_accepts_them(self):
        compiled = CITATIONS.compile_text(self.DRAFT, self._db(), "apa")
        for line in ("{figure:evidence-profile}", "{figure:evidence-map}", "{table:studies}",
                     "{equations:evidence-index}"):
            self.assertIn(line, compiled)
        self.assertEqual(INTEGRITY.run_checks(compiled), [])

    def test_they_count_toward_no_word_total(self):
        self.assertEqual(INTEGRITY.count_prose_words("One two.\n\n{figure:evidence-map}\n"), 2)

    def test_assemble_keeps_them_in_a_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            sections = Path(tmp) / "sections"
            sections.mkdir()
            (sections / "01_results.md").write_text("## Results\n\n{figure:evidence-map}\n\nText.\n")
            out = Path(tmp) / "full_draft.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = ASSEMBLE.main([str(sections), "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertIn("{figure:evidence-map}", out.read_text())


if __name__ == "__main__":
    unittest.main()
