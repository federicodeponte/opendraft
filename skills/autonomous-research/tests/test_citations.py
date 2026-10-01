import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "citations.py"
SPEC = importlib.util.spec_from_file_location("opendraft_citations", SCRIPT)
CITATIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CITATIONS)


# Two real, distinct sources used across the fixtures below.
DOI_A = "10.1007/979-8-8688-1808-0_1"   # single named author, book chapter
DOI_B = "10.1038/s41586-021-03819-2"    # two named authors, journal article

RAW_RECORDS = [
    {
        "doi": DOI_A,
        "title": "Introduction to Retrieval-Augmented Generation (RAG)",
        "authors": [{"family": "Bose", "given": "Ranajoy"}],
        "year": 2025,
        "venue": "Mastering Retrieval-Augmented Generation",
        "publisher": "Apress",
        "type": "book-chapter",
        "source": "crossref",
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
        "publisher": "Springer Science and Business Media LLC",
        "type": "journal-article",
        "source": "crossref",
    },
]


def _make_db(verified="resolved"):
    db = {"version": 1, "citations": {}}
    for raw in RAW_RECORDS:
        record = CITATIONS._normalize_record(raw)
        record["verified"] = verified
        db["citations"][record["doi"]] = record
    return db


class NormalizeRecordTests(unittest.TestCase):
    def test_normalize_record_lowercases_doi_and_keeps_structured_authors(self):
        record = CITATIONS._normalize_record(RAW_RECORDS[1])
        self.assertEqual(record["doi"], DOI_B.lower())
        self.assertEqual(record["authors"][0], {"family": "Jumper", "given": "John"})
        self.assertEqual(record["verified"], "unknown")

    def test_normalize_record_carries_the_publisher_named_in_the_schema(self):
        record = CITATIONS._normalize_record(RAW_RECORDS[0])
        self.assertEqual(record["publisher"], "Apress")

    def test_every_canonical_field_survives_normalization(self):
        record = CITATIONS._normalize_record(RAW_RECORDS[0])
        for field in ("doi", "title", "authors", "year", "venue", "publisher",
                      "type", "verified"):
            with self.subTest(field=field):
                self.assertIn(field, record)


class SortOrderTests(unittest.TestCase):
    """A bibliography must be reproducible: the same database, the same order."""

    @staticmethod
    def _same_surname_db():
        db = {"version": 1, "citations": {}}
        for doi, year, title in (
            ("10.1000/chen-b", 2019, "Beta results"),
            ("10.1000/chen-a", 2019, "Alpha results"),
            ("10.1000/chen-c", 2015, "Gamma results"),
        ):
            db["citations"][doi] = CITATIONS._normalize_record({
                "doi": doi, "title": title, "year": year,
                "authors": [{"family": "Chen", "given": "Li"}],
                "venue": "Journal of Testing", "type": "journal-article",
                "verified": "resolved",
            })
        return db

    def test_two_entries_with_the_same_surname_sort_deterministically(self):
        db = self._same_surname_db()
        keys = sorted(db["citations"], key=lambda d: CITATIONS._sort_key(db["citations"][d]))
        self.assertEqual(keys, ["10.1000/chen-c", "10.1000/chen-a", "10.1000/chen-b"])

    def test_sort_order_does_not_depend_on_insertion_order(self):
        db = self._same_surname_db()
        reversed_db = {"version": 1,
                       "citations": dict(reversed(list(db["citations"].items())))}
        order_one = [CITATIONS._sort_key(c) for c in
                     sorted(db["citations"].values(), key=CITATIONS._sort_key)]
        order_two = [CITATIONS._sort_key(c) for c in
                     sorted(reversed_db["citations"].values(), key=CITATIONS._sort_key)]
        self.assertEqual(order_one, order_two)

    def test_a_same_surname_bibliography_compiles_identically_twice(self):
        db = self._same_surname_db()
        draft = ("Alpha {cite_10.1000/chen-a}. Beta {cite_10.1000/chen-b}. "
                 "Gamma {cite_10.1000/chen-c}.\n")
        first = CITATIONS.compile_text(draft, db, "apa")
        shuffled = {"version": 1,
                    "citations": dict(reversed(list(db["citations"].items())))}
        second = CITATIONS.compile_text(draft, shuffled, "apa")
        self.assertEqual(first, second)


class BuildDatabaseTests(unittest.TestCase):
    def test_build_merges_and_preserves_prior_verification(self):
        with tempfile.TemporaryDirectory() as d:
            sources_json = Path(d) / "sources.json"
            db_path = Path(d) / "citations.json"
            sources_json.write_text(json.dumps(RAW_RECORDS), encoding="utf-8")

            stats = CITATIONS.build_database(sources_json, db_path)
            self.assertEqual(stats, {"added": 2, "updated": 0, "total": 2})

            db = CITATIONS.load_database(db_path)
            db["citations"][DOI_A]["verified"] = "resolved"
            CITATIONS.save_database(db_path, db)

            stats2 = CITATIONS.build_database(sources_json, db_path)
            self.assertEqual(stats2, {"added": 0, "updated": 2, "total": 2})
            db2 = CITATIONS.load_database(db_path)
            self.assertEqual(db2["citations"][DOI_A]["verified"], "resolved")

    def test_build_rejects_non_array_input(self):
        with tempfile.TemporaryDirectory() as d:
            sources_json = Path(d) / "sources.json"
            db_path = Path(d) / "citations.json"
            sources_json.write_text(json.dumps({"not": "an array"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                CITATIONS.build_database(sources_json, db_path)


class CompileTests(unittest.TestCase):
    DRAFT = (
        "# Test Draft\n\n"
        "RAG systems combine retrieval with generation {cite_%s}. "
        "AlphaFold demonstrated a similar leap for structure prediction {cite_%s}.\n"
    ) % (DOI_A, DOI_B)

    def test_compile_apa_style(self):
        db = _make_db()
        compiled = CITATIONS.compile_text(self.DRAFT, db, "apa")
        self.assertIn("(Bose, 2025)", compiled)
        self.assertIn("(Jumper & Evans, 2021)", compiled)
        self.assertNotIn("{cite_", compiled)
        self.assertIn("## References", compiled)
        # Alphabetical: Bose before Jumper.
        self.assertLess(compiled.index("Bose"), compiled.index("Jumper"))

    def test_compile_ieee_style_numbers_by_first_appearance(self):
        db = _make_db()
        compiled = CITATIONS.compile_text(self.DRAFT, db, "ieee")
        self.assertIn("[1]", compiled)
        self.assertIn("[2]", compiled)
        self.assertNotIn("{cite_", compiled)
        # Bose (DOI_A) appears first in the draft text, so it must be [1] in
        # the bibliography too.
        bib_start = compiled.index("## References")
        self.assertIn("[1] Bose", compiled[bib_start:])
        self.assertIn("[2] Jumper", compiled[bib_start:])

    def test_compile_vancouver_numeric(self):
        db = _make_db()
        compiled = CITATIONS.compile_text(self.DRAFT, db, "vancouver")
        self.assertIn("[1]", compiled)
        self.assertIn("[2]", compiled)
        bib_start = compiled.index("## References")
        self.assertIn("1. Bose", compiled[bib_start:])

    def test_compile_mla_and_chicago_and_harvard_run_without_error(self):
        db = _make_db()
        for style in ("mla", "chicago", "harvard"):
            compiled = CITATIONS.compile_text(self.DRAFT, db, style)
            self.assertNotIn("{cite_", compiled)
            self.assertIn("## References", compiled)

    def test_compile_missing_doi_raises_named_error(self):
        db = {"version": 1, "citations": {}}
        text = "See {cite_10.9999/does-not-exist} for details."
        with self.assertRaises(CITATIONS.CompileError) as ctx:
            CITATIONS.compile_text(text, db, "apa")
        self.assertIn("10.9999/does-not-exist", str(ctx.exception))

    def test_compile_rejects_unsupported_style(self):
        db = _make_db()
        with self.assertRaises(ValueError):
            CITATIONS.compile_text(self.DRAFT, db, "vancouver-ish")

    def test_compile_cli_exits_nonzero_on_missing_citation(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            CITATIONS.save_database(db_path, {"version": 1, "citations": {}})
            draft_path = Path(d) / "draft.md"
            draft_path.write_text("Unresolvable {cite_10.9999/nope}.\n", encoding="utf-8")
            out_path = Path(d) / "out.md"

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "compile", str(draft_path),
                 "-d", str(db_path), "--style", "apa", "-o", str(out_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("10.9999/nope", result.stderr)
            self.assertFalse(out_path.exists())


class AuthorFormattingTests(unittest.TestCase):
    """Finding 11: an empty given name must never leave a stranded comma."""

    ONE_NAME_ONLY = {
        "doi": "10.1/chen", "title": "A Single-Name Record",
        "authors": [{"family": "Chen", "given": ""}],
        "year": 2022, "venue": "Venue", "type": "journal-article",
        "url": "https://doi.org/10.1/chen", "verified": "resolved",
    }

    TWO_AUTHORS_FIRST_UNNAMED = {
        "doi": "10.1/pair", "title": "A Pair",
        "authors": [{"family": "Chen", "given": ""}, {"family": "Diaz", "given": "Ana"}],
        "year": 2022, "venue": "Venue", "type": "journal-article",
        "url": "https://doi.org/10.1/pair", "verified": "resolved",
    }

    def test_no_formatter_emits_a_stranded_comma(self):
        formatters = [
            CITATIONS._format_authors_apa,
            CITATIONS._format_authors_mla,
            CITATIONS._format_authors_chicago,
            CITATIONS._format_authors_harvard,
            CITATIONS._format_authors_numeric,
        ]
        for citation in (self.ONE_NAME_ONLY, self.TWO_AUTHORS_FIRST_UNNAMED):
            for fn in formatters:
                with self.subTest(fn=fn.__name__, doi=citation["doi"]):
                    out = fn(citation)
                    self.assertNotIn(", .", out)
                    self.assertNotIn(",,", out)
                    self.assertNotIn(", ,", out)
                    self.assertNotRegex(out, r",\s*$")

    def test_mla_single_author_without_given_name(self):
        self.assertEqual(CITATIONS._format_authors_mla(self.ONE_NAME_ONLY), "Chen.")

    def test_chicago_single_author_without_given_name(self):
        self.assertEqual(CITATIONS._format_authors_chicago(self.ONE_NAME_ONLY), "Chen.")

    def test_bibtex_author_field_has_no_stranded_comma(self):
        db = {"version": 1, "citations": {"10.1/chen": self.ONE_NAME_ONLY}}
        bib = CITATIONS.to_bibtex(db)
        self.assertIn("author = {Chen}", bib)


class NoAuthorCitationTests(unittest.TestCase):
    """Finding 12: a record with no authors must still produce a marker the
    integrity gate can match against its own bibliography entry."""

    ANON = {
        "doi": "10.1/anon", "title": "Alpha Study of Carbon Pricing",
        "authors": [], "year": 2023, "venue": "Venue", "type": "report",
        "url": "https://doi.org/10.1/anon", "verified": "resolved",
    }

    def test_marker_and_bibliography_share_the_same_author_token(self):
        for style in ("apa", "chicago", "harvard"):
            with self.subTest(style=style):
                marker = CITATIONS.format_in_text(style, self.ANON)
                reference = CITATIONS.format_reference(style, self.ANON)
                self.assertIn("Anon.", marker)
                self.assertNotIn("Alpha Study", marker)
                self.assertTrue(reference.startswith("Anon."), reference)

    def test_mla_marker_is_anon(self):
        self.assertEqual(CITATIONS.format_in_text("mla", self.ANON), "(Anon.)")

    def test_no_author_document_passes_the_integrity_gate(self):
        integrity_script = Path(__file__).parents[1] / "scripts" / "integrity.py"
        spec = importlib.util.spec_from_file_location("opendraft_integrity_na",
                                                      integrity_script)
        integrity = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integrity)

        db = {"version": 1, "citations": {"10.1/anon": self.ANON}}
        text = "An unattributed report is still a source {cite_10.1/anon}.\n"
        for style in sorted(CITATIONS.ALL_STYLES):
            with self.subTest(style=style):
                compiled = CITATIONS.compile_text(text, db, style)
                self.assertEqual(integrity.run_checks(compiled), [])


class VerifiedGateTests(unittest.TestCase):
    """Finding 14: SKILL.md promises every printed DOI resolved. Enforce it."""

    def test_compile_refuses_an_unverified_citation(self):
        db = _make_db(verified="unknown")
        with self.assertRaises(CITATIONS.UnverifiedCitationError) as ctx:
            CITATIONS.compile_text(CompileTests.DRAFT, db, "apa")
        message = str(ctx.exception)
        self.assertIn(DOI_A, message)
        self.assertIn(DOI_B, message)
        self.assertIn("unknown", message)
        self.assertIn("citations.py verify", message)

    def test_compile_names_every_offender_not_just_the_first(self):
        db = _make_db(verified="absent")
        with self.assertRaises(CITATIONS.UnverifiedCitationError) as ctx:
            CITATIONS.compile_text(CompileTests.DRAFT, db, "apa")
        self.assertIn(DOI_A, str(ctx.exception))
        self.assertIn(DOI_B, str(ctx.exception))

    def test_an_unverified_citation_that_is_never_cited_does_not_block(self):
        db = _make_db(verified="resolved")
        db["citations"]["10.1/unused"] = {
            "doi": "10.1/unused", "title": "Unused", "authors": [{"family": "X", "given": "Y"}],
            "year": 2020, "venue": "V", "type": "misc",
            "url": "https://doi.org/10.1/unused", "verified": "unknown",
        }
        compiled = CITATIONS.compile_text(CompileTests.DRAFT, db, "apa")
        self.assertIn("## References", compiled)

    def test_compile_cli_exits_nonzero_on_an_unverified_citation(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            CITATIONS.save_database(db_path, _make_db(verified="unknown"))
            draft_path = Path(d) / "draft.md"
            draft_path.write_text("A claim {cite_%s}.\n" % DOI_A, encoding="utf-8")
            out_path = Path(d) / "out.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "compile", str(draft_path),
                 "-d", str(db_path), "--style", "apa", "-o", str(out_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn(DOI_A, result.stderr)
            self.assertFalse(out_path.exists())


class UserErrorTests(unittest.TestCase):
    """Finding 8: ordinary user errors must not raise a traceback."""

    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args),
                              check=False, capture_output=True, text=True)

    def test_compile_reports_a_missing_draft_file(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            CITATIONS.save_database(db_path, _make_db())
            result = self._run("compile", str(Path(d) / "nope.md"),
                               "-d", str(db_path), "--style", "apa",
                               "-o", str(Path(d) / "out.md"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("not found", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_compile_reports_a_malformed_database(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            db_path.write_text("{not json at all", encoding="utf-8")
            draft = Path(d) / "draft.md"
            draft.write_text("Body.\n", encoding="utf-8")
            result = self._run("compile", str(draft), "-d", str(db_path),
                               "--style", "apa", "-o", str(Path(d) / "out.md"))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("not valid JSON", result.stderr)

    def test_bibtex_reports_a_malformed_database(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            db_path.write_text("[]not json", encoding="utf-8")
            result = self._run("bibtex", "-d", str(db_path),
                               "-o", str(Path(d) / "refs.bib"))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_verify_reports_a_malformed_database(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            db_path.write_text("nope", encoding="utf-8")
            result = self._run("verify", "-d", str(db_path))
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)


class DatabaseSchemaTests(unittest.TestCase):
    """Finding 9: a wrong-shaped database must fail as itself, not as a
    phantom missing-source problem."""

    def _write(self, d, payload):
        path = Path(d) / "citations.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_citations_as_a_list_is_rejected_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, {"version": 1, "citations": [
                {"doi": "10.1234/abc", "title": "T", "authors": [], "year": 2020},
            ]})
            with self.assertRaises(CITATIONS.DatabaseError) as ctx:
                CITATIONS.load_database(path)
            self.assertIn("citations", str(ctx.exception))
            self.assertIn("keyed by DOI", str(ctx.exception))

    def test_bare_string_author_is_rejected_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, {"version": 1, "citations": {
                "10.1234/abc": {"doi": "10.1234/abc", "title": "T",
                                "authors": ["Smith"], "year": 2020},
            }})
            with self.assertRaises(CITATIONS.DatabaseError) as ctx:
                CITATIONS.load_database(path)
            self.assertIn("10.1234/abc", str(ctx.exception))
            self.assertIn("family", str(ctx.exception))

    def test_top_level_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, [{"doi": "10.1234/abc"}])
            with self.assertRaises(CITATIONS.DatabaseError):
                CITATIONS.load_database(path)

    def test_wrong_shape_reports_the_schema_not_a_missing_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, {"version": 1, "citations": [
                {"doi": "10.1234/abc", "title": "T", "authors": [], "year": 2020},
            ]})
            draft = Path(d) / "draft.md"
            draft.write_text("A claim {cite_10.1234/abc}.\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "compile", str(draft),
                 "-d", str(path), "--style", "apa", "-o", str(Path(d) / "out.md")],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("placeholder(s) not found", result.stderr)
            self.assertIn("keyed by DOI", result.stderr)

    def test_a_well_formed_database_still_loads(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "citations.json"
            CITATIONS.save_database(path, _make_db())
            db = CITATIONS.load_database(path)
            self.assertEqual(len(db["citations"]), 2)


class DocstringTests(unittest.TestCase):
    def test_docstring_does_not_claim_a_requests_dependency(self):
        """Finding 10: nothing in the bundle imports requests."""
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("requests", CITATIONS.__doc__ or "")
        self.assertNotIn("import requests", source)


class BibtexTests(unittest.TestCase):
    def test_bibtex_entries_have_stable_collision_free_keys(self):
        db = _make_db()
        bib = CITATIONS.to_bibtex(db)
        self.assertIn("@incollection{bose2025introduction,", bib)
        self.assertIn("@article{jumper2021highly,", bib)
        self.assertIn("doi = {%s}" % DOI_A, bib)
        self.assertIn("journal = {Nature}", bib)

    def test_bibtex_keys_never_collide_even_with_same_author_year_title_word(self):
        db = {
            "version": 1,
            "citations": {
                "10.1/aaa": {
                    "doi": "10.1/aaa", "title": "Widgets are great", "authors": [{"family": "Smith", "given": "A"}],
                    "year": 2020, "venue": "", "type": "misc", "url": "https://doi.org/10.1/aaa", "verified": "unknown",
                },
                "10.1/bbb": {
                    "doi": "10.1/bbb", "title": "Widgets are also great", "authors": [{"family": "Smith", "given": "B"}],
                    "year": 2020, "venue": "", "type": "misc", "url": "https://doi.org/10.1/bbb", "verified": "unknown",
                },
            },
        }
        bib = CITATIONS.to_bibtex(db)
        self.assertIn("@misc{smith2020widgets,", bib)
        self.assertIn("@misc{smith2020widgetsa,", bib)


class MissingSourceMarkerTests(unittest.TestCase):
    """`{cite_MISSING: <description>}` is the drafter's honest admission that a
    claim has no source yet. compile must refuse it by name, with the drafter's
    own description, and must never substitute anything for it."""

    CLAIM_A = "Kirkwood's disposable soma theory"
    CLAIM_B = "the 2019 replication rate for social priming"

    def _draft(self):
        return (
            "# Draft\n\n"
            "RAG systems combine retrieval with generation "
            f"{{cite_{DOI_A}}}.\n\n"
            f"Ageing trades repair against reproduction {{cite_MISSING: {self.CLAIM_A}}}.\n\n"
            f"Priming replicates poorly {{cite_MISSING: {self.CLAIM_B}}}.\n"
        )

    def test_compile_text_refuses_a_missing_source_marker(self):
        with self.assertRaises(CITATIONS.MissingSourceError) as ctx:
            CITATIONS.compile_text(self._draft(), _make_db(), "apa")
        message = str(ctx.exception)
        self.assertIn("cite_MISSING", message)
        self.assertIn(self.CLAIM_A, message)

    def test_it_names_every_offender_at_once_not_just_the_first(self):
        with self.assertRaises(CITATIONS.MissingSourceError) as ctx:
            CITATIONS.compile_text(self._draft(), _make_db(), "apa")
        message = str(ctx.exception)
        self.assertIn(self.CLAIM_A, message)
        self.assertIn(self.CLAIM_B, message)
        self.assertEqual(len(ctx.exception.offenders), 2)

    def test_the_marker_is_never_reported_as_a_doi_not_in_the_database(self):
        """CITE_PATTERN would otherwise read `MISSING: Kirkwood...` as a DOI and
        raise the misleading `not found in the database` CompileError."""
        with self.assertRaises(CITATIONS.MissingSourceError) as ctx:
            CITATIONS.compile_text(self._draft(), _make_db(), "apa")
        self.assertNotIn("not found in the database", str(ctx.exception))

    def test_a_marker_with_no_description_is_still_refused(self):
        text = "A claim with nothing behind it {cite_MISSING}.\n"
        with self.assertRaises(CITATIONS.MissingSourceError):
            CITATIONS.compile_text(text, _make_db(), "apa")

    def test_a_real_citation_alongside_a_marker_is_not_silently_rendered(self):
        """The whole compile fails; no half-rendered output is produced."""
        with self.assertRaises(CITATIONS.MissingSourceError):
            CITATIONS.compile_text(self._draft(), _make_db(), "apa")

    def test_a_draft_without_markers_still_compiles(self):
        text = f"Body {{cite_{DOI_A}}}.\n"
        out = CITATIONS.compile_text(text, _make_db(), "apa")
        self.assertIn("(Bose, 2025)", out)

    def test_cli_compile_exits_nonzero_and_writes_no_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "citations.json"
            CITATIONS.save_database(db_path, _make_db())
            draft_path = Path(d) / "draft.md"
            draft_path.write_text(self._draft(), encoding="utf-8")
            out_path = Path(d) / "out.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "compile", str(draft_path),
                 "-d", str(db_path), "--style", "apa", "-o", str(out_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn(self.CLAIM_A, result.stderr)
            self.assertIn(self.CLAIM_B, result.stderr)
            self.assertIn("cite_MISSING", result.stderr)
            self.assertNotIn("not found in the database", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out_path.exists())


if __name__ == "__main__":
    unittest.main()
