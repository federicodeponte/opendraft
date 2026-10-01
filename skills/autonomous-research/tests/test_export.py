"""Export metadata: the exported paper has to carry its own title.

`pandoc -s` with no title metadata falls back to the source filename, so every
paper this bundle exported to HTML arrived titled "final" in the browser tab,
in the bookmark, and in every link preview that reads that element. Nothing
caught it: the file existed, the exit code was 0, and nobody reads a `<title>`
during a run. An end-to-end run found it by opening the output.

These tests exercise the extraction directly rather than through pandoc, so
they run on a machine that has no pandoc installed.
"""
import importlib.util
import re
import shutil
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


def _load(name, filename):
    script = Path(__file__).parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPORT = _load("opendraft_export", "export.py")


class DocumentTitleTests(unittest.TestCase):
    def _write(self, text):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "final.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_first_level_one_heading_is_the_title(self):
        path = self._write(
            "# Grounded but Unproven: A Narrative Review\n"
            "\n"
            "# Introduction\n"
            "\n"
            "Every section heading in this pipeline is also level one, so the\n"
            "first one has to win.\n")
        self.assertEqual(EXPORT._document_title(path),
                         "Grounded but Unproven: A Narrative Review")

    def test_a_comment_inside_a_code_fence_is_not_the_title(self):
        path = self._write(
            "```bash\n"
            "# python3 scripts/export.py final.md --format html\n"
            "```\n"
            "\n"
            "# The Real Title\n")
        self.assertEqual(EXPORT._document_title(path), "The Real Title")

    def test_a_document_with_no_level_one_heading_has_no_title(self):
        path = self._write("## Introduction\n\nText.\n")
        self.assertIsNone(EXPORT._document_title(path))

    def test_an_empty_heading_is_not_a_title(self):
        path = self._write("# \n\nText.\n")
        self.assertIsNone(EXPORT._document_title(path))

    def test_the_title_reaches_pandoc_as_metadata(self):
        path = self._write("# A Real Title\n")
        self.assertEqual(EXPORT._title_metadata(path),
                         ["--metadata", "title=A Real Title"])

    def test_no_metadata_flag_is_passed_when_there_is_no_title(self):
        path = self._write("Text with no heading at all.\n")
        self.assertEqual(EXPORT._title_metadata(path), [])

    def test_a_missing_file_yields_no_title_rather_than_an_error(self):
        self.assertIsNone(EXPORT._document_title(Path("/nonexistent/final.md")))


class HtmlCommandTests(unittest.TestCase):
    """The title has to reach pandoc, not merely be extractable.

    Testing `_title_metadata` alone would pass whether or not anything called
    it, which is the shape of guard that lets a fix be reverted silently. These
    capture the command the exporter actually builds.
    """

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src = Path(tmp.name) / "final.md"
        self.src.write_text("# A Real Title\n\nBody text.\n", encoding="utf-8")
        self.out = Path(tmp.name) / "final.html"
        self.seen = []
        original = EXPORT._run
        self.addCleanup(lambda: setattr(EXPORT, "_run", original))
        EXPORT._run = self._capture

    def _capture(self, cmd, **kwargs):
        self.seen.append(cmd)
        return 0, "", ""

    def test_export_html_passes_the_title_to_pandoc(self):
        EXPORT.export_html(self.src, self.out, {"pandoc": True})
        cmd = self.seen[0]
        self.assertIn("--metadata", cmd)
        self.assertIn("title=A Real Title", cmd)

    def test_the_citeproc_html_path_passes_the_title_too(self):
        # The bibliography/CSL branch builds its own command and was the easier
        # of the two to leave behind.
        EXPORT._export_with_extra_args(
            self.src, self.out, "html", {"pandoc": True, "pdf_engine": None},
            ["--citeproc"])
        cmd = self.seen[0]
        self.assertIn("--metadata", cmd)
        self.assertIn("title=A Real Title", cmd)

    def test_a_titleless_document_adds_no_metadata_flag(self):
        self.src.write_text("Body text with no heading.\n", encoding="utf-8")
        EXPORT.export_html(self.src, self.out, {"pandoc": True})
        self.assertNotIn("--metadata", self.seen[0])


class DocxTypographyTests(unittest.TestCase):
    """The body font, size and margins a reader actually sees.

    Three delivered .docx files went out set in the reading application's
    default theme font, at its default size, with no page margins at all,
    because pandoc was invoked with no reference document. These tests
    exercise the two XML patchers directly, so they run without pandoc.
    """

    STYLES = (
        '<?xml version="1.0"?><w:styles xmlns:w="w">'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        '<w:rFonts w:asciiTheme="minorHAnsi" w:hAnsiTheme="minorHAnsi"/>'
        '<w:sz w:val="22"/>'
        "</w:rPr></w:rPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:styleId="Normal">'
        '<w:name w:val="Normal"/></w:style>'
        "</w:styles>"
    )
    DOCUMENT = (
        '<?xml version="1.0"?><w:document xmlns:w="w"><w:body>'
        '<w:p/><w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
        "</w:body></w:document>"
    )

    def test_the_document_defaults_get_the_font_and_size(self):
        out = EXPORT.patch_styles_xml(self.STYLES, "Times New Roman", 12.0)
        self.assertIn('w:ascii="Times New Roman"', out)
        self.assertIn('w:hAnsi="Times New Roman"', out)
        self.assertIn('<w:sz w:val="24"/>', out)

    def test_the_theme_font_reference_is_replaced_not_left_beside(self):
        # A w:rFonts that still names a theme wins over the explicit family in
        # some readers, which is how "we set the font" and "it renders in
        # Calibri" were both true.
        out = EXPORT.patch_styles_xml(self.STYLES, "Times New Roman", 12.0)
        self.assertNotIn("minorHAnsi", out)

    def test_a_normal_style_with_no_run_properties_gains_them(self):
        out = EXPORT.patch_styles_xml(self.STYLES, "Garamond", 11.0)
        normal = out[out.index('w:styleId="Normal"'):]
        self.assertIn("<w:rPr>", normal)
        self.assertIn('w:ascii="Garamond"', normal)
        self.assertIn('<w:sz w:val="22"/>', normal)

    def test_an_existing_normal_run_block_is_patched_in_place(self):
        styles = self.STYLES.replace(
            '<w:name w:val="Normal"/></w:style>',
            '<w:name w:val="Normal"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style>')
        out = EXPORT.patch_styles_xml(styles, "Times New Roman", 12.0)
        normal = out[out.index('w:styleId="Normal"'):]
        self.assertIn('<w:sz w:val="24"/>', normal)
        self.assertNotIn('<w:sz w:val="20"/>', normal)

    def test_a_half_point_size_rounds_to_a_whole_half_point_value(self):
        out = EXPORT.patch_styles_xml(self.STYLES, "Times New Roman", 11.5)
        self.assertIn('<w:sz w:val="23"/>', out)

    def test_styles_with_nothing_to_patch_are_an_error(self):
        with self.assertRaises(EXPORT.ExportError):
            EXPORT.patch_styles_xml("<w:styles/>", "Times New Roman", 12.0)

    def test_margins_are_inserted_in_twips(self):
        out = EXPORT.patch_document_xml(self.DOCUMENT, 1.0)
        self.assertIn('<w:pgMar w:top="1440"', out)
        self.assertIn('w:right="1440"', out)
        self.assertIn('w:bottom="1440"', out)
        self.assertIn('w:left="1440"', out)

    def test_a_fractional_margin_converts_correctly(self):
        out = EXPORT.patch_document_xml(self.DOCUMENT, 1.25)
        self.assertIn('w:top="1800"', out)

    def test_an_existing_pgmar_is_replaced_not_duplicated(self):
        doc = self.DOCUMENT.replace(
            "</w:sectPr>", '<w:pgMar w:top="720" w:right="720"/></w:sectPr>')
        out = EXPORT.patch_document_xml(doc, 1.0)
        self.assertEqual(out.count("<w:pgMar"), 1)
        self.assertIn('w:top="1440"', out)

    def test_a_document_with_no_section_properties_is_an_error(self):
        with self.assertRaises(EXPORT.ExportError):
            EXPORT.patch_document_xml("<w:document/>", 1.0)

    def test_the_defaults_are_the_academic_ones(self):
        self.assertEqual(EXPORT.DEFAULT_DOCX_FONT, "Times New Roman")
        self.assertEqual(EXPORT.DEFAULT_DOCX_FONT_SIZE, 12.0)
        self.assertEqual(EXPORT.DEFAULT_DOCX_MARGIN_INCHES, 1.0)

    def test_a_self_closing_section_block_gains_margins(self):
        # pandoc 3.1.3 writes <w:sectPr /> in its reference document. A regex
        # that only knew the paired form raised here and the whole typography
        # patch was discarded on that host.
        out = EXPORT.patch_document_xml(
            "<w:document><w:body><w:p/><w:sectPr /></w:body></w:document>", 1.0)
        self.assertIn('<w:sectPr><w:pgMar w:top="1440"', out)
        self.assertNotIn("<w:sectPr />", out)


@unittest.skipUnless(shutil.which("pandoc"), "pandoc is not installed")
class RealPandocTypographyTest(unittest.TestCase):
    """End to end against whatever pandoc this host has, not a fixture.

    The hand-written fixtures above encode one pandoc version's XML shape.
    This is the test that would have caught the fix working on one host only.
    """

    def test_an_exported_docx_carries_the_font_size_and_margins(self):
        with TemporaryDirectory() as d:
            src = Path(d) / "paper.md"
            src.write_text("# Title\n\nBody text.\n", encoding="utf-8")
            out = Path(d) / "paper.docx"
            typography = (EXPORT.DEFAULT_DOCX_FONT, EXPORT.DEFAULT_DOCX_FONT_SIZE,
                          EXPORT.DEFAULT_DOCX_MARGIN_INCHES)
            EXPORT.export_docx(src, out, {"pandoc": shutil.which("pandoc")},
                               typography)
            with zipfile.ZipFile(out) as z:
                styles = z.read("word/styles.xml").decode("utf-8")
                document = z.read("word/document.xml").decode("utf-8")
        # pandoc re-serialises the reference parts, so match the elements
        # without assuming its whitespace inside empty tags.
        self.assertRegex(styles, r'<w:rFonts w:ascii="Times New Roman"')
        self.assertRegex(styles, r'<w:sz w:val="24"\s*/>')
        margins = re.search(r"<w:pgMar\b[^>]*/>", document)
        self.assertIsNotNone(margins, "no w:pgMar in the exported document")
        for side in ("top", "right", "bottom", "left"):
            self.assertIn(f'w:{side}="1440"', margins.group(0))


if __name__ == "__main__":
    unittest.main()
