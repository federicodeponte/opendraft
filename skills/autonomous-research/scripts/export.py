#!/usr/bin/env python3
"""Export a compiled markdown draft to docx, pdf, latex or html.

Standard library only (shells out to pandoc/weasyprint if installed; installs
nothing itself). Detects available conversion engines at runtime and fails
with the exact install command for this OS when none is available, rather
than a Python traceback.

    export.py <draft.md> --format docx -o out.docx
    export.py <draft.md> --format pdf  -o out.pdf  [--bibliography refs.bib --csl apa.csl]
    export.py <draft.md> --format latex -o out.tex
    export.py <draft.md> --format html -o out.html
    export.py <draft.md> --format pdf  -o out.pdf --template journal [--brand NAME]
    export.py <draft.md> --format html -o out.html --template journal
    export.py --check              # report what this machine can produce

Journal template: `--template journal` typesets the paper as a two-column
journal article (scripts/journal.py): masthead, serif title, two-column
abstract, numbered sections, and the evidence figures, tables and equations
that `scripts/evidence.py figures` drew, placed at the draft's
{figure:...}, {table:...} and {equations:...} placeholder lines. It needs
pandoc, and weasyprint for the PDF. The default template cannot place those
figures, so it removes the placeholder lines and names each one on stderr.

PDF strategy: pandoc with a LaTeX engine (xelatex/pdflatex) if one is
installed, otherwise pandoc with --pdf-engine=weasyprint (needs the
`weasyprint` Python package on PATH), otherwise fail with install commands
for both pandoc and a PDF engine.

DOCX typography: pandoc's own default reference document sets no body font,
no body size and no page margins, so the finished paper opens in whatever the
reader's Word calls Normal, which is Calibri 11 on a current install. A
manuscript going to a supervisor, a committee or a journal is read as a
formal document, and a formal document's body type is a decision somebody
made rather than the default of the program that produced it. So the docx
path patches a copy of that reference document to name a body font, a body
size and page margins, and hands it to pandoc as --reference-doc. The
defaults below are the ordinary academic manuscript setting; --font,
--font-size and --margin-inches change them when a venue's house style asks
for something else, and --plain-docx skips the whole step.

The patch is applied to the Normal style and to the document defaults, which
is what makes it one setting the whole document inherits rather than a value
stamped onto every paragraph: a reader who changes Normal in Word then
changes the whole paper, which is the behaviour anyone editing the file
afterwards expects.
"""
import argparse
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal  # noqa: E402

FORMATS = ("docx", "pdf", "latex", "html")
TEMPLATES = ("default", "journal")

# The ordinary academic manuscript setting, and the one the venue can override.
DEFAULT_DOCX_FONT = "Times New Roman"
DEFAULT_DOCX_FONT_SIZE = 12.0
DEFAULT_DOCX_MARGIN_INCHES = 1.0

PANDOC_INSTALL = {
    "Darwin": "brew install pandoc",
    "Linux": "sudo apt-get update && sudo apt-get install -y pandoc",
}
LATEX_INSTALL = {
    "Darwin": "brew install --cask mactex-no-gui   (or: brew install --cask basictex)",
    "Linux": "sudo apt-get install -y texlive-xetex",
}
WEASYPRINT_INSTALL = {
    "Darwin": "pip install weasyprint   (also needs: brew install pango)",
    "Linux": "pip install weasyprint   (also needs: sudo apt-get install -y libpango-1.0-0 libpangocairo-1.0-0)",
}


def _os_name():
    return platform.system()  # "Darwin", "Linux", "Windows"


def _install_hint(table):
    os_name = _os_name()
    if os_name in table:
        return table[os_name]
    return " / ".join(f"{k}: {v}" for k, v in table.items())


def detect_engines():
    """Return a dict describing what this machine can produce."""
    pandoc = shutil.which("pandoc")
    xelatex = shutil.which("xelatex")
    pdflatex = shutil.which("pdflatex")
    weasyprint = shutil.which("weasyprint")

    pdf_engine = None
    if pandoc and xelatex:
        pdf_engine = "xelatex"
    elif pandoc and pdflatex:
        pdf_engine = "pdflatex"
    elif pandoc and weasyprint:
        pdf_engine = "weasyprint"

    return {
        "pandoc": bool(pandoc),
        "pandoc_path": pandoc,
        "xelatex": bool(xelatex),
        "pdflatex": bool(pdflatex),
        "weasyprint": bool(weasyprint),
        "can_docx": bool(pandoc),
        "can_latex": bool(pandoc),
        "can_html": bool(pandoc),
        "can_pdf": bool(pdf_engine),
        "pdf_engine": pdf_engine,
    }


def _run(cmd, timeout=120):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        return 127, "", str(e)
    except subprocess.TimeoutExpired as e:
        return 124, "", f"Timed out after {timeout}s: {e}"
    return result.returncode, result.stdout, result.stderr


class ExportError(Exception):
    pass


# --- docx typography --------------------------------------------------------

def _twips(inches):
    """Inches to twentieths of a point, the unit w:pgMar is written in."""
    return int(round(inches * 1440))


def _half_points(points):
    """Points to half-points, the unit w:sz is written in."""
    return int(round(points * 2))


def _xml_escape(value):
    return (value.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


_RPR_DEFAULT = re.compile(r"(<w:rPrDefault>\s*<w:rPr>)(.*?)(</w:rPr>)", re.S)
_NORMAL_STYLE = re.compile(
    r'(<w:style\b[^>]*w:styleId="Normal"[^>]*>)(.*?)(</w:style>)', re.S)
_RFONTS = re.compile(r"<w:rFonts\b[^>]*/>")
_SZ = re.compile(r"<w:sz\b[^>]*/>")
_SZCS = re.compile(r"<w:szCs\b[^>]*/>")
_SECTPR = re.compile(r"(<w:sectPr\b[^>]*>)(.*?)(</w:sectPr>)", re.S)
# pandoc 3.1.x ships its reference document with an empty, self-closing
# section block. Newer pandoc writes the paired form. Both must be patchable,
# or margins silently never land on the older host.
_SECTPR_EMPTY = re.compile(r"<w:sectPr\b([^>]*?)\s*/>")
_PGMAR = re.compile(r"<w:pgMar\b[^>]*/>")


def _run_properties(font, size_pt):
    """The <w:rFonts>/<w:sz>/<w:szCs> triple naming a body font and size."""
    name = _xml_escape(font)
    half = _half_points(size_pt)
    return (f'<w:rFonts w:ascii="{name}" w:hAnsi="{name}" w:cs="{name}" '
            f'w:eastAsia="{name}"/>'
            f'<w:sz w:val="{half}"/><w:szCs w:val="{half}"/>')


def _apply_run_properties(inner, font, size_pt):
    """`inner`, an <w:rPr> body, with the font and size elements set.

    Each of the three elements is replaced where it already exists and
    prepended where it does not, because pandoc's shipped reference document
    carries an rFonts pointing at the theme (which is where the Calibri comes
    from) and no rFonts at all on the Normal style itself.
    """
    name = _xml_escape(font)
    half = _half_points(size_pt)
    replacements = [
        (_RFONTS, f'<w:rFonts w:ascii="{name}" w:hAnsi="{name}" w:cs="{name}" '
                  f'w:eastAsia="{name}"/>'),
        (_SZ, f'<w:sz w:val="{half}"/>'),
        (_SZCS, f'<w:szCs w:val="{half}"/>'),
    ]
    missing = ""
    for pattern, element in replacements:
        if pattern.search(inner):
            inner = pattern.sub(element, inner, count=1)
        else:
            missing += element
    return missing + inner


def patch_styles_xml(xml, font, size_pt):
    """word/styles.xml with the body font and size set on Normal and on the defaults.

    Both places, because they answer two different questions. The document
    defaults are what every style without its own font inherits, so patching
    them is what actually changes the rendered body. The Normal style is what
    a reader sees when they open the style pane and what they edit to restyle
    the paper, so a Normal that still says "theme font" while the page renders
    in Times is a document that lies about itself.
    """
    def default_sub(m):
        return m.group(1) + _apply_run_properties(m.group(2), font, size_pt) + m.group(3)

    def normal_sub(m):
        head, inner, tail = m.groups()
        rpr = re.search(r"(<w:rPr>)(.*?)(</w:rPr>)", inner, re.S)
        if rpr:
            inner = (inner[:rpr.start()] + rpr.group(1)
                     + _apply_run_properties(rpr.group(2), font, size_pt)
                     + rpr.group(3) + inner[rpr.end():])
        else:
            inner = inner + f"<w:rPr>{_run_properties(font, size_pt)}</w:rPr>"
        return head + inner + tail

    patched, defaults_done = _RPR_DEFAULT.subn(default_sub, xml, count=1)
    patched, normal_done = _NORMAL_STYLE.subn(normal_sub, patched, count=1)
    if not (defaults_done or normal_done):
        raise ExportError(
            "pandoc's reference document has neither a document-defaults run "
            "block nor a Normal style to set the body font on")
    return patched


def patch_document_xml(xml, margin_inches):
    """word/document.xml with page margins set on the section properties.

    pandoc's reference document ships a sectPr with no w:pgMar, which leaves
    the margins to whatever the reading application defaults to.
    """
    twips = _twips(margin_inches)
    element = (f'<w:pgMar w:top="{twips}" w:right="{twips}" w:bottom="{twips}" '
               f'w:left="{twips}" w:header="720" w:footer="720" w:gutter="0"/>')

    def sub(m):
        head, inner, tail = m.groups()
        if _PGMAR.search(inner):
            inner = _PGMAR.sub(element, inner, count=1)
        else:
            # w:pgMar follows w:footnotePr, w:endnotePr, w:type and w:pgSz in
            # the schema's element order, and precedes nothing this document
            # carries, so the end of the block is the correct position.
            inner = inner + element
        return head + inner + tail

    patched, done = _SECTPR.subn(sub, xml, count=1)
    if not done:
        patched, done = _SECTPR_EMPTY.subn(
            lambda m: f"<w:sectPr{m.group(1)}>{element}</w:sectPr>", xml, count=1)
    if not done:
        raise ExportError("pandoc's reference document has no section "
                          "properties to set page margins on")
    return patched


def build_reference_docx(dest, font, size_pt, margin_inches):
    """pandoc's own reference.docx, copied out and given a body font and margins."""
    result = subprocess.run(
        ["pandoc", "--print-default-data-file", "reference.docx"],
        capture_output=True, timeout=60)
    if result.returncode != 0 or not result.stdout:
        raise ExportError(
            "pandoc could not produce its default reference document "
            f"(exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', 'replace').strip()}")

    source = Path(dest).with_suffix(".source.docx")
    source.write_bytes(result.stdout)
    patchers = {
        "word/styles.xml": lambda xml: patch_styles_xml(xml, font, size_pt),
        "word/document.xml": lambda xml: patch_document_xml(xml, margin_inches),
    }
    failures = []
    with zipfile.ZipFile(source) as src, \
            zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            data = src.read(item.filename)
            patch = patchers.get(item.filename)
            if patch is not None:
                # Each part is patched independently. A margin patch that
                # fails must not throw away a font patch that succeeded,
                # which is how a host with an older pandoc shipped Calibri.
                try:
                    data = patch(data.decode("utf-8")).encode("utf-8")
                except ExportError as e:
                    failures.append(f"{item.filename}: {e}")
            out.writestr(item, data)
    source.unlink()
    if len(failures) == len(patchers):
        raise ExportError("; ".join(failures))
    for failure in failures:
        print(f"Warning: docx typography partly applied, {failure}",
              file=sys.stderr)
    return dest


def _reference_doc_args(stack, typography):
    """['--reference-doc=...'] for a docx export, or [] when it is turned off.

    A failure to build the reference document is reported and then stepped
    over: a paper that exports in the reader's default font is worse than one
    that exports in Times, and better than one that does not export at all.
    """
    if typography is None:
        return []
    font, size_pt, margin_inches = typography
    path = Path(stack) / "reference.docx"
    try:
        build_reference_docx(path, font, size_pt, margin_inches)
    except (ExportError, OSError, zipfile.BadZipFile, subprocess.SubprocessError) as e:
        print(f"Warning: falling back to pandoc's default docx typography "
              f"({font} {size_pt:g}pt was not applied): {e}", file=sys.stderr)
        return []
    return [f"--reference-doc={path}"]


def export_docx(src, out, engines, typography=None):
    if not engines["pandoc"]:
        raise ExportError(_missing_pandoc_message())
    with tempfile.TemporaryDirectory() as stack:
        cmd = (["pandoc", str(src)] + _reference_doc_args(stack, typography)
               + ["-o", str(out)])
        code, _, err = _run(cmd)
    if code != 0:
        raise ExportError(f"pandoc failed (exit {code}):\n{err.strip()}")


def export_latex(src, out, engines):
    if not engines["pandoc"]:
        raise ExportError(_missing_pandoc_message())
    code, _, err = _run(["pandoc", str(src), "-o", str(out)])
    if code != 0:
        raise ExportError(f"pandoc failed (exit {code}):\n{err.strip()}")


def _document_title(src):
    """The paper's own title: its first level-1 heading, outside code fences.

    `pandoc -s` with no title metadata falls back to the source filename, so a
    finished paper exported to HTML arrived titled "final" in the browser tab
    and in every search result and link preview that reads that element. The
    title is the one piece of metadata the document already carries, and
    nothing else in the pipeline records it.
    """
    try:
        with open(src, encoding="utf-8") as handle:
            in_fence = False
            for line in handle:
                if line.lstrip().startswith(("```", "~~~")):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip() or None
    except OSError:
        return None
    return None


def _title_metadata(src):
    title = _document_title(src)
    return ["--metadata", f"title={title}"] if title else []


def export_html(src, out, engines):
    if not engines["pandoc"]:
        raise ExportError(_missing_pandoc_message())
    cmd = ["pandoc", str(src), "-s"] + _title_metadata(src) + ["-o", str(out)]
    code, _, err = _run(cmd)
    if code != 0:
        raise ExportError(f"pandoc failed (exit {code}):\n{err.strip()}")


def export_pdf(src, out, engines):
    if not engines["pandoc"]:
        raise ExportError(_missing_pandoc_message())
    if not engines["pdf_engine"]:
        raise ExportError(
            "No PDF engine available. pandoc is installed but needs either a "
            "LaTeX engine or weasyprint to produce a PDF.\n"
            f"Install a LaTeX engine:\n  {_install_hint(LATEX_INSTALL)}\n"
            f"or install weasyprint:\n  {_install_hint(WEASYPRINT_INSTALL)}"
        )
    cmd = ["pandoc", str(src), f"--pdf-engine={engines['pdf_engine']}", "-o", str(out)]
    code, _, err = _run(cmd, timeout=180)
    if code != 0:
        raise ExportError(f"pandoc --pdf-engine={engines['pdf_engine']} failed (exit {code}):\n{err.strip()}")


def _missing_pandoc_message():
    return (
        "pandoc is not installed. It is required for every export format.\n"
        f"Install it with:\n  {_install_hint(PANDOC_INSTALL)}"
    )


EXPORTERS = {
    "docx": export_docx,
    "latex": export_latex,
    "html": export_html,
    "pdf": export_pdf,
}


def export_journal(src, out, fmt, engines, options=None):
    """The journal template: HTML from scripts/journal.py, PDF via weasyprint."""
    options = dict(options or {})
    if fmt not in ("pdf", "html"):
        raise ExportError("--template journal produces pdf or html only")
    if not engines["pandoc"]:
        raise ExportError(_missing_pandoc_message())
    base = Path(src).resolve().parent
    options.setdefault("figures_dir", base / "research" / "figures")
    options.setdefault("research_dir", base / "research")
    try:
        page, warnings = journal.build_html(src, **options)
    except journal.JournalError as e:
        raise ExportError(str(e))
    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)
    if fmt == "html":
        Path(out).write_text(page, encoding="utf-8")
        return
    if not engines["weasyprint"]:
        raise ExportError("The journal PDF needs weasyprint.\n"
                          f"Install it with:\n  {_install_hint(WEASYPRINT_INSTALL)}")
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / "journal.html"
        page_path.write_text(page, encoding="utf-8")
        code, _, err = _run(["weasyprint", str(page_path), str(out)], timeout=300)
    if code != 0:
        raise ExportError(f"weasyprint failed (exit {code}):\n{err.strip()}")


def export(src_path, out_path, fmt, bibliography=None, csl=None, typography=None,
           template="default", journal_options=None):
    engines = detect_engines()
    if fmt not in EXPORTERS:
        raise ExportError(f"Unsupported format '{fmt}'. Choose from: {', '.join(FORMATS)}")
    if template == "journal":
        if bibliography or csl:
            raise ExportError("--template journal typesets the compiled references; "
                              "drop --bibliography/--csl")
        export_journal(src_path, out_path, fmt, engines, journal_options)
        return
    text = Path(src_path).read_text(encoding="utf-8")
    stripped, removed = journal.strip_placeholders(text)
    if removed:
        for line in removed:
            print(f"Warning: {line} dropped; only --template journal can place it",
                  file=sys.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / Path(src_path).name
            clean.write_text(stripped, encoding="utf-8")
            export(clean, out_path, fmt, bibliography, csl, typography)
        return

    extra = []
    if bibliography:
        if not Path(bibliography).exists():
            raise ExportError(f"Bibliography file not found: {bibliography}")
        extra += [f"--bibliography={bibliography}", "--citeproc"]
    if csl:
        if not Path(csl).exists():
            raise ExportError(f"CSL style file not found: {csl}")
        extra += [f"--csl={csl}"]

    if extra:
        _export_with_extra_args(src_path, out_path, fmt, engines, extra, typography)
    elif fmt == "docx":
        export_docx(src_path, out_path, engines, typography)
    else:
        EXPORTERS[fmt](src_path, out_path, engines)


def _export_with_extra_args(src, out, fmt, engines, extra, typography=None):
    if not engines["pandoc"]:
        raise ExportError(_missing_pandoc_message())
    cmd = ["pandoc", str(src)] + extra
    if fmt == "docx":
        with tempfile.TemporaryDirectory() as stack:
            cmd += _reference_doc_args(stack, typography)
            code, _, err = _run(cmd + ["-o", str(out)], timeout=180)
        if code != 0:
            raise ExportError(f"pandoc failed (exit {code}):\n{err.strip()}")
        return
    if fmt == "pdf":
        if not engines["pdf_engine"]:
            raise ExportError(
                "No PDF engine available. pandoc is installed but needs either a "
                "LaTeX engine or weasyprint to produce a PDF.\n"
                f"Install a LaTeX engine:\n  {_install_hint(LATEX_INSTALL)}\n"
                f"or install weasyprint:\n  {_install_hint(WEASYPRINT_INSTALL)}"
            )
        cmd.append(f"--pdf-engine={engines['pdf_engine']}")
    elif fmt == "html":
        cmd.append("-s")
        cmd += _title_metadata(src)
    cmd += ["-o", str(out)]
    code, _, err = _run(cmd, timeout=180)
    if code != 0:
        raise ExportError(f"pandoc failed (exit {code}):\n{err.strip()}")


def _print_check(engines):
    print(f"OS: {_os_name()}")
    print(f"pandoc:     {'yes (' + engines['pandoc_path'] + ')' if engines['pandoc'] else 'NOT FOUND'}")
    print(f"xelatex:    {'yes' if engines['xelatex'] else 'no'}")
    print(f"pdflatex:   {'yes' if engines['pdflatex'] else 'no'}")
    print(f"weasyprint: {'yes' if engines['weasyprint'] else 'no'}")
    print()
    print(f"docx:  {'OK' if engines['can_docx'] else 'unavailable, ' + PANDOC_INSTALL.get(_os_name(), _install_hint(PANDOC_INSTALL))}")
    print(f"latex: {'OK' if engines['can_latex'] else 'unavailable, ' + PANDOC_INSTALL.get(_os_name(), _install_hint(PANDOC_INSTALL))}")
    print(f"html:  {'OK' if engines['can_html'] else 'unavailable, ' + PANDOC_INSTALL.get(_os_name(), _install_hint(PANDOC_INSTALL))}")
    if engines["can_pdf"]:
        print(f"pdf:   OK (via pandoc --pdf-engine={engines['pdf_engine']})")
    else:
        print("pdf:   unavailable")
        if not engines["pandoc"]:
            print(f"       install pandoc: {_install_hint(PANDOC_INSTALL)}")
        else:
            print(f"       install a LaTeX engine: {_install_hint(LATEX_INSTALL)}")
            print(f"       or install weasyprint: {_install_hint(WEASYPRINT_INSTALL)}")


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="export.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("draft", nargs="?", help="Path to the compiled draft markdown file")
    parser.add_argument("--format", choices=FORMATS, help="Output format")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--bibliography", help="BibTeX file for pandoc --citeproc rendering")
    parser.add_argument("--csl", help="CSL style file for pandoc citation rendering")
    parser.add_argument("--font", default=DEFAULT_DOCX_FONT,
                         help="docx body font, set on the Normal style rather than stamped on "
                              f"every paragraph (default: {DEFAULT_DOCX_FONT})")
    parser.add_argument("--font-size", type=float, default=DEFAULT_DOCX_FONT_SIZE,
                         metavar="PT",
                         help=f"docx body size in points (default: {DEFAULT_DOCX_FONT_SIZE:g})")
    parser.add_argument("--margin-inches", type=float, default=DEFAULT_DOCX_MARGIN_INCHES,
                         metavar="N",
                         help="docx page margin on all four sides, in inches "
                              f"(default: {DEFAULT_DOCX_MARGIN_INCHES:g})")
    parser.add_argument("--plain-docx", action="store_true",
                         help="Skip the typography step and let pandoc's own reference document "
                              "decide the docx body font, size and margins. That default sets no "
                              "body font at all, so the paper renders in whatever the reader's "
                              "Word calls Normal.")
    parser.add_argument("--template", choices=TEMPLATES, default="default",
                         help="journal: two-column journal article with the evidence figures "
                              "(pdf or html only)")
    parser.add_argument("--figures", metavar="DIR",
                         help="journal: directory evidence.py figures wrote "
                              "(default: research/figures next to the draft)")
    parser.add_argument("--research", metavar="DIR",
                         help="journal: research/ directory for the at-a-glance numbers "
                              "(default: research next to the draft)")
    parser.add_argument("--brand", default="OpenDraft",
                         help="journal: masthead name (default: OpenDraft)")
    parser.add_argument("--kind", help='journal: article type line, e.g. "Narrative review"')
    parser.add_argument("--byline", help="journal: byline under the title")
    parser.add_argument("--masthead-note", help="journal: right-hand masthead text")
    parser.add_argument("--lang", default="en", help="journal: document language, for hyphenation")
    parser.add_argument("--no-glance", action="store_true",
                         help="journal: leave out the at-a-glance number strip")
    parser.add_argument("--check", action="store_true",
                         help="Report what this machine can produce and exit (no conversion)")
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.check:
        _print_check(detect_engines())
        return 0

    if not args.draft or not args.format or not args.output:
        parser.print_help()
        return 2

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Error: draft not found: {args.draft}", file=sys.stderr)
        return 1

    typography = (None if args.plain_docx
                  else (args.font, args.font_size, args.margin_inches))
    try:
        options = {"brand": args.brand, "kind": args.kind, "byline": args.byline,
                   "masthead_note": args.masthead_note, "lang": args.lang,
                   "glance": not args.no_glance}
        if args.figures:
            options["figures_dir"] = Path(args.figures)
        if args.research:
            options["research_dir"] = Path(args.research)
        export(draft_path, Path(args.output), args.format,
               bibliography=args.bibliography, csl=args.csl,
               typography=typography, template=args.template,
               journal_options=options)
    except ExportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Exported {args.draft} -> {args.output} ({args.format})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
