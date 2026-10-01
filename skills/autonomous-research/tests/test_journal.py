"""The journal template: placement, refusal and the export wiring.

The template's one hard promise is that a placeholder line in the draft either
becomes the figure it names or stops the export. A figure that silently goes
missing, or a line of literal braces printed into a paper, is the failure it
was written to prevent.
"""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JOURNAL = _load("opendraft_journal_t", "journal.py")
EXPORT = _load("opendraft_export_t", "export.py")
EV = _load("opendraft_evidence_t", "evidence.py")
HAS_PANDOC = shutil.which("pandoc") is not None
HAS_WEASYPRINT = shutil.which("weasyprint") is not None

DRAFT = """# Shorter Weeks: A Review of the Evidence

## Abstract

What the review found.

{figure:evidence-profile}

## Introduction

Earlier work framed the question (Martin, 1981) (Fottler, 1977).

## Methods

{figure:source-flow}

### Evidence index

{equations:evidence-index}

## Results

{figure:evidence-map}

{table:studies}

{table:ledger}

## References

Martin, L. (1981). A modified week. https://doi.org/10.2307/3380297
"""


def research(tmp):
    r = Path(tmp) / "research"
    r.mkdir()
    studies = [{"doi": "10.1000/a", "label": "Alpha 2020", "country": "Sweden", "design": "Cluster RCT",
                "tier": 3, "n": 600, "type": "Reduced hours",
                "outcomes": {"wellbeing": ["+", "Sleep improved."]}}]
    (r / "evidence.json").write_text(json.dumps({"studies": studies}))
    (r / "abstracts.json").write_text(json.dumps({"10.1000/a": {"abstract": "Sleep improved."}}))
    (r / "sources.json").write_text(json.dumps([{"doi": "10.1000/a", "year": 2020},
                                                {"doi": "10.2307/3380297", "year": 1981}]))
    (r / "index.json").write_text(json.dumps(EV.compute_index(studies, ["wellbeing"])))
    EV.build_figures(r, r / "figures")
    return r


class SplitAndPlaceholderTests(unittest.TestCase):

    def test_split_takes_title_abstract_body_and_references(self):
        title, abstract, body, refs = JOURNAL.split_draft(DRAFT)
        self.assertEqual(title, "Shorter Weeks: A Review of the Evidence")
        self.assertEqual(abstract, "What the review found.")
        self.assertTrue(body.startswith("{figure:evidence-profile}"))
        self.assertIn("Martin, L. (1981)", refs)
        self.assertNotIn("Martin, L. (1981)", body)

    def test_unknown_placeholder_is_an_error_not_a_skip(self):
        with self.assertRaises(JOURNAL.JournalError) as ctx:
            JOURNAL.find_placeholders("Text.\n\n{figure:forest-plot}\n")
        self.assertIn("forest-plot", str(ctx.exception))

    def test_placeholders_are_found_in_order(self):
        _, _, body, _ = JOURNAL.split_draft(DRAFT)
        names = [n for _, _, n in JOURNAL.find_placeholders(body)]
        self.assertEqual(names, ["evidence-profile", "source-flow", "evidence-index",
                                 "evidence-map", "studies", "ledger"])

    def test_other_exports_drop_and_name_the_lines(self):
        text, removed = JOURNAL.strip_placeholders(DRAFT)
        self.assertEqual(len(removed), 6)
        self.assertNotIn("{figure:", text)
        self.assertIn("What the review found.", text)

    def test_adjacent_author_year_citations_merge(self):
        self.assertEqual(JOURNAL.ADJACENT_CITES.sub(r"\1; ", "(Martin, 1981) (Fottler, 1977)"),
                         "(Martin, 1981; Fottler, 1977)")
        self.assertEqual(JOURNAL.ADJACENT_CITES.sub(r"\1; ", "[1] [2]"), "[1] [2]")

    def test_bundled_assets_are_present(self):
        for name in JOURNAL.EQUATION_FILES:
            self.assertTrue((JOURNAL.ASSETS / name).exists(), name)
        _, missing = JOURNAL.font_faces()
        self.assertEqual(missing, [])


@unittest.skipUnless(HAS_PANDOC, "pandoc not installed")
class BuildHtmlTests(unittest.TestCase):

    def test_every_placeholder_becomes_its_figure_and_the_hero_leads(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = research(tmp)
            draft = Path(tmp) / "final.md"
            draft.write_text(DRAFT)
            page, _ = JOURNAL.build_html(draft, r / "figures", r, kind="Narrative review")
        self.assertNotIn("{figure:", page)
        self.assertNotIn("{table:", page)
        self.assertNotIn("JOURNALSLOT", page)
        self.assertIn('<figure class="hero">', page)
        self.assertLess(page.index('class="hero"'), page.index("<main"))
        self.assertIn("Fig. 1 | Evidence at a glance.", page)
        self.assertIn("Fig. 3 | Evidence map.", page)
        self.assertIn("Table 2 | Evidence ledger.", page)
        self.assertIn("(Martin, 1981; Fottler, 1977)", page)
        self.assertIn("<span class=num>1</span>Introduction", page)
        self.assertIn("class=glance", page)
        self.assertIn("<h1>Shorter Weeks</h1>", page)
        self.assertIn("A Review of the Evidence", page)
        self.assertEqual(page.count("<div class=eq>"), 3)

    def test_a_placeholder_without_its_figure_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = research(tmp)
            (r / "figures" / "evidence-map.svg").unlink()
            draft = Path(tmp) / "final.md"
            draft.write_text(DRAFT)
            with self.assertRaises(JOURNAL.JournalError) as ctx:
                JOURNAL.build_html(draft, r / "figures", r)
        self.assertIn("evidence.py figures", str(ctx.exception))

    def test_no_invented_masthead_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = research(tmp)
            draft = Path(tmp) / "final.md"
            draft.write_text(DRAFT)
            page, _ = JOURNAL.build_html(draft, r / "figures", r)
        for word in ("Volume", "Vol.", "Received", "Accepted", "Issue"):
            self.assertNotIn(word, page)
        self.assertIn("<span class=brand>OpenDraft</span>", page)


@unittest.skipUnless(HAS_PANDOC and HAS_WEASYPRINT, "pandoc and weasyprint needed")
class JournalPdfTests(unittest.TestCase):

    def test_export_cli_writes_a_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            research(tmp)
            draft = Path(tmp) / "final.md"
            draft.write_text(DRAFT)
            out = Path(tmp) / "final.pdf"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = EXPORT.main([str(draft), "--format", "pdf", "-o", str(out), "--template", "journal"])
            self.assertEqual(code, 0)
            self.assertTrue(out.read_bytes().startswith(b"%PDF"))

    def test_journal_template_refuses_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "final.md"
            draft.write_text(DRAFT)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = EXPORT.main([str(draft), "--format", "docx", "-o", str(Path(tmp) / "x.docx"),
                                    "--template", "journal"])
            self.assertEqual(code, 1)
            self.assertIn("pdf or html only", err.getvalue())


if __name__ == "__main__":
    unittest.main()
