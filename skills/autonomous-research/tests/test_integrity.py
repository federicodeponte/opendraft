import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "integrity.py"
SPEC = importlib.util.spec_from_file_location("opendraft_integrity", SCRIPT)
INTEGRITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INTEGRITY)


# Real APA output of citations.py compile, used verbatim as the "clean" fixture.
CLEAN_APA = (
    "# Test Draft\n\n"
    "RAG systems combine retrieval with generation (Bose, 2025). "
    "AlphaFold demonstrated a similar leap for structure prediction "
    "(Jumper & Evans, 2021).\n\n"
    "## References\n\n"
    "Bose, R. (2025). Introduction to Retrieval-Augmented Generation (RAG). "
    "*Mastering Retrieval-Augmented Generation*. "
    "https://doi.org/10.1007/979-8-8688-1808-0_1\n\n"
    "Jumper, J., & Evans, R. (2021). Highly accurate protein structure "
    "prediction with AlphaFold. *Nature*. "
    "https://doi.org/10.1038/s41586-021-03819-2\n"
)

# Real IEEE output of citations.py compile, used verbatim as the "clean" fixture.
CLEAN_IEEE = (
    "# Test Draft\n\n"
    "RAG systems combine retrieval with generation [1]. "
    "AlphaFold demonstrated a similar leap for structure prediction [2].\n\n"
    "## References\n\n"
    '[1] Bose, R., "Introduction to Retrieval-Augmented Generation (RAG)," '
    "*Mastering Retrieval-Augmented Generation*, 2025. "
    "https://doi.org/10.1007/979-8-8688-1808-0_1\n\n"
    '[2] Jumper, J., Evans, R., "Highly accurate protein structure prediction '
    'with AlphaFold," *Nature*, 2021. '
    "https://doi.org/10.1038/s41586-021-03819-2\n"
)


class CleanDraftTests(unittest.TestCase):
    def test_clean_apa_draft_has_no_failures(self):
        self.assertEqual(INTEGRITY.run_checks(CLEAN_APA), [])

    def test_clean_ieee_draft_has_no_failures(self):
        self.assertEqual(INTEGRITY.run_checks(CLEAN_IEEE), [])

    def test_clean_draft_cli_exits_zero_and_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


class PlaceholderCheckTests(unittest.TestCase):
    def test_surviving_placeholder_is_reported_with_line_number(self):
        text = "Line one.\nStill unresolved {cite_10.1/xyz} here.\n"
        failures = INTEGRITY.check_placeholders(text)
        self.assertEqual(len(failures), 1)
        self.assertIn("line 2", failures[0])
        self.assertIn("{cite_10.1/xyz}", failures[0])

    def test_full_pipeline_fails_on_surviving_placeholder(self):
        broken = CLEAN_APA.replace("(Bose, 2025)", "(Bose, 2025) {cite_10.1/still-here}")
        failures = INTEGRITY.run_checks(broken)
        self.assertTrue(any("unresolved placeholder" in f for f in failures))


class BibliographyMatchTests(unittest.TestCase):
    def test_bibliography_entry_never_cited_is_reported(self):
        text = (
            "Body text with no citations at all.\n\n"
            "## References\n\n"
            "Bose, R. (2025). Introduction to RAG. *Some Venue*. https://doi.org/10.1/x\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(any("never cited" in f for f in failures))

    def test_in_text_marker_with_no_bibliography_entry_is_reported(self):
        text = (
            "Some claim (Nobody, 2025) needs a source.\n\n"
            "## References\n\n"
            "Someone, S. (2020). Other Work. *Venue*. https://doi.org/10.1/y\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(any("Nobody" in f and "no matching bibliography entry" in f for f in failures))

    def test_numeric_marker_must_land_on_matching_bibliography_number(self):
        text = (
            "A claim needing a source [3].\n\n"
            "## References\n\n"
            "[1] Someone, S., \"Title,\" *Venue*, 2020.\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(any("[3] has no matching bibliography entry 3" in f for f in failures))

    def test_numeric_bibliography_entry_never_cited_is_reported(self):
        text = (
            "A claim [1].\n\n"
            "## References\n\n"
            "[1] Someone, S., \"Title,\" *Venue*, 2020.\n\n"
            "[2] Other, O., \"Other Title,\" *Venue*, 2021.\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(any("bibliography entry 2 is never cited" in f for f in failures))


class StrandedPunctuationTests(unittest.TestCase):
    def test_double_space_left_by_a_removed_marker_is_reported(self):
        text = "The claim was shown  to hold.\n"
        failures = INTEGRITY.check_stranded_punctuation(text)
        self.assertTrue(failures)

    def test_space_before_period_is_reported(self):
        text = "The claim was shown to hold .\n"
        failures = INTEGRITY.check_stranded_punctuation(text)
        self.assertTrue(any("line 1" in f for f in failures))

    def test_space_before_semicolon_is_reported(self):
        text = "First point ; second point.\n"
        failures = INTEGRITY.check_stranded_punctuation(text)
        self.assertTrue(failures)

    def test_clean_text_has_no_stranded_punctuation_failures(self):
        self.assertEqual(INTEGRITY.check_stranded_punctuation(CLEAN_APA), [])


MARKDOWN_BODY = (
    "# Results\n"
    "\n"
    "The synthesis table below reports every included study (Bose, 2025).\n"
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
    "## References\n"
    "\n"
    "Bose, R. (2025). Introduction to RAG. *Some Venue*. https://doi.org/10.1/x\n"
)


class StrandedPunctuationMarkdownTests(unittest.TestCase):
    """Finding 2: the gate must not fire on ordinary markdown structure."""

    def test_aligned_table_nested_list_and_code_fence_are_clean(self):
        self.assertEqual(INTEGRITY.check_stranded_punctuation(MARKDOWN_BODY), [])

    def test_full_run_on_a_markdown_document_is_clean(self):
        self.assertEqual(INTEGRITY.run_checks(MARKDOWN_BODY), [])

    def test_real_deleted_marker_double_space_is_still_caught(self):
        text = "The effect was shown  to hold across every cohort.\n"
        failures = INTEGRITY.check_stranded_punctuation(text)
        self.assertTrue(failures, "a double space between words must still fail")

    def test_double_space_after_a_comma_mid_sentence_is_still_caught(self):
        text = "In the first cohort,  the effect was smaller.\n"
        self.assertTrue(INTEGRITY.check_stranded_punctuation(text))


class LeadingZeroDecimalTests(unittest.TestCase):
    """The gate must not be passable only by corrupting correct writing.

    An end-to-end run of the whole pipeline failed here five times, on p-values
    written the way the paper's own venue requires them. Every one was correct
    text. Worse than the noise: the message said a marker had been removed, so
    the repairs it invited were all wrong, and the run reached exit 0 only by
    editing the statistics into a house style no clinical journal accepts.
    """

    def test_a_p_value_without_its_leading_zero_is_not_stranded(self):
        text = "The effect held (HR 1.21, 95% CI 1.11-1.32, P < .001) in both arms.\n"
        self.assertEqual(INTEGRITY.check_stranded_punctuation(text), [])

    def test_a_bare_decimal_after_an_equals_sign_is_not_stranded(self):
        text = "The correlation was weak (r = .42) in the replication sample.\n"
        self.assertEqual(INTEGRITY.check_stranded_punctuation(text), [])

    def test_an_unspaced_elision_is_not_stranded(self):
        text = 'The authors wrote that the finding "held ... under every model".\n'
        self.assertEqual(INTEGRITY.check_stranded_punctuation(text), [])

    def test_a_spaced_elision_is_not_stranded(self):
        text = 'The authors wrote that the finding "held . . . under every model".\n'
        self.assertEqual(INTEGRITY.check_stranded_punctuation(text), [])

    def test_a_genuinely_stranded_period_is_still_reported(self):
        # What deleting "[14]" from "shown to hold [14]." actually leaves.
        self.assertTrue(INTEGRITY.check_stranded_punctuation(
            "The claim was shown to hold .\n"))

    def test_a_stranded_period_mid_paragraph_is_still_reported(self):
        self.assertTrue(INTEGRITY.check_stranded_punctuation(
            "The claim was shown to hold . The next sentence follows.\n"))

    def test_a_stranded_comma_before_a_number_is_still_reported(self):
        self.assertTrue(INTEGRITY.check_stranded_punctuation(
            "Across every cohort , 38 percent of the pairs held.\n"))


class MarkerYearMatchingTests(unittest.TestCase):
    """Finding 4: surname-only matching lets two different Smiths pass."""

    def test_marker_year_must_match_the_bibliography_entry_year(self):
        text = (
            "A claim needing a source (Smith, 2019).\n"
            "\n"
            "## References\n"
            "\n"
            "Smith, J. (2021). A Later Work. *Venue*. https://doi.org/10.1/y\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(
            any("Smith" in f and "no matching bibliography entry" in f for f in failures),
            f"expected a surname+year mismatch failure, got: {failures}",
        )

    def test_two_distinct_same_surname_entries_do_not_satisfy_each_other(self):
        text = (
            "One claim (Smith, 2019) is supported.\n"
            "\n"
            "## References\n"
            "\n"
            "Smith, A. (2019). An Earlier Work. *Venue*. https://doi.org/10.1/a\n"
            "\n"
            "Smith, B. (2021). A Later Work. *Venue*. https://doi.org/10.1/b\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(
            any("never cited" in f and "2021" in f for f in failures),
            f"the uncited Smith 2021 entry must be reported, got: {failures}",
        )

    def test_matching_surname_and_year_passes(self):
        text = (
            "One claim (Smith, 2019) and another (Smith, 2021).\n"
            "\n"
            "## References\n"
            "\n"
            "Smith, A. (2019). An Earlier Work. *Venue*. https://doi.org/10.1/a\n"
            "\n"
            "Smith, B. (2021). A Later Work. *Venue*. https://doi.org/10.1/b\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])


class YearlessMarkerTests(unittest.TestCase):
    """Finding 1: MLA in-text markers carry no year."""

    def test_mla_style_yearless_marker_counts_as_a_citation(self):
        text = (
            "A claim needing a source (Bose).\n"
            "\n"
            "## References\n"
            "\n"
            'Bose, Ranajoy. "Introduction to RAG." *Some Venue*, 2025. '
            "https://doi.org/10.1/x\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_ordinary_parenthetical_abbreviation_is_not_a_marker(self):
        text = (
            "Retrieval-augmented generation (RAG) is common (Bose).\n"
            "\n"
            "## References\n"
            "\n"
            'Bose, Ranajoy. "Introduction to RAG." *Some Venue*, 2025. '
            "https://doi.org/10.1/x\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_a_body_with_only_a_parenthetical_needs_no_bibliography(self):
        text = "Retrieval-augmented generation (RAG) is common.\n"
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])


class UnicodeSurnameTests(unittest.TestCase):
    """A gate that cannot read 'Muller' with an umlaut fails correct papers."""

    def test_accented_surname_round_trips(self):
        text = (
            "A claim needing a source (Müller, 2020).\n"
            "\n"
            "## References\n"
            "\n"
            "Müller, H. (2020). Ein Werk. *Venue*. https://doi.org/10.1/z\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])


class ParticleSurnameTests(unittest.TestCase):
    """A surname carrying a nobiliary/prepositional particle (German "von",
    Dutch "van der", Spanish/Portuguese/Italian "de"/"della"/"dos", Arabic
    "al-", ...) must match on the particle-plus-name as one unit, not fail
    and push a drafter toward dropping the particle to pass the gate. Real
    incident: "Birte von Haaren" got corrupted to "Haaren, B. (2015)" in a
    shipped draft because the old single-token regex could never match
    "(von Haaren et al., 2015)" against the correctly written bibliography
    entry.
    """

    def test_particle_surname_cited_and_present_passes(self):
        text = (
            "The literature notes a strong effect (von Haaren et al., 2015).\n"
            "\n"
            "## References\n"
            "\n"
            "Von Haaren, B., Meyer, C., & Klein, D. (2015). A Study. *Venue*. "
            "https://doi.org/10.1/x\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_particle_surname_present_but_genuinely_never_cited_still_fails(self):
        # No mention of the author anywhere in the body -- this must still be
        # caught. A regex that matches particle surnames too eagerly (turning
        # this check into a rubber stamp) would be a worse bug than the one
        # it fixes.
        text = (
            "This body discusses something else entirely and cites no one.\n"
            "\n"
            "## References\n"
            "\n"
            "Von Haaren, B. (2015). A Study. *Venue*. https://doi.org/10.1/x\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(
            any("never cited" in f and "Von Haaren" in f for f in failures),
            f"expected the uncited 'Von Haaren' entry to be reported, got: {failures}",
        )

    def test_multi_word_particle_van_der_round_trips(self):
        text = (
            "The effect replicates across cohorts (van der Berg, 2020).\n"
            "\n"
            "## References\n"
            "\n"
            "Van der Berg, T. (2020). A Study. *Venue*. https://doi.org/10.1/z\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_hyphen_attached_al_particle_round_trips(self):
        text = (
            "A claim needing a source (al-Rashid, 2020).\n"
            "\n"
            "## References\n"
            "\n"
            "Al-Rashid, S. (2020). A Study. *Venue*. https://doi.org/10.1/y\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_particle_surname_with_wrong_year_is_still_a_mismatch(self):
        # The particle fix must not loosen year matching: a particle surname
        # citing the wrong year is still a genuine error.
        text = (
            "A claim needing a source (von Haaren, 2019).\n"
            "\n"
            "## References\n"
            "\n"
            "Von Haaren, B. (2015). A Study. *Venue*. https://doi.org/10.1/x\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(
            any("von Haaren" in f and "no matching bibliography entry" in f for f in failures),
            f"expected a surname+year mismatch failure, got: {failures}",
        )


class HyphenatedAndApostropheSurnameTests(unittest.TestCase):
    """Non-particle edge cases the fix must not regress: a hyphenated
    surname and a surname with an apostrophe, both of which already worked
    under the old single-token regex and must keep working unchanged."""

    def test_hyphenated_surname_round_trips(self):
        text = (
            "The novel remains a landmark work (Garcia-Marquez, 1967).\n"
            "\n"
            "## References\n"
            "\n"
            "Garcia-Marquez, G. (1967). One Hundred Years of Solitude. *Venue*. "
            "https://doi.org/10.1/w\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_apostrophe_surname_round_trips(self):
        text = (
            "The account is a formative example of the genre (O'Brien, 1990).\n"
            "\n"
            "## References\n"
            "\n"
            "O'Brien, T. (1990). The Things They Carried. *Venue*. "
            "https://doi.org/10.1/v\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])


class ExistingSingleTokenSurnameUnchangedTests(unittest.TestCase):
    """The pre-existing single-token case (no particle at all) must be
    completely unaffected by the particle addition."""

    def test_single_token_surname_still_round_trips(self):
        text = (
            "RAG systems combine retrieval with generation (Bose, 2025).\n"
            "\n"
            "## References\n"
            "\n"
            "Bose, R. (2025). Introduction to RAG. *Venue*. https://doi.org/10.1/x\n"
        )
        self.assertEqual(INTEGRITY.check_markers_and_bibliography(text), [])

    def test_single_token_surname_genuinely_uncited_still_fails(self):
        text = (
            "Body text with no citations at all.\n"
            "\n"
            "## References\n"
            "\n"
            "Bose, R. (2025). Introduction to RAG. *Venue*. https://doi.org/10.1/x\n"
        )
        failures = INTEGRITY.check_markers_and_bibliography(text)
        self.assertTrue(any("never cited" in f for f in failures))


class WordCountTests(unittest.TestCase):
    def test_no_target_means_no_check(self):
        self.assertEqual(INTEGRITY.check_word_count("one two three", None, 0.1), [])

    def test_word_count_within_tolerance_passes(self):
        text = " ".join(["word"] * 100)
        self.assertEqual(INTEGRITY.check_word_count(text, target=100, tolerance=0.1), [])

    def test_word_count_outside_tolerance_fails(self):
        text = " ".join(["word"] * 50)
        failures = INTEGRITY.check_word_count(text, target=100, tolerance=0.1)
        self.assertTrue(failures)
        self.assertIn("word count 50", failures[0])

    def test_word_count_counts_prose_not_markdown_syntax(self):
        """Finding 3: pipes, dashes, hashes and fences are not prose."""
        text = (
            "## Results\n"                                   # 1 prose word
            "\n"
            "| Study | Design | Outcome |\n"                 # 3
            "|-------|--------|---------|\n"                 # 0
            "| Bose  | Narrow | Positive |\n"                # 3
            "\n"
            "- first point\n"                                # 2
            "- second point\n"                               # 2
            "\n"
            "```python\n"
            "def rank(docs, key):\n"                         # 0, inside a fence
            "    return sorted(docs)\n"                      # 0, inside a fence
            "```\n"
            "\n"
            "---\n"                                          # 0
            "\n"
            "Final sentence here.\n"                         # 3
        )
        self.assertEqual(INTEGRITY.count_prose_words(text), 14)
        self.assertEqual(
            INTEGRITY.check_word_count(text, target=14, tolerance=0.1), [])

    def test_word_count_excludes_bibliography(self):
        # The bibliography section is long; only the body should count.
        body_words = ["word"] * 20
        text = " ".join(body_words) + "\n\n## References\n\n" + " ".join(["ref"] * 500)
        failures = INTEGRITY.check_word_count(text, target=20, tolerance=0.1)
        self.assertEqual(failures, [])


class TemplateTextTests(unittest.TestCase):
    def test_todo_marker_is_reported(self):
        text = "Some finished text.\nTODO: fill in the rest.\n"
        failures = INTEGRITY.check_template_text(text)
        self.assertTrue(any("TODO" in f for f in failures))

    def test_lorem_ipsum_is_reported(self):
        text = "Lorem ipsum dolor sit amet.\n"
        failures = INTEGRITY.check_template_text(text)
        self.assertTrue(failures)

    def test_insert_bracket_is_reported(self):
        text = "The author is [insert name here].\n"
        failures = INTEGRITY.check_template_text(text)
        self.assertTrue(failures)

    def test_your_name_here_is_reported(self):
        text = "Written by your name here.\n"
        failures = INTEGRITY.check_template_text(text)
        self.assertTrue(failures)

    def test_clean_text_has_no_template_failures(self):
        self.assertEqual(INTEGRITY.check_template_text(CLEAN_APA), [])

    def test_attribution_line_in_the_paper_body_fails_the_gate(self):
        """SKILL.md prints the attribution in conversation and never writes it
        into the paper. The gate is what makes that binding."""
        text = (
            "Built with opendraft (MIT). If it saved you time, a star helps: "
            "github.com/federicodeponte/opendraft\n"
        )
        failures = INTEGRITY.check_template_text(text)
        self.assertTrue(any("Built with opendraft" in f for f in failures))

    def test_attribution_line_appended_to_a_clean_draft_fails_run_checks(self):
        draft = CLEAN_APA + "\nBuilt with opendraft (MIT).\n"
        self.assertTrue(any("Built with opendraft" in f
                            for f in INTEGRITY.run_checks(draft)))


class CliExitCodeTests(unittest.TestCase):
    def test_cli_exits_nonzero_and_prints_report_on_failure(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text("TODO write this. {cite_10.1/missing}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAILED", result.stderr)
        self.assertIn("TODO", result.stderr)

    def test_cli_reports_missing_draft_file(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "/nonexistent/path/does-not-exist.md"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)


class MissingSourceMarkerTests(unittest.TestCase):
    """`{cite_MISSING: <description>}` is an honest marker and a fatal one. Each
    occurrence is one critical issue, reported with the drafter's description and
    with its own message, not swallowed by the leftover-template check."""

    CLAIM_A = "Kirkwood's disposable soma theory"
    CLAIM_B = "the 2019 replication rate for social priming"

    def _draft(self):
        return (
            "# Draft\n\n"
            f"Ageing trades repair against reproduction {{cite_MISSING: {self.CLAIM_A}}}.\n\n"
            f"Priming replicates poorly {{cite_MISSING: {self.CLAIM_B}}}.\n"
        )

    def test_each_marker_is_one_failure(self):
        failures = INTEGRITY.check_missing_sources(self._draft())
        self.assertEqual(len(failures), 2)

    def test_the_failure_quotes_the_drafters_own_description(self):
        joined = "\n".join(INTEGRITY.check_missing_sources(self._draft()))
        self.assertIn(self.CLAIM_A, joined)
        self.assertIn(self.CLAIM_B, joined)

    def test_the_failure_says_how_to_clear_it(self):
        joined = "\n".join(INTEGRITY.check_missing_sources(self._draft()))
        self.assertIn("sources.py find", joined)

    def test_run_checks_treats_it_as_a_failure(self):
        failures = INTEGRITY.run_checks(self._draft())
        self.assertTrue(any("unsourced claim" in f for f in failures))

    def test_it_is_not_swallowed_by_the_unresolved_placeholder_check(self):
        failures = INTEGRITY.run_checks(self._draft())
        self.assertFalse(any("placeholder" in f.lower() for f in failures),
                         msg=f"the specific message must win: {failures}")

    def test_a_marker_with_no_description_is_still_a_failure(self):
        failures = INTEGRITY.check_missing_sources("A bare claim {cite_MISSING}.\n")
        self.assertEqual(len(failures), 1)

    def test_a_real_placeholder_is_still_reported_as_a_placeholder(self):
        failures = INTEGRITY.run_checks("Body {cite_10.1/real}.\n")
        self.assertTrue(any("placeholder" in f.lower() for f in failures))

    def test_a_clean_draft_reports_no_missing_sources(self):
        self.assertEqual(INTEGRITY.check_missing_sources(CLEAN_APA), [])

    def test_cli_exits_nonzero_and_names_the_claim(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(self._draft(), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn(self.CLAIM_A, result.stderr)
        self.assertIn("unsourced claim", result.stderr)
        self.assertNotIn("placeholder", result.stderr.lower())


class BracketSlotCheckTests(unittest.TestCase):
    """Bidirectional proof for check_bracket_slots: every real authoring slot
    quoted verbatim (via `grep -o '\\[[^][]*\\]'`) from agents/07-crafter.md,
    agents/17-abstract.md and agents/05-architect.md must be caught, and every
    legitimate bracket use those same files, and the rest of this pipeline,
    can produce must not be. Each slot is embedded mid-sentence so the check
    is exercised the way it runs against a real compiled draft, not as a
    bracket standing alone on its own line.
    """

    # Every distinct multi-word slot the three agent files actually contain,
    # collected by grepping each file for `\[[^][]*\]` and deduplicating.
    REAL_SLOTS = [
        "reported effect, verbatim from summaries.md",
        "figure from summaries.md",
        "period from summaries.md",
        "r value from summaries.md",
        "dataset named in summaries.md",
        "range from summaries.md",
        "populations named in summaries.md",
        "HR range from summaries.md",
        "value from summaries.md",
        "CI from summaries.md",
        "cohorts named in summaries.md",
        "population or method named in summaries.md",
        "difference named in summaries.md or gaps.md",
        "the methodological difference summaries.md records",
        "number of sites, from summaries.md",
        "the access and sustainability indicators the body actually uses",
        "the relationship the body's analysis section actually reports, in the terms the body reports it",
        "the second contribution as the conclusion states it",
        "the technique the introduction names",
        "the outcome the introduction frames as the open question",
        "the approach the methodology section states",
        "The data or source set the methodology section actually names",
        "the specific method the methodology section states",
        "the finding, in the terms the results or discussion section actually reports it",
        "the first contribution as the conclusion states it",
        "the third contribution as the conclusion states it",
        "the implication the discussion draws",
        "the audience or decision the discussion names",
        "term one",
        "term two",
        "term three",
        "name the actual problem",
        "name the actual gap",
        "name the actual approach taken",
        "data or method",
        "what the results need to demonstrate",
        "name the actual contribution",
        "named direction",
        "from summaries.md",
        "UNSOURCED: what's needed",
    ]

    # Slots that appear in the same three files but are deliberately left
    # uncaught: single bare words (indistinguishable by shape alone from a
    # legitimate editorial insertion like "[sic]"), and the "2-3 sentences"
    # length hint, which is a documentation convention on the template
    # itself, not a value to look up and substitute.
    INTENTIONALLY_UNCAUGHT_REAL_SLOTS = [
        "topic", "terms", "study", "Field", "UNSOURCED",
        "2-3 sentences",
        "2-3 sentences: (1) ..., (2) ..., (3) ...",
    ]

    def _embed(self, slot):
        return f"Some sentence with a slot [{slot}] embedded in it.\n"

    def test_every_real_slot_from_the_three_agent_files_is_caught(self):
        missed = []
        for slot in self.REAL_SLOTS:
            if not INTEGRITY.check_bracket_slots(self._embed(slot)):
                missed.append(slot)
        self.assertEqual(missed, [], msg=f"these real slots were not caught: {missed}")

    def test_intentionally_uncaught_slots_are_not_flagged(self):
        false_positives = []
        for slot in self.INTENTIONALLY_UNCAUGHT_REAL_SLOTS:
            if INTEGRITY.check_bracket_slots(self._embed(slot)):
                false_positives.append(slot)
        self.assertEqual(false_positives, [],
                         msg=f"these should stay uncaught by design: {false_positives}")

    def test_numeric_citation_markers_are_not_flagged(self):
        cases = [
            "This finding [1] was replicated.\n",
            "See [12] for details.\n",
            "Multiple studies agree [1, 4].\n",
            "The effect held across the range [2-5].\n",
        ]
        for text in cases:
            self.assertEqual(INTEGRITY.check_bracket_slots(text), [], msg=text)

    def test_en_dash_numeric_range_is_not_flagged(self):
        # The most likely false positive: an en dash (U+2013) inside a
        # numeric citation range, which reads identically to a hyphen range
        # to a person but is a different character to a naive regex.
        text = "The effect held across the range [2–5] of studies.\n"
        self.assertEqual(INTEGRITY.check_bracket_slots(text), [])

    def test_markdown_links_and_images_are_not_flagged(self):
        cases = [
            "See the [documentation](https://example.com/docs) for details.\n",
            "![diagram of the pipeline](figures/diagram.png)\n",
            "As shown in [the appendix](#appendix) below.\n",
        ]
        for text in cases:
            self.assertEqual(INTEGRITY.check_bracket_slots(text), [], msg=text)

    def test_reference_style_links_and_footnotes_are_not_flagged(self):
        cases = [
            "See [my label][ref-1] for details.\n",
            "This claim needs a citation.[^1]\n",
            "[^1]: The footnote text itself.\n",
        ]
        for text in cases:
            self.assertEqual(INTEGRITY.check_bracket_slots(text), [], msg=text)

    def test_editorial_brackets_in_direct_quotation_are_not_flagged(self):
        # The second most likely false positive: a bracket a direct
        # quotation legitimately uses to mark an editorial insertion.
        cases = [
            'The report states "the model [sic] performed well."\n',
            'She writes, "[emphasis added] this changes everything."\n',
            "They [the authors] argue for immediate change.\n",
            'The paper notes "results were mixed [see Table 2]."\n',
        ]
        for text in cases:
            self.assertEqual(INTEGRITY.check_bracket_slots(text), [], msg=text)

    def test_task_list_syntax_is_not_flagged(self):
        cases = [
            "- [ ] an incomplete todo item\n",
            "- [x] a completed todo item\n",
        ]
        for text in cases:
            self.assertEqual(INTEGRITY.check_bracket_slots(text), [], msg=text)

    def test_bracket_at_end_of_line_is_still_caught(self):
        # Regression guard for the tail-check off-by-one: a slot with
        # nothing after the closing bracket (as several real slots in
        # agents/05-architect.md's fenced code examples are) must not be
        # mistaken for the start of a markdown link just because there is no
        # following character to inspect.
        text = "Results: evidence shows Z works: [what the results need to demonstrate]"
        self.assertTrue(INTEGRITY.check_bracket_slots(text))

    def test_numeric_marker_at_end_of_line_is_still_clean(self):
        text = "trailing citation marker at line end [12]"
        self.assertEqual(INTEGRITY.check_bracket_slots(text), [])

    def test_clean_drafts_are_unaffected(self):
        self.assertEqual(INTEGRITY.run_checks(CLEAN_APA), [])
        self.assertEqual(INTEGRITY.run_checks(CLEAN_IEEE), [])

    def test_run_checks_reports_the_line_number(self):
        text = "# Draft\n\nline one\n\nThe value was [figure from summaries.md] percent.\n"
        failures = INTEGRITY.run_checks(text)
        self.assertTrue(any("line 5" in f for f in failures), msg=failures)

    def test_cli_reports_a_surviving_slot_as_a_failure(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(
                "# Draft\n\nThe result was [figure from summaries.md] percent higher.\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("bracketed authoring slot", result.stderr)


class DatabaseCrossCheckTests(unittest.TestCase):
    """Task 2: -d/--database cross-checks every DOI printed in the compiled
    bibliography against the database. Both directions matter: a resolved
    DOI must not be flagged, and an unresolved or missing one must be.
    """

    def _db(self, records):
        return {"citations": records}

    def test_all_resolved_produces_no_failures(self):
        db = self._db({
            "10.1007/979-8-8688-1808-0_1": {"verified": "resolved"},
            "10.1038/s41586-021-03819-2": {"verified": "resolved"},
        })
        self.assertEqual(INTEGRITY.check_database_cross_check(CLEAN_APA, db), [])
        self.assertEqual(INTEGRITY.run_checks(CLEAN_APA, database=db), [])

    def test_unresolved_doi_is_a_failure_naming_the_doi_and_status(self):
        db = self._db({
            "10.1007/979-8-8688-1808-0_1": {"verified": "unknown"},
            "10.1038/s41586-021-03819-2": {"verified": "resolved"},
        })
        failures = INTEGRITY.check_database_cross_check(CLEAN_APA, db)
        self.assertEqual(len(failures), 1)
        self.assertIn("10.1007/979-8-8688-1808-0_1", failures[0])
        self.assertIn("unknown", failures[0])

    def test_doi_missing_from_database_entirely_is_a_failure(self):
        db = self._db({
            "10.1038/s41586-021-03819-2": {"verified": "resolved"},
        })
        failures = INTEGRITY.check_database_cross_check(CLEAN_APA, db)
        self.assertEqual(len(failures), 1)
        self.assertIn("10.1007/979-8-8688-1808-0_1", failures[0])
        self.assertIn("not in the citation database", failures[0])

    def test_empty_database_flags_every_doi_as_missing(self):
        failures = INTEGRITY.check_database_cross_check(CLEAN_APA, self._db({}))
        self.assertEqual(len(failures), 2)

    def test_run_checks_without_database_argument_skips_the_cross_check(self):
        # Passing no database at all must behave exactly as before this
        # feature existed: run_checks(text) with the old two-argument-style
        # call still works and never calls the cross-check.
        db = self._db({})  # would fail everything if it ran
        self.assertEqual(INTEGRITY.run_checks(CLEAN_APA), [])
        # Sanity: the same database WOULD produce failures if it were used.
        self.assertTrue(INTEGRITY.run_checks(CLEAN_APA, database=db))

    def test_cli_without_dash_d_is_silent_and_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_cli_with_dash_d_and_unresolved_doi_fails_and_says_the_cross_check_ran(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            db_path = Path(d) / "citations.json"
            db_path.write_text(json.dumps({"citations": {
                "10.1007/979-8-8688-1808-0_1": {"verified": "unknown"},
                "10.1038/s41586-021-03819-2": {"verified": "resolved"},
            }}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "-d", str(db_path)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("10.1007/979-8-8688-1808-0_1", result.stderr)
        self.assertIn("database cross-check: ran against", result.stderr)

    def test_cli_with_dash_d_and_all_resolved_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            db_path = Path(d) / "citations.json"
            db_path.write_text(json.dumps({"citations": {
                "10.1007/979-8-8688-1808-0_1": {"verified": "resolved"},
                "10.1038/s41586-021-03819-2": {"verified": "resolved"},
            }}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "-d", str(db_path)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_cli_failure_without_dash_d_says_cross_check_did_not_run(self):
        # A failing draft with no -d must not imply the DOI cross-check
        # passed; the header must say plainly that it did not run at all.
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA + "\nTODO: revisit this paragraph.\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("database cross-check: not run", result.stderr)

    def test_cli_reports_missing_database_file(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "-d", "/nonexistent/citations.json"],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)


CORPUS = (
    "# Summaries\n\n"
    "## Smith 2023\n"
    "A 34% improvement in triage accuracy across 1,200 participants.\n"
    "Inter-rater agreement was 0.91.\n\n"
    "## Jones 2024\n"
    "Cohort of 640; effect size 0.42.\n"
)


class TestNumberProvenance(unittest.TestCase):
    """The advisory check for numbers that appear nowhere in the corpus.

    check_bracket_slots catches a slot left unfilled. This catches the other
    half: a slot filled with something invented. Every test here names which
    half it is guarding.
    """

    def notes(self, body, corpus=CORPUS):
        return INTEGRITY.check_number_provenance(body, corpus)

    def test_invented_number_is_reported(self):
        text = "# D\n\nThe trial reported 0.83 agreement.\n"
        notes = self.notes(text)
        self.assertEqual(len(notes), 1, msg=notes)
        self.assertIn("0.83", notes[0])
        self.assertIn("line 3", notes[0])

    def test_number_present_in_the_corpus_is_not_reported(self):
        text = "# D\n\nAccuracy improved by 34% across 1,200 participants.\n"
        self.assertEqual(self.notes(text), [])

    def test_sentence_final_number_in_the_corpus_is_recognised(self):
        # Regression guard. The first version of _CLAIM_NUMBER ended with
        # (?![\w.]), which rejected any number followed by a period. That made
        # "effect size 0.42." in the corpus extract as no number at all, so a
        # correctly sourced 0.42 in the draft was reported as fabricated. A
        # provenance check whose corpus reader drops values manufactures the
        # very defect it exists to find, which is worse than not running.
        self.assertIn("0.42", INTEGRITY.corpus_numbers("effect size 0.42."))
        self.assertEqual(self.notes("# D\n\nThe effect size was 0.42.\n"), [])

    def test_comma_and_trailing_zero_forms_match(self):
        self.assertEqual(self.notes("# D\n\nWe enrolled 1200 people.\n"), [])
        self.assertEqual(self.notes("# D\n\nAgreement was 0.910.\n"), [])

    def test_hyphenated_names_are_not_numbers(self):
        for text in ("# D\n\nCOVID-19 changed triage.\n",
                     "# D\n\nGPT-4 outperformed the baseline.\n"):
            self.assertEqual(self.notes(text), [], msg=text)

    def test_version_strings_are_not_numbers(self):
        self.assertEqual(self.notes("# D\n\nWe used version 3.4.5 throughout.\n"), [])

    def test_standards_designations_are_not_numbers(self):
        for text in ("# D\n\nTimestamps follow ISO 8601 formatting.\n",
                     "# D\n\nThe wording follows RFC 2119.\n"):
            self.assertEqual(self.notes(text), [], msg=text)

    def test_an_acronym_does_not_hide_a_number(self):
        # The complement of the test above, and the reason the standards list
        # is a short closed set rather than a general "an acronym precedes it"
        # rule: a fabricated number is exactly what would hide behind one.
        notes = self.notes("# D\n\nThe RCT reported 77% retention.\n")
        self.assertTrue(any("77" in n for n in notes), msg=notes)

    def test_document_labels_are_not_numbers(self):
        for text in ("# D\n\nFigure 2 shows the split.\n",
                     "# D\n\nSee Table 1 for the breakdown.\n",
                     "# D\n\nSection 3 covers the method.\n"):
            self.assertEqual(self.notes(text), [], msg=text)

    def test_an_ordinary_word_is_not_a_document_label(self):
        # "no", "part", "issue" and "page" are label words and ordinary
        # English words both. Matching them case-insensitively exempted
        # whatever number happened to follow them in running prose.
        for text in ("# D\n\nThere were no 38 percent gains anywhere.\n",
                     "# D\n\nThe issue 47 percent of respondents raised was cost.\n"):
            self.assertTrue(self.notes(text), msg=f"not flagged: {text!r}")

    def test_a_real_label_still_keeps_its_exemption(self):
        # The complement: abbreviated with a period or capitalised, these are
        # genuine labels and must stay exempt.
        for text in ("# D\n\nSee no. 47 in the appendix listing.\n",
                     "# D\n\nPart 3 covers the method.\n",
                     "# D\n\nQuoted at pp. 88 of the original.\n"):
            self.assertEqual(self.notes(text), [], msg=text)

    def test_years_are_not_measurements(self):
        self.assertEqual(self.notes("# D\n\nThe survey ran in 2019 and 2021.\n"), [])

    def test_a_count_inside_the_year_band_is_still_a_measurement(self):
        # The year exemption is the widest one here, and a cohort size lands
        # inside it constantly: "n = 2000" and "a sample of 1,847" are exactly
        # the numbers this check exists to question, and a blanket band would
        # have waved both through. The exemption is withdrawn wherever the
        # number is doing a counting job, named either side of it.
        for text in ("# D\n\nThe study included n = 2000 participants.\n",
                     "# D\n\nWe drew a sample of 1,847 records.\n",
                     "# D\n\nThe 1950 respondents completed both waves.\n"):
            notes = self.notes(text)
            self.assertTrue(notes, msg=f"not flagged: {text!r}")

    def test_a_publication_year_keeps_its_exemption(self):
        # The complement: withdrawing the exemption must not cost the ordinary
        # case, or every paper citing a date acquires a page of advisories.
        for text in ("# D\n\nPublished in 2019, the guidance changed.\n",
                     "# D\n\nThe 2019 cohort is described elsewhere.\n"):
            self.assertEqual(self.notes(text), [], msg=text)

    def test_a_measurement_inside_the_year_band_is_not_a_year(self):
        # The count-noun fix closed "n = 2000 participants" and left every
        # other kind of unit open, which is the same route one word to the
        # right: a fabricated cost, dose or duration landing in the 1900-2100
        # band still read as a publication date and was waved through.
        for text in ("# D\n\nThe intervention cost 1,950 euros per patient.\n",
                     "# D\n\nEach dose contained 1975 mg of the compound.\n",
                     "# D\n\nTraining required 2050 hours of staff time.\n",
                     "# D\n\nMean cost per case was $2,075 across sites.\n"):
            self.assertTrue(self.notes(text), msg=f"not flagged: {text!r}")

    def test_conventional_thresholds_are_not_measurements(self):
        self.assertEqual(self.notes("# D\n\nSignificance was set at p < 0.05.\n"), [])

    def test_a_spelled_out_percentage_is_read(self):
        # The digits-only boundary was a real hole: writing the same
        # fabrication in words walked straight through a check whose whole
        # purpose is to question it, and the digit twin two words away was
        # caught. The percent word is what marks it as a measurement.
        notes = self.notes("# D\n\nAccuracy rose by seventy-seven percent.\n")
        self.assertTrue(notes, msg="spelled-out fabrication not flagged")
        self.assertIn("seventy-seven", notes[0])
        self.assertIn("77", notes[0])

    def test_a_spelled_out_percentage_present_in_the_corpus_is_not_reported(self):
        # CORPUS records "34%". Spelling it out is the same figure, and
        # reporting it would manufacture the defect this check exists to find.
        self.assertEqual(self.notes("# D\n\nA thirty-four percent gain held.\n"), [])

    def test_a_corpus_that_spells_a_percentage_makes_the_digits_known(self):
        # The other direction, and the reason the corpus reader has to change
        # too: a corpus writing "twelve percent" must make a draft's "12%"
        # known, or a correctly sourced figure is reported as invented purely
        # because the two spelled it differently.
        corpus = "## A\nThe pooled analysis found a twelve percent improvement.\n"
        self.assertEqual(self.notes("# D\n\nAccuracy improved by 12%.\n", corpus), [])

    def test_ordinary_prose_numbers_are_not_measurements(self):
        # The reason this is gated on the percent word rather than reading
        # every spelled number. Prose is full of these, none is a measurement,
        # and an advisory list mostly made of them is one nobody reads.
        text = ("# D\n\nOne of the studies used two approaches, and three "
                "coders reviewed the sample of ten records.\n")
        self.assertEqual(self.notes(text), [])

    def test_percentage_point_and_scale_forms_are_read(self):
        for body, shown in (("It rose by forty-one percentage points.", "41"),
                            ("Coverage reached one hundred percent.", "100"),
                            ("Growth hit two thousand percent.", "2000"),
                            ("Uptake was fifty-eight per cent.", "58")):
            notes = self.notes(f"# D\n\n{body}\n")
            self.assertTrue(notes, msg=f"not flagged: {body!r}")
            self.assertIn(shown, notes[0], msg=notes)

    def test_a_threshold_value_is_exempt_only_in_threshold_context(self):
        # _CI_LEVELS was context-gated after a smuggling route was found in
        # it; _CONVENTIONAL was left unconditional, which is the same hole in
        # the same function. 0.1 is a plausible effect size, 0.05 a plausible
        # proportion and 0.01 a plausible rate, so all three inherited an
        # exemption written for "p < 0.05" and were never read.
        for text in (
                "# D\n\nThe observed effect size was 0.1 standard deviations.\n",
                "# D\n\nOnly 0.05 of the eligible sample completed.\n",
                "# D\n\nAttrition ran at 0.01 per participant-week.\n"):
            self.assertTrue(self.notes(text), msg=f"not flagged: {text!r}")

    def test_threshold_context_keeps_its_exemption(self):
        # The complement: the convention itself must never be flagged, or
        # every paper that states its alpha collects an advisory for doing so.
        for text in ("# D\n\nWe used alpha = 0.01 throughout.\n",
                     "# D\n\nTests used a significance level of 0.001.\n",
                     "# D\n\nRejected at the 0.05 level.\n"):
            self.assertEqual(self.notes(text), [], msg=text)

    def test_confidence_level_is_exempt_only_in_context(self):
        self.assertEqual(
            self.notes("# D\n\nWe report a 95% CI throughout.\n"), [])
        # The same 95 with no interval context is an ordinary claim.
        notes = self.notes("# D\n\nRetention reached 95% by week four.\n")
        self.assertTrue(any("95" in n for n in notes), msg=notes)
        # And the prefix form is exempt too.
        self.assertEqual(
            self.notes("# D\n\nEstimates use a confidence level of 95%.\n"), [])

    def test_an_interval_elsewhere_on_the_line_does_not_exempt_the_claim(self):
        # The first version searched the whole line for "CI", which is a
        # smuggling route: a parenthesised interval at the end of the sentence
        # exempted the reported figure at the front of it. Here the reported
        # 95% is the fabricated one and the interval is incidental.
        text = "# D\n\nRetention was 95% by week four (95% CI 0.81 to 0.94).\n"
        notes = self.notes(text)
        self.assertTrue(any("'95'" in n for n in notes), msg=notes)

    def test_numeric_citation_markers_are_not_measurements(self):
        self.assertEqual(self.notes("# D\n\nPrior work agrees [17], [22-24].\n"), [])

    def test_bibliography_is_not_scanned(self):
        text = (
            "# D\n\nAccuracy improved by 34%.\n\n"
            "## References\n\n"
            "[1] Smith, J. (2023). *Journal*, 12(4), 881-899.\n"
        )
        self.assertEqual(self.notes(text), [])

    def test_fenced_code_is_not_scanned(self):
        text = "# D\n\n```python\nthreshold = 4242\n```\n"
        self.assertEqual(self.notes(text), [])

    def test_a_bare_fence_is_a_figure_and_is_scanned(self):
        # agents/16-enhancer.md has stage 16 draw ASCII diagrams in bare
        # fences, so a bare fence in a draft carries content, not code. While
        # every fence was skipped alike, a number invented into a diagram was
        # the one place in the draft this check could not see.
        text = "# D\n\n```\nAdoption 62%  ---->  Retention 41%\n```\n"
        notes = self.notes(text)
        self.assertTrue(any("62" in n for n in notes), msg=notes)

    def test_a_tagged_fence_after_a_bare_one_is_still_code(self):
        # The fence state has to remember the opening info string rather than
        # toggle one flag, or the second fence in a draft inherits the first
        # fence's treatment and the distinction collapses on any real file.
        text = ("# D\n\n```\nAdoption 62%\n```\n\n"
                "```python\nthreshold = 4242\n```\n")
        notes = self.notes(text)
        self.assertTrue(any("62" in n for n in notes), msg=notes)
        self.assertFalse(any("4242" in n for n in notes), msg=notes)

    def test_table_rows_are_scanned(self):
        # The opposite of check_stranded_punctuation's exemption, and
        # deliberately so: stage 5 requires a synthesis table, which is
        # precisely where a fabricated effect size would be written.
        text = "# D\n\n| Study | Effect |\n|---|---|\n| Smith | 0.77 |\n"
        notes = self.notes(text)
        self.assertTrue(any("0.77" in n for n in notes), msg=notes)

    def test_run_reviews_is_silent_without_a_corpus(self):
        self.assertEqual(INTEGRITY.run_reviews("# D\n\nA 0.83 result.\n"), [])

    def test_reviews_never_change_run_checks(self):
        text = "# D\n\nA 0.83 result.\n"
        self.assertEqual(INTEGRITY.run_checks(text), [])

    def test_cli_prints_the_advisory_and_still_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            corpus = Path(d) / "summaries.md"
            draft.write_text(CLEAN_APA.replace(
                "RAG systems combine retrieval with generation",
                "RAG systems improved recall by 0.83 percentage points"),
                encoding="utf-8")
            corpus.write_text(CORPUS, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "-c", str(corpus)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Advisory", result.stderr)
        self.assertIn("0.83", result.stderr)

    def test_cli_is_silent_without_the_corpus_flag(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft)],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.strip(), "")

    def test_cli_reports_a_missing_corpus_file(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "-c", "/nonexistent/summaries.md"],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("corpus not found", result.stderr)


# --- the brief's own numbers ------------------------------------------------

def _draft(body_words, refs=2, abstract_words=None, sections=(), ref_words=0):
    """A compiled draft with a controlled main-text length and reference count.

    Shaped the way stage 18 leaves one: a single level-1 title, the abstract
    under its own heading, body sections under theirs, references last.
    """
    out = ["# Test Draft", ""]
    if abstract_words is not None:
        out += ["## Abstract", "", " ".join(["summary"] * abstract_words), ""]
    # Every bibliography entry is cited, because the gate already checks that
    # and an uncited entry would fail these drafts for the wrong reason.
    cited = " ".join(f"A claim (Author{i}, {2020 + i})." for i in range(refs))
    names = list(sections) or ["Body"]
    per, extra = divmod(max(body_words, 0), len(names))
    for i, name in enumerate(names):
        count = per + (extra if i == 0 else 0)
        prose = " ".join(["word"] * count)
        if i == 0 and cited:
            prose = (prose + " " + cited).strip()
        out += [f"## {name}", "", prose, ""]
    out += ["## References", ""]
    padding = (" " + " ".join(["subtitle"] * ref_words)) if ref_words else ""
    for i in range(refs):
        out.append(f"Author{i}, A. ({2020 + i}). A title number {i}.{padding} *Venue*.")
        out.append("")
    return "\n".join(out)


class SectionParsingTests(unittest.TestCase):
    def test_a_heading_inside_a_fenced_block_is_not_a_section(self):
        text = "# Title\n\n```\n# not a heading\n```\n\n## Real\n\nBody.\n"
        titles = [t for _l, t, _s, _e in INTEGRITY.sections(text)]
        self.assertEqual(titles, ["Title", "Real"])

    def test_a_section_ends_at_the_next_heading_of_the_same_level(self):
        text = "## One\n\nA.\n\n### Deeper\n\nB.\n\n## Two\n\nC.\n"
        spans = {t: (s, e) for _l, t, s, e in INTEGRITY.sections(text)}
        self.assertEqual(spans["One"][1], spans["Two"][0])
        self.assertEqual(spans["Deeper"][1], spans["Two"][0])


class AbstractLocationTests(unittest.TestCase):
    def test_a_summary_heading_is_the_same_section_as_an_abstract(self):
        found = INTEGRITY.find_abstract("## Summary\n\nOne two three.\n")
        self.assertIsNotNone(found)
        self.assertEqual(found[0], "Summary")

    def test_a_german_zusammenfassung_counts_as_one(self):
        found = INTEGRITY.find_abstract("## Zusammenfassung\n\nEin Satz hier.\n")
        self.assertIsNotNone(found)

    def test_a_draft_with_no_abstract_returns_none(self):
        self.assertIsNone(INTEGRITY.find_abstract("# Title\n\n## Introduction\n\nX.\n"))


class MainTextCountTests(unittest.TestCase):
    def test_the_bibliography_is_not_main_text(self):
        # Same body, same citations, a bibliography ten times the size: the
        # main-text count does not move.
        short = INTEGRITY.count_main_text_words(_draft(100, refs=8))
        long = INTEGRITY.count_main_text_words(_draft(100, refs=8, ref_words=40))
        self.assertEqual(short, long)

    def test_the_abstract_is_not_main_text(self):
        # A brief that caps the main text and the abstract separately is
        # counting them separately.
        plain = INTEGRITY.count_main_text_words(_draft(100))
        with_abstract = INTEGRITY.count_main_text_words(_draft(100, abstract_words=200))
        self.assertEqual(plain, with_abstract)

    def test_reference_entries_are_counted_one_per_entry(self):
        self.assertEqual(INTEGRITY.count_reference_entries(_draft(50, refs=7)), 7)

    def test_a_draft_with_no_bibliography_has_no_entries(self):
        self.assertEqual(INTEGRITY.count_reference_entries("# T\n\nBody.\n"), 0)


class BriefWordRangeTests(unittest.TestCase):
    def test_a_draft_inside_the_range_passes(self):
        self.assertEqual(INTEGRITY.check_word_range(_draft(300), 250, 350), [])

    def test_a_draft_over_the_cap_fails_and_says_by_how_much(self):
        failures = INTEGRITY.check_word_range(_draft(500), 100, 200)
        self.assertEqual(len(failures), 1)
        self.assertIn("Cut", failures[0])

    def test_a_draft_under_the_floor_fails(self):
        failures = INTEGRITY.check_word_range(_draft(50), 400, 600)
        self.assertEqual(len(failures), 1)
        self.assertIn("under", failures[0])

    def test_no_range_checks_nothing(self):
        self.assertEqual(INTEGRITY.check_word_range(_draft(9000), None, None), [])


class BriefReferenceCountTests(unittest.TestCase):
    def test_meeting_the_minimum_passes(self):
        self.assertEqual(INTEGRITY.check_reference_count(_draft(50, refs=24), 24), [])

    def test_falling_short_fails_and_says_to_search_further(self):
        failures = INTEGRITY.check_reference_count(_draft(50, refs=10), 24)
        self.assertEqual(len(failures), 1)
        self.assertIn("10", failures[0])
        self.assertIn("stage 1", failures[0])

    def test_no_minimum_checks_nothing(self):
        self.assertEqual(INTEGRITY.check_reference_count(_draft(50, refs=1), None), [])


class BriefAbstractTests(unittest.TestCase):
    def test_an_abstract_inside_the_cap_passes(self):
        self.assertEqual(INTEGRITY.check_abstract(_draft(200, abstract_words=150), 250), [])

    def test_a_missing_abstract_fails_when_the_brief_asks_for_one(self):
        failures = INTEGRITY.check_abstract(_draft(200), 250)
        self.assertEqual(len(failures), 1)
        self.assertIn("no abstract", failures[0])

    def test_an_over_long_abstract_fails(self):
        failures = INTEGRITY.check_abstract(_draft(200, abstract_words=400), 250)
        self.assertEqual(len(failures), 1)
        self.assertIn("over", failures[0])

    def test_an_empty_abstract_heading_is_not_an_abstract(self):
        failures = INTEGRITY.check_abstract("# T\n\n## Abstract\n\n## Introduction\n\nX.\n", 250)
        self.assertEqual(len(failures), 1)
        self.assertIn("empty", failures[0])

    def test_no_cap_checks_nothing(self):
        self.assertEqual(INTEGRITY.check_abstract(_draft(200), None), [])


class BriefRequiredSectionTests(unittest.TestCase):
    def test_every_named_section_present_passes(self):
        text = _draft(200, sections=("Introduction", "Methodology", "Conclusion"))
        self.assertEqual(
            INTEGRITY.check_required_sections(
                text, ["Introduction", "Methodology", "Conclusion", "References"]), [])

    def test_a_missing_section_is_named_in_the_failure(self):
        text = _draft(200, sections=("Introduction",))
        failures = INTEGRITY.check_required_sections(text, ["Introduction", "Methodology"])
        self.assertEqual(len(failures), 1)
        self.assertIn("Methodology", failures[0])

    def test_matching_ignores_case_and_surrounding_words(self):
        text = _draft(200, sections=("2. Methodology and Data",))
        self.assertEqual(INTEGRITY.check_required_sections(text, ["methodology"]), [])

    def test_no_named_sections_checks_nothing(self):
        self.assertEqual(INTEGRITY.check_required_sections(_draft(50), []), [])


class BriefFileTests(unittest.TestCase):
    def _write(self, payload):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / "brief.json"
        path.write_text(payload, encoding="utf-8")
        return path

    def test_a_word_range_pair_becomes_a_min_and_a_max(self):
        brief = INTEGRITY.normalise_brief({"word_range": [2700, 3300]})
        self.assertEqual((brief["words_min"], brief["words_max"]), (2700, 3300))

    def test_an_unknown_key_is_an_error_rather_than_an_omission(self):
        # A misspelt key that is silently ignored turns a stated requirement
        # into an unchecked one.
        with self.assertRaises(INTEGRITY.BriefError) as caught:
            INTEGRITY.normalise_brief({"min_refrences": 24})
        self.assertIn("min_refrences", str(caught.exception))

    def test_a_non_integer_number_is_an_error(self):
        with self.assertRaises(INTEGRITY.BriefError):
            INTEGRITY.normalise_brief({"min_references": "twenty-four"})

    def test_a_malformed_word_range_is_an_error(self):
        with self.assertRaises(INTEGRITY.BriefError):
            INTEGRITY.normalise_brief({"word_range": [3000]})

    def test_required_sections_have_to_be_strings(self):
        with self.assertRaises(INTEGRITY.BriefError):
            INTEGRITY.normalise_brief({"required_sections": [1, 2]})

    def test_an_empty_brief_states_nothing_and_checks_nothing(self):
        brief = INTEGRITY.normalise_brief({})
        self.assertEqual(INTEGRITY.run_checks(CLEAN_APA, brief=brief),
                         INTEGRITY.run_checks(CLEAN_APA))

    def test_a_brief_file_loads_from_disk(self):
        path = self._write('{"min_references": 12, "abstract_max_words": 200}')
        brief = INTEGRITY.load_brief(path)
        self.assertEqual(brief["min_references"], 12)
        self.assertEqual(brief["abstract_max_words"], 200)

    def test_invalid_json_is_a_brief_error(self):
        with self.assertRaises(INTEGRITY.BriefError):
            INTEGRITY.load_brief(self._write("{not json"))


class BriefFlagTests(unittest.TestCase):
    def _args(self, argv):
        return INTEGRITY._build_parser().parse_args(argv)

    def test_flags_alone_build_a_brief(self):
        brief = INTEGRITY.brief_from_args(self._args(
            ["d.md", "--word-range", "1200-1500", "--min-references", "8",
             "--abstract-max", "150", "--require-section", "Methodology"]))
        self.assertEqual((brief["words_min"], brief["words_max"]), (1200, 1500))
        self.assertEqual(brief["min_references"], 8)
        self.assertEqual(brief["abstract_max_words"], 150)
        self.assertEqual(brief["required_sections"], ["Methodology"])

    def test_repeating_require_section_accumulates(self):
        brief = INTEGRITY.brief_from_args(self._args(
            ["d.md", "--require-section", "Introduction", "--require-section", "Conclusion"]))
        self.assertEqual(brief["required_sections"], ["Introduction", "Conclusion"])

    def test_a_backwards_range_is_rejected(self):
        with self.assertRaises(INTEGRITY.BriefError):
            INTEGRITY.brief_from_args(self._args(["d.md", "--word-range", "1500-1200"]))

    def test_a_range_that_is_not_a_range_is_rejected(self):
        with self.assertRaises(INTEGRITY.BriefError):
            INTEGRITY.brief_from_args(self._args(["d.md", "--word-range", "about 1500"]))


class BriefGateTests(unittest.TestCase):
    """The gate itself: the checks run, and they decide the exit code."""

    def _run(self, text, extra, brief_json=None):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(text, encoding="utf-8")
            argv = [sys.executable, str(SCRIPT), str(draft)] + extra
            if brief_json is not None:
                brief = Path(d) / "brief.json"
                brief.write_text(brief_json, encoding="utf-8")
                argv += ["-b", str(brief)]
            return subprocess.run(argv, check=False, capture_output=True, text=True)

    def test_a_draft_short_of_the_reference_minimum_fails_the_gate(self):
        result = self._run(_draft(400, refs=3), [], '{"min_references": 24}')
        self.assertEqual(result.returncode, 1)
        self.assertIn("reference list has 3", result.stdout + result.stderr)

    def test_a_draft_meeting_every_stated_number_passes(self):
        text = _draft(400, refs=6, abstract_words=120,
                      sections=("Introduction", "Conclusion"))
        result = self._run(text, [], json.dumps({
            "word_range": [300, 500], "min_references": 6,
            "abstract_max_words": 250,
            "required_sections": ["Introduction", "Conclusion", "References"]}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_missing_brief_file_is_reported_not_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.md"
            draft.write_text(CLEAN_APA, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "-b", "/nonexistent/brief.json"],
                check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("brief not found", result.stderr)

    def test_a_bad_brief_file_is_rejected_before_the_draft_is_read(self):
        result = self._run(_draft(400), [], '{"min_refrences": 24}')
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown key", result.stderr)

    def test_flags_override_the_file(self):
        result = self._run(_draft(400, refs=3), ["--min-references", "3"],
                           '{"min_references": 24}')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_stats_prints_the_numbers_and_checks_nothing(self):
        # A draft that would fail the gate still exits 0 under --stats, because
        # --stats is for counting a draft while it is still being written.
        result = self._run(_draft(400, refs=2, abstract_words=90), ["--stats"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("main text words:", result.stdout)
        self.assertIn("abstract words:    90", result.stdout)
        self.assertIn("reference entries: 2", result.stdout)

    def test_stats_says_so_when_there_is_no_abstract(self):
        result = self._run(_draft(400), ["--stats"])
        self.assertIn("no abstract section", result.stdout)


if __name__ == "__main__":
    unittest.main()
