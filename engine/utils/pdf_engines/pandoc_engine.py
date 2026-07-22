#!/usr/bin/env python3
"""
ABOUTME: Pandoc/LaTeX-based PDF generation engine for academic papers
ABOUTME: Professional typesetting using LaTeX with proper font rendering
"""

import re
import subprocess
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from .base import PDFEngine, PDFGenerationOptions, EngineResult


# LaTeX special characters that must be escaped in plain-text values injected
# directly into the preamble (title, author, institution, ...). Without this a
# title like "Cost & Benefit_Analysis of 50%" makes the custom \maketitle
# definition unparseable and XeLaTeX aborts with "File ended while scanning use
# of \@argdef", even though Pandoc reported success. Applied to BOTH the PDF and
# the .tex paths (they share _create_latex_preamble).
def _latex_escape_text(value: Any) -> str:
    """Escape LaTeX special characters in a plain-text metadata value."""
    if value is None:
        return ""
    s = str(value)
    # Backslash first, then the rest, so we don't double-escape our own escapes.
    s = s.replace("\\", r"\textbackslash{}")
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, escaped in replacements.items():
        s = s.replace(char, escaped)
    return s


class PandocLatexEngine(PDFEngine):
    """
    Pandoc/LaTeX-based PDF generation engine.

    Uses Pandoc to convert markdown to LaTeX, then XeLaTeX to generate PDF.
    This is the modern academic standard for document typesetting with superior
    typography and full Unicode support (including CJK characters).

    Advantages:
    - Best font rendering quality (solves AI vs Al visual issues)
    - Professional academic typesetting
    - Industry standard for research papers
    - Proper handling of italics, bold, and formatting
    - Full Unicode support for international characters (Chinese, Japanese, Korean, etc.)
    - Clean separation of content and presentation

    Requirements:
    - pandoc
    - xelatex (texlive-xetex)
    - texlive-latex-recommended (for additional packages)
    - fonts-noto-cjk (for CJK character support)
    """

    def get_name(self) -> str:
        """Get engine name."""
        return "Pandoc/LaTeX"

    def get_priority(self) -> int:
        """
        Priority: 85/100

        Highest priority due to superior typography and academic standards.
        Should be preferred over all other engines when available.
        """
        return 85

    def is_available(self) -> bool:
        """Check if pandoc and xelatex are available."""
        return (
            shutil.which('pandoc') is not None and
            self._find_xelatex() is not None
        )

    def _find_xelatex(self) -> Optional[str]:
        """Find xelatex binary, checking common LaTeX installation paths."""
        # First check PATH
        xelatex = shutil.which('xelatex')
        if xelatex:
            return xelatex

        # Common LaTeX installation paths on macOS
        common_paths = [
            # TinyTeX (R/RStudio default)
            Path.home() / "Library/TinyTeX/bin/universal-darwin/xelatex",
            # MacTeX
            Path("/Library/TeX/texbin/xelatex"),
            Path("/usr/local/texlive/2025/bin/universal-darwin/xelatex"),
            Path("/usr/local/texlive/2024/bin/universal-darwin/xelatex"),
            Path("/usr/local/texlive/2023/bin/universal-darwin/xelatex"),
            # BasicTeX
            Path("/usr/local/texlive/2025basic/bin/universal-darwin/xelatex"),
        ]

        for path in common_paths:
            if path.exists():
                return str(path)

        return None

    def generate(
        self,
        md_file: Path,
        output_pdf: Path,
        options: PDFGenerationOptions
    ) -> EngineResult:
        """
        Generate PDF via Markdown → LaTeX → PDF pipeline.

        Args:
            md_file: Input markdown file
            output_pdf: Output PDF path
            options: Generation options

        Returns:
            EngineResult with success/failure details
        """
        # Validate inputs
        error = self.validate_inputs(md_file, output_pdf)
        if error:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=error
            )

        try:
            # Normalize YAML field names for Pandoc compatibility
            # (Pandoc only recognizes English field names like 'title', 'author', 'date')
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # CRITICAL: Save original content BEFORE normalization for formatter check
            # Normalization strips showcase YAML fields, causing wrong cover page detection
            original_md_content = md_content

            md_content = self._normalize_yaml_for_pandoc(md_content)

            # CRITICAL: Remove outer ```markdown wrapper if present (BUG #20)
            # Recent draft generations incorrectly wrap entire file in code fence
            md_content = self._unwrap_markdown_fence(md_content)

            # CRITICAL: Remove duplicate title heading for showcase theses
            # Custom cover page already renders title, so remove # Title heading from body
            # to prevent it from appearing in Table of Contents
            # Use ORIGINAL content for showcase detection (before normalization strips showcase fields)
            md_content = self._remove_title_heading(md_content, original_md_content)

            # CRITICAL: Remove code blocks (ASCII diagrams) before PDF generation
            # Code blocks cause massive verbatim sections in LaTeX that truncate documents
            # (e.g., 122 pages → 39 pages due to unbreakable monospace text)
            md_content = self._strip_code_blocks(md_content)
            
            # BUG #6 FIX: Normalize bullet list formatting for consistent PDF rendering
            # Converts `*   ` and `* ` variations to standard `- ` format
            md_content = self._normalize_bullet_lists(md_content)

            # BUG #21 FIX: Escape LaTeX special characters in URLs and plain text
            md_content = self._escape_latex_special_chars(md_content)

            # Note: XeLaTeX handles Unicode natively, no sanitization needed
            # (Previous pdflatex required _sanitize_unicode_for_latex)

            # Write normalized content to temporary file for Pandoc
            import tempfile
            temp_md = None
            temp_fd = None
            try:
                temp_fd, temp_path = tempfile.mkstemp(suffix='.md', text=True)
                temp_md = Path(temp_path)
                with open(temp_md, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            finally:
                if temp_fd is not None:
                    import os
                    os.close(temp_fd)

            # Create LaTeX preamble for header customization
            # CRITICAL: Use ORIGINAL content (before normalization) for YAML extraction
            # This preserves showcase fields for is_showcase_draft() check
            latex_preamble = self._create_latex_preamble(options, original_md_content)
            preamble_path = output_pdf.parent / f"{output_pdf.stem}_preamble.tex"
            preamble_path = preamble_path.resolve()  # Get absolute path

            # Write preamble
            with open(preamble_path, 'w', encoding='utf-8') as f:
                f.write(latex_preamble)

            # Convert markdown to PDF using Pandoc + LaTeX (use normalized temp file)
            result = self._run_pandoc(temp_md, output_pdf, preamble_path, options)

            # Cleanup preamble file
            if preamble_path.exists():
                preamble_path.unlink()

            # Cleanup temporary markdown file
            if temp_md and temp_md.exists():
                temp_md.unlink()

            # Cleanup LaTeX auxiliary files
            self._cleanup_latex_files(output_pdf)

            return result

        except Exception as e:
            # Cleanup temp file on error
            if temp_md and temp_md.exists():
                temp_md.unlink()
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Unexpected error: {str(e)}"
            )

    def latex_is_available(self) -> bool:
        """
        Check if standalone LaTeX (.tex) generation is possible.

        Unlike PDF generation, emitting a .tex source only needs Pandoc; a LaTeX
        compiler (XeLaTeX) is NOT required to WRITE the .tex file. The generated
        document still targets XeLaTeX for compilation (fontspec preamble).
        """
        return shutil.which('pandoc') is not None

    def generate_latex(
        self,
        md_file: Path,
        output_tex: Path,
        options: PDFGenerationOptions
    ) -> EngineResult:
        """
        Generate a standalone, compilable LaTeX (.tex) source from Markdown.

        Reuses the EXACT same preprocessing and preamble as the proven PDF path
        (generate()), but emits a standalone LaTeX document instead of running
        XeLaTeX to a PDF. The resulting .tex is a full document
        (\\documentclass ... \\begin{document} ... \\end{document}) that compiles
        with XeLaTeX (the preamble uses fontspec) and carries the same
        style-formatted References section as the PDF, i.e. an embedded,
        properly formatted bibliography.

        Args:
            md_file: Input markdown file
            output_tex: Output .tex path
            options: Generation options (shared with the PDF path)

        Returns:
            EngineResult with success/failure details
        """
        # Validate inputs (mirror of validate_inputs, but for a .tex target)
        if not md_file.exists():
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Input file not found: {md_file}"
            )
        if md_file.suffix.lower() not in ['.md', '.markdown']:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Input file must be markdown (.md), got: {md_file.suffix}"
            )
        if output_tex.suffix.lower() != '.tex':
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Output file must have .tex extension, got: {output_tex.suffix}"
            )
        output_tex.parent.mkdir(parents=True, exist_ok=True)

        temp_md = None
        preamble_path = None
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # Identical preprocessing chain to the PDF path (generate()).
            original_md_content = md_content
            md_content = self._normalize_yaml_for_pandoc(md_content)
            md_content = self._unwrap_markdown_fence(md_content)
            md_content = self._remove_title_heading(md_content, original_md_content)
            md_content = self._strip_code_blocks(md_content)
            md_content = self._normalize_bullet_lists(md_content)
            md_content = self._escape_latex_special_chars(md_content)

            import tempfile
            import os
            temp_fd, temp_path = tempfile.mkstemp(suffix='.md', text=True)
            temp_md = Path(temp_path)
            try:
                with open(temp_md, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            finally:
                os.close(temp_fd)

            # Same preamble the PDF uses (title page, TOC, fonts, hyperref, tables).
            latex_preamble = self._create_latex_preamble(options, original_md_content)
            preamble_path = (output_tex.parent / f"{output_tex.stem}_preamble.tex").resolve()
            with open(preamble_path, 'w', encoding='utf-8') as f:
                f.write(latex_preamble)

            result = self._run_pandoc_latex(temp_md, output_tex, preamble_path, options)
            return result

        except Exception as e:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Unexpected error generating LaTeX: {str(e)}"
            )
        finally:
            if preamble_path and preamble_path.exists():
                try:
                    preamble_path.unlink()
                except Exception:
                    pass
            if temp_md and temp_md.exists():
                try:
                    temp_md.unlink()
                except Exception:
                    pass

    def _run_pandoc_latex(
        self,
        md_file: Path,
        output_tex: Path,
        preamble_path: Path,
        options: PDFGenerationOptions
    ) -> EngineResult:
        """
        Run Pandoc to convert markdown to a standalone .tex source.

        Mirrors _run_pandoc but targets `-t latex --standalone` (no --pdf-engine),
        so the output is editable, compilable LaTeX rather than a PDF.
        """
        try:
            margin = options.margins

            cmd = [
                'pandoc',
                str(md_file.resolve()),
                '-o', str(output_tex.resolve()),
                '--standalone',
                '--to', 'latex',
                '--include-in-header', str(preamble_path.resolve()),
                '--from', 'markdown+autolink_bare_uris+raw_tex',
                '--variable', f'geometry:margin={margin}',
                '--variable', f'fontsize={options.font_size}',
                '--variable', 'papersize:letter',
                '--variable', 'documentclass:article',
            ]

            # Pandoc --variable values are substituted literally (NOT LaTeX-escaped),
            # and they land in \title{...}/\author{...}, so escape special chars here
            # too or a title like "Cost & Benefit" breaks the compile.
            if options.title:
                cmd.extend(['--variable', f'title={_latex_escape_text(options.title)}'])
            if options.author:
                cmd.extend(['--variable', f'author={_latex_escape_text(options.author)}'])
            if options.date:
                cmd.extend(['--variable', f'date={_latex_escape_text(options.date)}'])
            if options.institution:
                cmd.extend(['--variable', f'institution={_latex_escape_text(options.institution)}'])
            if options.department:
                cmd.extend(['--variable', f'department={_latex_escape_text(options.department)}'])
            if options.course:
                cmd.extend(['--variable', f'course={_latex_escape_text(options.course)}'])
            if options.instructor:
                cmd.extend(['--variable', f'instructor={_latex_escape_text(options.instructor)}'])

            if options.enable_toc:
                cmd.append('--toc')
                cmd.extend(['--variable', f'toc-depth={options.toc_depth}'])
                cmd.extend(['--variable', 'toc-title=Table of Contents'])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=output_tex.parent
            )

            if result.returncode != 0:
                error_lines = result.stderr.split('\n')
                latex_errors = [line for line in error_lines if line.startswith('!')]
                if latex_errors:
                    error_msg = '\n'.join(latex_errors[:3])
                else:
                    error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                return EngineResult(
                    success=False,
                    engine_name=self.get_name(),
                    error_message=f"Pandoc LaTeX conversion failed:\n{error_msg}"
                )

            if not output_tex.exists():
                return EngineResult(
                    success=False,
                    engine_name=self.get_name(),
                    error_message="Pandoc did not generate .tex file"
                )

            # Prepend a TeX-editor magic comment so the .tex is compiled with the
            # right engine. The preamble uses fontspec, so it requires XeLaTeX (or
            # LuaLaTeX); pdflatex will fail. This makes the requirement explicit.
            try:
                original = output_tex.read_text(encoding='utf-8')
                header = (
                    "% !TeX program = xelatex\n"
                    "% Generated by OpenDraft. Compile with XeLaTeX or LuaLaTeX "
                    "(the preamble uses fontspec); pdflatex is not supported.\n"
                )
                if not original.lstrip().startswith('% !TeX'):
                    output_tex.write_text(header + original, encoding='utf-8')
            except OSError:
                pass  # Non-fatal: the .tex is already valid without the comment.

            warnings = []
            if 'Warning' in result.stdout or 'Warning' in result.stderr:
                warnings.append("Pandoc generated warnings (non-critical)")

            return EngineResult(
                success=True,
                engine_name=self.get_name(),
                output_path=output_tex,
                warnings=warnings
            )

        except subprocess.TimeoutExpired:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message="Pandoc LaTeX conversion timed out (>2 minutes)"
            )
        except Exception as e:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Pandoc execution failed: {str(e)}"
            )

    def _create_latex_preamble(self, options: PDFGenerationOptions, md_content: str = "") -> str:
        """
        Create LaTeX preamble for header customization.

        This is injected into Pandoc's default template, which is more robust
        than creating a full custom template.

        REVERTED: Restored original Pandoc template-based approach (pre-83330e9).
        Pandoc reads YAML frontmatter and calls \\maketitle automatically.
        This approach works for ALL theses (showcase theses have rich YAML = beautiful cover).

        Args:
            options: PDF generation options
            md_content: Markdown content (for YAML metadata extraction)

        Returns:
            str: LaTeX preamble content
        """
        # Parse line spacing for LaTeX (2.0 = double spacing)
        if options.line_spacing >= 1.9:
            spacing_command = r'\doublespacing'
        elif options.line_spacing >= 1.4:
            spacing_command = r'\onehalfspacing'
        else:
            spacing_command = r'\singlespacing'

        preamble = r'''\PassOptionsToPackage{hyphens}{url}
\usepackage{xurl}
\usepackage{etoolbox}
\usepackage{setspace}
''' + spacing_command + r'''

% Unicode font support for XeLaTeX (handles CJK and all Unicode)
\usepackage{fontspec}
% XeLaTeX natively handles Unicode - no special CJK packages needed
% System fonts like DejaVu Sans support basic CJK glyphs

\usepackage{indentfirst}
\setlength{\parindent}{0.5in}
\setlength{\parskip}{0pt}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\cfoot{\thepage}
\widowpenalty=10000
\clubpenalty=10000

% Configure hyperref for clickable DOI/URL links (Pandoc loads it automatically)
\AtBeginDocument{%
  \hypersetup{%
    colorlinks=true,%
    linkcolor=black,%
    citecolor=black,%
    urlcolor=blue,%
    breaklinks=true%
  }%
  \urlstyle{same}%
  % Enhanced URL breaking for DOIs and long URLs
  % Allow breaks at: / - _ . (common in DOIs and URLs)
  \def\UrlBreaks{\do\/\do\-\do\_\do\.}%
  % Add small spacing around break points for better line breaking
  \Urlmuskip=0mu plus 1mu%
  % Suppress page number on cover page (first page only)
  \thispagestyle{empty}%
}

% Fix Level 3 headings: italic (NOT bold) - APA 7th edition
\usepackage{titlesec}
% Use full \titleformat to override Pandoc's default bold formatting
\titleformat{\subsubsection}
  {\normalfont\normalsize\itshape}  % Format: normal weight (not bold), normal size, italic
  {}                                  % Label
  {0pt}                               % Sep
  {}                                  % Before-code

% Better table formatting - prevent truncation, auto-wrap cells
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{array}
\usepackage{tabularx}
\usepackage{relsize}
% Set table margins to full text width
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
% Reduce font size slightly for wide tables
\let\oldlongtable\longtable
\let\endoldlongtable\endlongtable
\renewenvironment{longtable}{\small\oldlongtable}{\endoldlongtable}
'''

        # Add APA 7th edition title page formatting if metadata provided
        # ORIGINAL APPROACH: Use titling package to customize Pandoc's template
        # Pandoc reads YAML (title, subtitle, author, date, etc.) and calls \maketitle
        # Showcase theses have RICH YAML → beautiful automated cover page
        if any([options.title, options.author, options.institution,
                options.course, options.instructor]):
            preamble += r'''
% Professional Academic Title Page - Balanced Layout
\usepackage{titling}
\renewcommand{\maketitle}{%
  \begin{titlepage}
    \centering
    % Institution Block - top
    \vspace*{0.5in}
'''
            # Add institution if provided
            if options.institution:
                preamble += f'''    {{\\normalsize\\scshape {_latex_escape_text(options.institution)}\\par}}
'''
            # Add faculty if provided
            if hasattr(options, 'faculty') and options.faculty:
                preamble += f'''    \\vspace{{0.08cm}}
    {{\\small {_latex_escape_text(options.faculty)}\\par}}
'''
            if options.department:
                preamble += f'''    \\vspace{{0.08cm}}
    {{\\small\\itshape {_latex_escape_text(options.department)}\\par}}
'''

            preamble += r'''
    \vfill
    % Title Block - center
'''
            if options.title:
                preamble += f'''    {{\\Large\\bfseries {_latex_escape_text(options.title)}\\par}}
'''
            if options.subtitle:
                preamble += f'''    \\vspace{{0.25cm}}
    {{\\normalsize\\itshape {_latex_escape_text(options.subtitle)}\\par}}
'''

            # Add project type descriptor
            if options.project_type:
                preamble += f'''    \\vspace{{0.5cm}}
    {{\\small\\scshape {_latex_escape_text(options.project_type)}\\par}}
'''

            # Add degree
            if options.course:  # course field holds degree info
                preamble += f'''    \\vspace{{0.2cm}}
    {{\\small submitted in partial fulfillment of the requirements for the degree of\\par}}
    \\vspace{{0.1cm}}
    {{\\normalsize\\bfseries {_latex_escape_text(options.course)}\\par}}
'''

            preamble += r'''
    \vfill
    % Author Block
    {\small submitted by\par}
    \vspace{0.15cm}
'''
            if options.author:
                preamble += f'''    {{\\normalsize\\bfseries {_latex_escape_text(options.author)}\\par}}
'''
            # Student ID or Matriculation number
            if options.student_id:
                preamble += f'''    \\vspace{{0.08cm}}
    {{\\small Matriculation No.: {_latex_escape_text(options.student_id)}\\par}}
'''
            if hasattr(options, 'matriculation_number') and options.matriculation_number:
                preamble += f'''    \\vspace{{0.08cm}}
    {{\\small Matriculation No.: {_latex_escape_text(options.matriculation_number)}\\par}}
'''

            preamble += r'''
    \vfill
    % Supervision Block
'''
            # Add advisor/supervisor
            if options.instructor:
                preamble += f'''    {{\\small\\bfseries First Supervisor:}} {{\\small {_latex_escape_text(options.instructor)}\\par}}
'''
            # Add second examiner if provided
            if hasattr(options, 'second_examiner') and options.second_examiner:
                preamble += f'''    \\vspace{{0.08cm}}
    {{\\small\\bfseries Second Examiner:}} {{\\small {_latex_escape_text(options.second_examiner)}\\par}}
'''

            # Add system credit
            if options.system_credit:
                preamble += f'''    \\vspace{{0.2cm}}
    {{\\footnotesize\\itshape {_latex_escape_text(options.system_credit)}\\par}}
'''

            preamble += r'''
    \vfill
    % Bottom section - Location and Date
'''
            # Add location if provided
            if hasattr(options, 'location') and options.location:
                preamble += f'''    {{\\small {_latex_escape_text(options.location)}\\par}}
'''
            # Add submission date, regular date, or default to today
            if hasattr(options, 'submission_date') and options.submission_date:
                display_date = options.submission_date
            elif options.date:
                display_date = options.date
            else:
                display_date = datetime.now().strftime('%B %d, %Y')
            preamble += f'''    \\vspace{{0.08cm}}
    {{\\small {_latex_escape_text(display_date)}\\par}}
'''

            preamble += r'''
    \vspace{0.5in}
  \end{titlepage}
}

'''

        # Add front matter page numbering (roman numerals) if TOC enabled
        if options.enable_toc:
            preamble += r'''
% Front matter page numbering (roman numerals for title page + TOC)
\usepackage{tocloft}
\pagenumbering{roman}
% Hook to switch to arabic numbering after TOC
\AfterPreamble{%
  \let\oldtableofcontents\tableofcontents
  \renewcommand{\tableofcontents}{%
    \clearpage
    \oldtableofcontents
    \cleardoublepage
    \pagenumbering{arabic}%
  }%
}
'''

        return preamble

    def _run_pandoc(
        self,
        md_file: Path,
        output_pdf: Path,
        preamble_path: Path,
        options: PDFGenerationOptions
    ) -> EngineResult:
        """
        Run Pandoc to convert markdown to PDF.

        Uses Pandoc's default template with custom preamble for robustness.

        Args:
            md_file: Input markdown file
            output_pdf: Output PDF path
            preamble_path: LaTeX preamble path
            options: Generation options

        Returns:
            EngineResult with success/failure
        """
        try:
            # Pandoc command with default template + custom preamble
            # This is more robust than a full custom template
            # Use absolute paths to avoid any path resolution issues
            margin = options.margins.replace('in', 'in').replace('cm', 'cm')

            # Find xelatex path (may not be in PATH)
            xelatex_path = self._find_xelatex()

            cmd = [
                'pandoc',
                str(md_file.resolve()),
                '-o', str(output_pdf.resolve()),
                f'--pdf-engine={xelatex_path}',  # Use XeLaTeX for full Unicode support
                '--include-in-header', str(preamble_path.resolve()),
                '--from', 'markdown+autolink_bare_uris+raw_tex',
                '--variable', f'geometry:margin={margin}',
                '--variable', f'fontsize={options.font_size}',
                '--variable', 'papersize:letter',
                '--variable', 'documentclass:article',
            ]

            # Add title page metadata if provided.
            # Pandoc --variable values are substituted literally (NOT LaTeX-escaped)
            # into \title{...}/\author{...}, so escape special chars (&, %, _, #, ...)
            # or a title like "Cost & Benefit" aborts the XeLaTeX compile.
            if options.title:
                cmd.extend(['--variable', f'title={_latex_escape_text(options.title)}'])
            if options.author:
                cmd.extend(['--variable', f'author={_latex_escape_text(options.author)}'])
            if options.date:
                cmd.extend(['--variable', f'date={_latex_escape_text(options.date)}'])

            # Add institutional metadata for professional cover page
            if options.institution:
                cmd.extend(['--variable', f'institution={_latex_escape_text(options.institution)}'])
            if options.department:
                cmd.extend(['--variable', f'department={_latex_escape_text(options.department)}'])
            if options.course:
                cmd.extend(['--variable', f'course={_latex_escape_text(options.course)}'])
            if options.instructor:
                cmd.extend(['--variable', f'instructor={_latex_escape_text(options.instructor)}'])

            # Add table of contents if enabled
            if options.enable_toc:
                cmd.append('--toc')
                cmd.extend(['--variable', f'toc-depth={options.toc_depth}'])
                cmd.extend(['--variable', 'toc-title=Table of Contents'])

            # NOTE: Do NOT use --number-sections because draft markdown files
            # typically have manual section numbering embedded (e.g., "2.1 The Evolution...")
            # Using --number-sections would create duplicates like "1.1 2.1 The Evolution..."

            # Run Pandoc
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,  # 3 minute timeout for LaTeX compilation
                cwd=output_pdf.parent  # Run in output directory
            )

            if result.returncode != 0:
                # Extract useful error message from LaTeX output
                error_lines = result.stderr.split('\n')
                # Look for actual error messages (lines starting with !)
                latex_errors = [line for line in error_lines if line.startswith('!')]

                if latex_errors:
                    error_msg = '\n'.join(latex_errors[:3])  # First 3 errors
                else:
                    error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr

                return EngineResult(
                    success=False,
                    engine_name=self.get_name(),
                    error_message=f"Pandoc/LaTeX compilation failed:\n{error_msg}"
                )

            if not output_pdf.exists():
                return EngineResult(
                    success=False,
                    engine_name=self.get_name(),
                    error_message="Pandoc did not generate PDF file"
                )

            # Check for warnings in LaTeX output
            warnings = []
            if 'Warning' in result.stdout or 'Warning' in result.stderr:
                warnings.append("LaTeX generated warnings (non-critical)")

            return EngineResult(
                success=True,
                engine_name=self.get_name(),
                output_path=output_pdf,
                warnings=warnings
            )

        except subprocess.TimeoutExpired:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message="Pandoc/LaTeX compilation timed out (>3 minutes)"
            )
        except Exception as e:
            return EngineResult(
                success=False,
                engine_name=self.get_name(),
                error_message=f"Pandoc execution failed: {str(e)}"
            )

    def _cleanup_latex_files(self, pdf_path: Path) -> None:
        """
        Clean up LaTeX auxiliary files.

        Args:
            pdf_path: Path to generated PDF (used to find auxiliary files)
        """
        # LaTeX generates many auxiliary files
        aux_extensions = ['.aux', '.log', '.out', '.toc', '.lof', '.lot']

        for ext in aux_extensions:
            aux_file = pdf_path.parent / f"{pdf_path.stem}{ext}"
            if aux_file.exists():
                try:
                    aux_file.unlink()
                except Exception:
                    pass  # Ignore cleanup errors

    def _extract_yaml_metadata(self, md_content: str) -> Dict[str, Any]:
        """
        Extract YAML frontmatter metadata from markdown content.

        Args:
            md_content: Markdown content with YAML frontmatter

        Returns:
            Dictionary of YAML metadata (empty dict if no YAML found)
        """
        if not md_content.strip().startswith('---'):
            return {}

        try:
            # Extract YAML frontmatter (between first and second ---)
            parts = md_content.split('---', 2)
            if len(parts) < 3:
                return {}

            yaml_content = parts[1]
            metadata = yaml.safe_load(yaml_content)

            return metadata if isinstance(metadata, dict) else {}

        except Exception:
            # YAML parsing failed, return empty dict
            return {}

    def _normalize_yaml_for_pandoc(self, md_content: str) -> str:
        """
        Normalize YAML frontmatter field names to English for Pandoc compatibility.

        Pandoc only recognizes English field names (title, subtitle, author, date)
        for creating styled paragraphs in DOCX/PDF output. This function translates
        localized field names back to English while preserving the field values.

        Supported translations:
        - German: titel→title, untertitel→subtitle, autor→author, datum→date
        - Spanish: título→title, subtítulo→subtitle, autor→author, fecha→date
        - French: titre→title, sous-titre→subtitle, auteur→author, date→date

        Args:
            md_content: Markdown content with YAML frontmatter

        Returns:
            Markdown content with normalized YAML field names
        """
        import re

        # Translation map: localized → English
        field_translations = {
            # German (18 fields)
            'titel:': 'title:',
            'untertitel:': 'subtitle:',
            'autor:': 'author:',
            'datum:': 'date:',
            'wortzahl:': 'word_count:',
            'seitenzahl:': 'page_count:',
            'sprache:': 'language:',
            'thema:': 'topic:',
            'schlagwörter:': 'keywords:',
            'qualitäts_bewertung:': 'quality_score:',
            'system_ersteller:': 'system_creator:',
            'zitate_verifiziert:': 'citations_verified:',
            'visuelle_elemente:': 'visual_elements:',
            'generierungs_methode:': 'generation_method:',
            'beschreibung_showcase:': 'showcase_description:',
            'system_fähigkeiten:': 'system_capabilities:',
            'aufruf_zur_aktion:': 'call_to_action:',
            'lizenz:': 'license:',

            # Spanish (5 fields)
            'título:': 'title:',
            'subtítulo:': 'subtitle:',
            'fecha:': 'date:',
            'recuento_de_palabras:': 'word_count:',
            'idioma:': 'language:',

            # French (5 fields)
            'titre:': 'title:',
            'sous-titre:': 'subtitle:',
            'auteur:': 'author:',
            'nombre_de_mots:': 'word_count:',
            'langue:': 'language:',
        }

        # Only process if YAML frontmatter exists
        if not md_content.strip().startswith('---'):
            return md_content

        # Extract YAML frontmatter
        parts = md_content.split('---', 2)
        if len(parts) < 3:
            return md_content

        yaml_content = parts[1]
        rest_content = parts[2]

        # Translate field names (case-insensitive)
        for localized, english in field_translations.items():
            yaml_content = re.sub(
                f'^{re.escape(localized)}',
                english,
                yaml_content,
                flags=re.MULTILINE | re.IGNORECASE
            )

        # Strip custom fields that Pandoc doesn't recognize
        # Only keep: title, subtitle, author, date, abstract
        # CRITICAL: For showcase theses (with custom cover pages), EXCLUDE title/subtitle
        # to prevent Pandoc from inserting duplicate title headings that appear in ToC
        pandoc_recognized_fields = ['title', 'subtitle', 'author', 'date', 'abstract']

        # Check if this is a showcase draft (has custom professional cover page)
        # Detection: either has showcase_description field OR project_type contains "showcase"
        is_showcase = ('showcase_description:' in yaml_content.lower() or
                      'showcase' in yaml_content.lower())

        # If showcase draft, remove title/subtitle from allowed fields
        # The custom titlepage already renders these - Pandoc shouldn't duplicate them
        if is_showcase:
            pandoc_recognized_fields = ['author', 'date', 'abstract']

        yaml_lines = yaml_content.split('\n')
        filtered_lines = []

        for line in yaml_lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('#'):
                # Keep empty lines and comments
                filtered_lines.append(line)
                continue

            # Check if this line starts with a field name
            field_match = re.match(r'^(\w+):', line_stripped)
            if field_match:
                field_name = field_match.group(1).lower()
                if field_name in pandoc_recognized_fields:
                    filtered_lines.append(line)
                # Skip lines with unrecognized fields
            else:
                # Keep continuation lines (indented or quoted multi-line values)
                filtered_lines.append(line)

        yaml_content = '\n'.join(filtered_lines)

        # Reconstruct markdown
        return f'---{yaml_content}---{rest_content}'

    def _unwrap_markdown_fence(self, md_content: str) -> str:
        """
        Remove outer ```markdown wrapper if present (BUG #20).

        Recent draft generations incorrectly wrap the entire file content
        in a code fence like:
            ```markdown
            ---
            title: ...
            ---
            # Content...
            ```

        This causes Pandoc to treat the entire draft as verbatim code.

        Args:
            md_content: Markdown content potentially wrapped in code fence

        Returns:
            Markdown content with outer wrapper removed
        """
        lines = md_content.strip().split('\n')

        # Check if first line is ```markdown and last line is ```
        if (len(lines) >= 3 and
            lines[0].strip().startswith('```') and
            lines[-1].strip() == '```'):
            # Remove first and last line
            return '\n'.join(lines[1:-1])

        return md_content

    def _remove_title_heading(self, md_content: str, original_content: str) -> str:
        """
        Remove first level-1 heading for showcase theses (BUG: Title in ToC).

        Showcase theses have a custom professional cover page that renders
        the title. The markdown body often includes the title as a level-1
        heading (# Title...), which creates a duplicate title entry in the
        Table of Contents. This method removes that first heading.

        Args:
            md_content: Markdown content after YAML frontmatter
            original_content: Original content BEFORE normalization (for showcase detection)

        Returns:
            Markdown content with first # heading removed (if showcase draft)
        """
        import re

        # Only process showcase theses (check for "showcase" in ORIGINAL content)
        # Use original because normalization strips custom fields that contain "showcase"
        if 'showcase' not in original_content.lower():
            return md_content

        # Split by YAML frontmatter
        parts = md_content.split('---', 2)
        if len(parts) < 3:
            return md_content

        yaml_part = parts[1]
        body_part = parts[2]

        # NEVER remove standard academic section headings
        # These are legitimate sections, not duplicate titles
        protected_headings = [
            'abstract', 'introduction', 'literature', 'methodology', 'method',
            'results', 'discussion', 'conclusion', 'references', 'appendix',
            'background', 'chapter', 'analysis', 'findings'
        ]

        # Find first level-1 heading
        match = re.search(r'^\s*#\s+([^\n]+)\n', body_part, flags=re.MULTILINE)
        if not match:
            return md_content

        heading_text = match.group(1).strip().lower()

        # Don't remove if it's a protected heading or starts with a number
        if any(heading_text.startswith(p) for p in protected_headings):
            return md_content
        if heading_text and heading_text[0].isdigit():
            return md_content

        # Remove the title heading (it's a duplicate of the cover page title)
        body_part = re.sub(
            r'^\s*#\s+[^\n]+\n+',
            r'',
            body_part,
            count=1,
            flags=re.MULTILINE
        )

        # Reconstruct
        return f'---{yaml_part}---{body_part}'

    def _strip_code_blocks(self, md_content: str) -> str:
        """
        Remove markdown code blocks (fenced with triple backticks) from content.

        This fixes PDF truncation caused by ASCII diagrams in code blocks.
        LaTeX renders code blocks as unbreakable verbatim text, causing:
        - Overfull hbox errors (lines too wide for page)
        - Document truncation (e.g., 122 pages → 39 pages)
        - Missing citations and content

        Also handles orphaned code fences (opening fence with no closing fence)
        by removing just the orphaned fence line instead of all content after it.

        Args:
            md_content: Markdown content potentially containing code blocks

        Returns:
            Markdown content with all code blocks removed
        """
        import logging
        logger = logging.getLogger(__name__)

        # Separate YAML frontmatter from body to avoid processing YAML fences
        if md_content.strip().startswith('---'):
            parts = md_content.split('---', 2)
            if len(parts) >= 3:
                yaml_section = f"---{parts[1]}---"
                body_content = parts[2]
            else:
                # No valid YAML, process entire content
                yaml_section = ""
                body_content = md_content
        else:
            yaml_section = ""
            body_content = md_content

        # First pass: find orphaned code fences (opening with no closing)
        lines = body_content.split('\n')
        fence_stack = []  # Track line indices of opening fences

        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                if fence_stack:
                    # This closes the most recent opening fence
                    fence_stack.pop()
                else:
                    # This is an opening fence
                    fence_stack.append(i)

        # Any remaining fences in the stack are orphaned (no closing fence)
        orphaned_fence_lines = set(fence_stack)
        if orphaned_fence_lines:
            logger.warning(f"Found {len(orphaned_fence_lines)} orphaned code fence(s) at lines: {list(orphaned_fence_lines)}")

        # Second pass: remove code blocks but preserve content after orphaned fences
        result = []
        in_code_block = False

        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                if i in orphaned_fence_lines:
                    # Skip orphaned fence line but don't enter code block mode
                    continue
                # Toggle code block state for properly paired fences
                in_code_block = not in_code_block
                continue  # Skip the fence line itself

            if not in_code_block:
                result.append(line)

        cleaned_body = '\n'.join(result)

        # Reconstruct with YAML intact
        return yaml_section + cleaned_body if yaml_section else cleaned_body


    def _normalize_bullet_lists(self, md_content: str) -> str:
        """
        Normalize markdown bullet list formatting for consistent PDF rendering.
        
        Fixes BUG #6: Bullet points (`*   ...`) not rendering as proper lists.
        
        The AI agents sometimes use inconsistent bullet formatting:
        - `*   ` (asterisk with multiple spaces)
        - `* ` (asterisk with one space)
        - `-  ` (hyphen with multiple spaces)
        
        Pandoc/LaTeX may not recognize these variations as proper lists,
        rendering them as literal asterisks instead of bullet characters.
        
        This method normalizes all bullet variations to the standard format:
        `- ` (hyphen with single space)
        
        Args:
            md_content: Markdown content with potential bullet formatting issues
            
        Returns:
            Markdown content with normalized bullet formatting
        """
        import re
        
        # Separate YAML frontmatter from body to avoid processing YAML
        if md_content.strip().startswith('---'):
            parts = md_content.split('---', 2)
            if len(parts) >= 3:
                yaml_section = f"---{parts[1]}---"
                body_content = parts[2]
            else:
                yaml_section = ""
                body_content = md_content
        else:
            yaml_section = ""
            body_content = md_content
        
        # Normalize bullet patterns in body only
        # Pattern 1: `*   ` or `*  ` or `* ` at start of line -> `- `
        body_content = re.sub(r'^\*\s+', '- ', body_content, flags=re.MULTILINE)
        
        # Pattern 2: Multiple spaces after hyphen -> single space
        body_content = re.sub(r'^-\s{2,}', '- ', body_content, flags=re.MULTILINE)
        
        # Pattern 3: Nested bullets with inconsistent spacing
        # `  *   ` -> `  - ` (preserve indentation)
        body_content = re.sub(r'^(\s+)\*\s+', r'\1- ', body_content, flags=re.MULTILINE)
        body_content = re.sub(r'^(\s+)-\s{2,}', r'\1- ', body_content, flags=re.MULTILINE)
        
        return yaml_section + body_content if yaml_section else body_content

    def _sanitize_unicode_for_latex(self, md_content: str) -> str:
        """
        Replace problematic Unicode characters with ASCII/LaTeX equivalents.

        Fixes Unicode errors like U+FF1A (fullwidth colon) and Korean Hangul
        characters (U+CD08 etc.) that break pdflatex compilation.
        These characters are common in citations from international sources.

        Args:
            md_content: Markdown content with potential Unicode issues

        Returns:
            Markdown content with sanitized characters
        """
        replacements = {
            # Fullwidth punctuation (common in East Asian sources)
            '：': ':',    # U+FF1A fullwidth colon
            '，': ',',    # U+FF0C fullwidth comma
            '（': '(',    # U+FF08 fullwidth left paren
            '）': ')',    # U+FF09 fullwidth right paren
            '　': ' ',    # U+3000 ideographic space

            # Typographic quotes and dashes
            ''': "'",    # U+2018 left single quotation mark
            ''': "'",    # U+2019 right single quotation mark
            '"': '"',    # U+201C left double quotation mark
            '"': '"',    # U+201D right double quotation mark
            '–': '-',    # U+2013 en dash
            '—': '--',   # U+2014 em dash
            '…': '...', # U+2026 horizontal ellipsis

            # Korean Hangul characters (replace with romanized equivalents)
            # FIXED: Korean character 초 (U+CD08) causing LibreOffice fallback
            '초': 'cho',  # U+CD08 Korean "cho" (initial)
            '기': 'gi',   # U+AE30 Korean "gi" (machine/base)
            '코': 'ko',   # U+CF54 Korean "ko" (code)
            '드': 'deu',  # U+B4DC Korean "deu" (de)
        }

        for unicode_char, ascii_equiv in replacements.items():
            md_content = md_content.replace(unicode_char, ascii_equiv)

        return md_content

    def _escape_latex_special_chars(self, md_content: str) -> str:
        """
        Escape LaTeX special characters in URLs and plain text to prevent compilation errors.

        Fixes BUG #21: "Missing $ inserted" errors from unescaped characters.

        Common problematic characters:
        - `_` (underscore) in URLs like `doi.org/10.1007/978-3-319-64964-1_5`
        - `%` (percent) in URL-encoded strings like `%20`
        - `&` (ampersand) in query strings

        This function:
        1. Wraps bare URLs in angle brackets for Pandoc to properly process
        2. Fixes `Https://` to `https://` (common AI hallucination)
        3. Escapes remaining special chars in plain text (outside URLs and math)
        """
        import re

        # Separate YAML frontmatter from body
        if md_content.strip().startswith('---'):
            parts = md_content.split('---', 2)
            if len(parts) >= 3:
                yaml_section = f'---{parts[1]}---'
                body_content = parts[2]
            else:
                yaml_section = ''
                body_content = md_content
        else:
            yaml_section = ''
            body_content = md_content

        # Fix 1: Normalize Https:// to https:// (AI sometimes capitalizes)
        body_content = re.sub(r'\bHttps://', 'https://', body_content)
        body_content = re.sub(r'\bHttp://', 'http://', body_content)

        # Fix 2: Wrap bare URLs in angle brackets for Pandoc to handle properly
        url_pattern = r'(?<![<\[])(https?://[^\s\)\]>]+)(?![>\]])'
        body_content = re.sub(url_pattern, r'<\1>', body_content)

        # Fix 3: Escape underscores in plain text (outside URLs, math mode, and emphasis)
        lines = body_content.split('\n')
        processed_lines = []

        for line in lines:
            if '$' in line:
                processed_lines.append(line)
                continue
            if '<http' in line:
                processed_lines.append(line)
                continue
            if line.strip().startswith('|') and line.strip().endswith('|'):
                processed_lines.append(line)
                continue
            if '_' in line and not re.search(r'[*_]{1,2}\w+[*_]{1,2}', line):
                line = re.sub(r'(?<!\\)_(?!\w+_)', r'\\_', line)
            processed_lines.append(line)

        body_content = '\n'.join(processed_lines)

        return yaml_section + body_content if yaml_section else body_content
