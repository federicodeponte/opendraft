"""Round-trip tests: real compile_text output fed into integrity.run_checks.

Every prior integrity fixture was hand-typed, so no test ever proved that the
document the pipeline actually produces passes the gate the pipeline actually
runs. These tests close that loop for all six styles.
"""
import importlib.util
import unittest
from pathlib import Path


def _load(name, filename):
    script = Path(__file__).parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CITATIONS = _load("opendraft_citations_rt", "citations.py")
INTEGRITY = _load("opendraft_integrity_rt", "integrity.py")

DOI_A = "10.1007/979-8-8688-1808-0_1"
DOI_B = "10.1038/s41586-021-03819-2"
# A book with a press and no publication year, so the round-trip covers both
# the publisher field and the "n.d." branch of every style.
DOI_C = "10.5555/no-year-book"

RAW_RECORDS = [
    {
        "doi": DOI_A,
        "title": "Introduction to Retrieval-Augmented Generation (RAG)",
        "authors": [{"family": "Bose", "given": "Ranajoy"}],
        "year": 2025,
        "venue": "Mastering Retrieval-Augmented Generation",
        "type": "book-chapter",
        "verified": "resolved",
    },
    {
        "doi": DOI_B,
        "title": "Highly accurate protein structure prediction with AlphaFold",
        "authors": [
            {"family": "Jumper", "given": "John"},
            {"family": "Evans", "given": "Richard"},
        ],
        "year": 2021,
        "venue": "Nature",
        "type": "journal-article",
        "verified": "resolved",
    },
    {
        "doi": DOI_C,
        "title": "Undated Notes on Evaluation",
        "authors": [{"family": "Nakamura", "given": "Sora"}],
        "year": None,
        "venue": "",
        "publisher": "Kettle Press",
        "type": "book",
        "verified": "resolved",
    },
]


def make_db():
    db = {"version": 1, "citations": {}}
    for raw in RAW_RECORDS:
        record = CITATIONS._normalize_record(raw)
        record["verified"] = "resolved"
        db["citations"][record["doi"]] = record
    return db


# A draft that looks like what stage 5 of the skill actually requires: a
# synthesis table in Results, a nested bullet list, a fenced code block, and an
# ordinary parenthetical abbreviation that is not a citation marker.
DRAFT = (
    "# Retrieval and Structure Prediction\n"
    "\n"
    "Retrieval-augmented generation (RAG) combines retrieval with generation\n"
    "{cite_%s}. AlphaFold demonstrated a similar leap for structure\n"
    "prediction {cite_%s}. An undated set of notes reaches the same\n"
    "conclusion {cite_%s}.\n"
    "\n"
    "## Results\n"
    "\n"
    "| Study       | Design       | Outcome  |\n"
    "|-------------|--------------|----------|\n"
    "| Bose 2025   | Narrative    | Positive |\n"
    "| Jumper 2021 | Experimental | Positive |\n"
    "\n"
    "Key observations:\n"
    "\n"
    "- Retrieval quality dominates the result.\n"
    "  - Chunk size matters less than expected.\n"
    "  - Reranking helps on long documents.\n"
    "- Generation quality is secondary.\n"
    "\n"
    "```python\n"
    "def rank(docs):\n"
    "    return sorted(docs,  key=score)\n"
    "```\n"
    "\n"
    "The two findings agree.\n"
) % (DOI_A, DOI_B, DOI_C)


class RoundTripTests(unittest.TestCase):
    """Finding 1 (MLA can never pass) and finding 2 (tables/lists/fences)."""

    def test_every_style_compiles_to_a_document_the_gate_accepts(self):
        db = make_db()
        for style in sorted(CITATIONS.ALL_STYLES):
            with self.subTest(style=style):
                compiled = CITATIONS.compile_text(DRAFT, db, style)
                self.assertNotIn("{cite_", compiled)
                self.assertEqual(INTEGRITY.run_checks(compiled), [])

    def test_mla_marker_is_seen_by_the_gate(self):
        db = make_db()
        compiled = CITATIONS.compile_text(DRAFT, db, "mla")
        self.assertIn("(Bose)", compiled)
        self.assertEqual(INTEGRITY.run_checks(compiled), [])

    def test_no_year_record_never_renders_a_double_period(self):
        """A style that appends its own period after the "n.d." token, which
        already ends in one, printed "n.d..". Six styles, one assertion."""
        db = make_db()
        for style in sorted(CITATIONS.ALL_STYLES):
            with self.subTest(style=style):
                compiled = CITATIONS.compile_text(DRAFT, db, style)
                self.assertIn("n.d.", compiled)
                self.assertNotIn("n.d..", compiled)

    def test_publisher_survives_normalization_and_is_printed_for_a_book(self):
        """DECISIONS.md names `publisher` in the canonical record and
        sources.py collects it; it used to be dropped by _normalize_record."""
        db = make_db()
        self.assertEqual(db["citations"][DOI_C]["publisher"], "Kettle Press")
        for style in sorted(CITATIONS.ALL_STYLES):
            with self.subTest(style=style):
                compiled = CITATIONS.compile_text(DRAFT, db, style)
                self.assertIn("Kettle Press", compiled)

    def test_a_journal_article_does_not_print_its_crossref_imprint(self):
        """Crossref reports a publisher for journal articles too; no style
        prints one in a reference list, so it must not leak into the output."""
        db = make_db()
        db["citations"][DOI_B]["publisher"] = "Springer Science and Business Media LLC"
        for style in sorted(CITATIONS.ALL_STYLES):
            with self.subTest(style=style):
                compiled = CITATIONS.compile_text(DRAFT, db, style)
                self.assertNotIn("Springer Science", compiled)

    def test_gate_still_catches_a_real_break_in_every_style(self):
        """The round-trip must not pass because the gate stopped checking."""
        db = make_db()
        for style in sorted(CITATIONS.ALL_STYLES):
            with self.subTest(style=style):
                compiled = CITATIONS.compile_text(DRAFT, db, style)
                broken = compiled.replace("The two findings agree.",
                                          "The two findings agree. TODO tighten this.")
                self.assertTrue(INTEGRITY.run_checks(broken))


if __name__ == "__main__":
    unittest.main()
