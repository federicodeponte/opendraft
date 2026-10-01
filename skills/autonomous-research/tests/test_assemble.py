"""Tests for scripts/assemble.py.

The command line is fixed by SKILL.md as `assemble.py sections -o full_draft.md`:
a positional source directory and -o for the output. These tests call it that
way on purpose, so the script and the documented invocation cannot drift apart
without a test going red.
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "assemble.py"
SPEC = importlib.util.spec_from_file_location("opendraft_assemble", SCRIPT)
ASSEMBLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSEMBLE)


def _sections(tmp, files):
    d = Path(tmp) / "sections"
    d.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args],
                          check=False, capture_output=True, text=True)


class HappyPathTests(unittest.TestCase):
    def test_sections_are_merged_in_numeric_not_lexical_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "# Introduction\n\nFirst.\n",
                "02_methods.md": "# Methods\n\nSecond.\n",
                "10_conclusion.md": "# Conclusion\n\nTenth.\n",
                "03_results.md": "# Results\n\nThird.\n",
                "04_a.md": "# A\n\nFourth.\n",
                "05_b.md": "# B\n\nFifth.\n",
                "06_c.md": "# C\n\nSixth.\n",
                "07_d.md": "# D\n\nSeventh.\n",
                "08_e.md": "# E\n\nEighth.\n",
                "09_f.md": "# F\n\nNinth.\n",
            })
            out = Path(tmp) / "full_draft.md"
            code = ASSEMBLE.main([str(d), "-o", str(out)])
            self.assertEqual(code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertLess(text.index("Ninth."), text.index("Tenth."))
            self.assertLess(text.index("First."), text.index("Second."))
            self.assertTrue(text.endswith("\n"))

    def test_dash_separator_and_bare_number_names_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01-introduction.md": "Alpha.\n",
                "02-methods.md": "Beta.\n",
            })
            out = Path(tmp) / "full_draft.md"
            self.assertEqual(ASSEMBLE.main([str(d), "-o", str(out)]), 0)
            self.assertIn("Alpha.", out.read_text(encoding="utf-8"))


class NumberingTests(unittest.TestCase):
    def test_a_gap_in_the_numbering_fails_and_names_the_missing_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "First.\n",
                "03_results.md": "Third.\n",
            })
            out = Path(tmp) / "full_draft.md"
            result = _run(d, "-o", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("02", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.exists())

    def test_a_duplicate_number_fails_and_names_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "First.\n",
                "01_intro-alt.md": "Also first.\n",
                "02_methods.md": "Second.\n",
            })
            out = Path(tmp) / "full_draft.md"
            result = _run(d, "-o", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("01_introduction.md", result.stderr)
            self.assertIn("01_intro-alt.md", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.exists())

    def test_an_empty_sections_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {})
            out = Path(tmp) / "full_draft.md"
            result = _run(d, "-o", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no numbered section", result.stderr.lower())
            self.assertFalse(out.exists())

    def test_a_missing_sections_directory_fails_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(Path(tmp) / "nope", "-o", Path(tmp) / "x.md")
            self.assertEqual(result.returncode, 1)
            self.assertIn("not found", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class ReportExclusionTests(unittest.TestCase):
    def test_unnumbered_files_are_never_spliced_into_the_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "First.\n",
                "02_methods.md": "Second.\n",
                "notes.md": "SCRATCH NOTES, not part of the paper.\n",
                "README.md": "How this directory works.\n",
            })
            out = Path(tmp) / "full_draft.md"
            self.assertEqual(ASSEMBLE.main([str(d), "-o", str(out)]), 0)
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("SCRATCH NOTES", text)
            self.assertNotIn("How this directory works", text)

    def test_a_numbered_qa_report_is_never_spliced_into_the_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "First.\n",
                "02_methods.md": "Second.\n",
                "08_thread-report.md": "REPORT BODY: three continuity breaks.\n",
            })
            out = Path(tmp) / "full_draft.md"
            code = ASSEMBLE.main([str(d), "-o", str(out)])
            self.assertEqual(code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("REPORT BODY", text)

    def test_a_numbered_qa_report_does_not_count_as_a_numbering_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "First.\n",
                "02_methods.md": "Second.\n",
                "08_thread-report.md": "REPORT BODY.\n",
            })
            out = Path(tmp) / "full_draft.md"
            self.assertEqual(ASSEMBLE.main([str(d), "-o", str(out)]), 0)


class CheckModeTests(unittest.TestCase):
    def test_check_reports_what_it_would_merge_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {
                "01_introduction.md": "First.\n",
                "02_methods.md": "Second.\n",
                "notes.md": "Scratch.\n",
            })
            out = Path(tmp) / "full_draft.md"
            result = _run(d, "-o", out, "--check")
            self.assertEqual(result.returncode, 0)
            self.assertIn("01_introduction.md", result.stdout)
            self.assertIn("02_methods.md", result.stdout)
            self.assertIn("notes.md", result.stdout)
            self.assertFalse(out.exists())

    def test_check_still_fails_on_a_numbering_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n", "03_c.md": "C.\n"})
            result = _run(d, "-o", Path(tmp) / "full_draft.md", "--check")
            self.assertEqual(result.returncode, 1)


class OverwriteGuardTests(unittest.TestCase):
    def test_an_existing_output_is_not_overwritten_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n", "02_b.md": "B.\n"})
            out = Path(tmp) / "full_draft.md"
            out.write_text("EDITED BY HAND\n", encoding="utf-8")
            result = _run(d, "-o", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("--force", result.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), "EDITED BY HAND\n")

    def test_force_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n", "02_b.md": "B.\n"})
            out = Path(tmp) / "full_draft.md"
            out.write_text("EDITED BY HAND\n", encoding="utf-8")
            self.assertEqual(
                ASSEMBLE.main([str(d), "-o", str(out), "--force"]), 0)
            self.assertNotIn("EDITED BY HAND", out.read_text(encoding="utf-8"))

    def test_check_does_not_trip_the_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n", "02_b.md": "B.\n"})
            out = Path(tmp) / "full_draft.md"
            out.write_text("EDITED BY HAND\n", encoding="utf-8")
            result = _run(d, "-o", out, "--check")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "EDITED BY HAND\n")


class DocumentedInterfaceTests(unittest.TestCase):
    """SKILL.md documents exactly one invocation. It has to be the real one."""

    def test_documented_invocation_works_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            _sections(tmp, {"01_a.md": "A.\n", "02_b.md": "B.\n"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "sections", "-o", "full_draft.md"],
                cwd=tmp, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(tmp) / "full_draft.md").exists())

    def test_source_directory_is_positional_not_a_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n"})
            result = _run("--sections", d, "-o", Path(tmp) / "full_draft.md")
            self.assertNotEqual(result.returncode, 0)

    def test_refusal_message_names_what_a_forced_rerun_would_discard(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n", "02_b.md": "B.\n"})
            out = Path(tmp) / "full_draft.md"
            out.write_text("EDITED BY HAND\n", encoding="utf-8")
            result = _run(d, "-o", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("--force", result.stderr)
            self.assertIn("10", result.stderr)
            self.assertIn("15", result.stderr)
            self.assertIn("discards", result.stderr.lower())


class SeparationTests(unittest.TestCase):
    def test_sections_are_separated_by_a_blank_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "# A\n\nAlpha.", "02_b.md": "# B\n\nBeta.\n\n\n"})
            out = Path(tmp) / "full_draft.md"
            self.assertEqual(ASSEMBLE.main([str(d), "-o", str(out)]), 0)
            self.assertEqual(out.read_text(encoding="utf-8"),
                             "# A\n\nAlpha.\n\n# B\n\nBeta.\n")

    def test_an_empty_section_file_fails_rather_than_silently_merging(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _sections(tmp, {"01_a.md": "A.\n", "02_b.md": "   \n"})
            out = Path(tmp) / "full_draft.md"
            result = _run(d, "-o", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("02_b.md", result.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
