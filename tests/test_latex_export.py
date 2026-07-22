#!/usr/bin/env python3
"""
ABOUTME: Tests for the LaTeX (.tex) export path (export_latex / generate_latex)
ABOUTME: Verifies a standalone, structurally valid, special-char-safe .tex is produced
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from utils.export_professional import export_latex  # noqa: E402
from utils.pdf_engines.pandoc_engine import _latex_escape_text  # noqa: E402


PANDOC = shutil.which("pandoc") is not None
XELATEX = shutil.which("xelatex") is not None

pytestmark = pytest.mark.skipif(not PANDOC, reason="pandoc not installed")


CLEAN_MD = """---
title: "Transformer Architectures for Low-Resource Machine Translation"
author: "OpenDraft AI"
date: "July 2026"
institution: "OpenDraft University"
department: "Department of Computer Science"
degree: "Master of Science"
advisor: "Prof. Dr. A. Supervisor"
project_type: "Master Draft"
generated_by: "OpenDraft AI"
---

## Abstract
This paper studies transformers (Vaswani et al., 2017).

# 1. Introduction
Neural machine translation has advanced rapidly.

# 4. References

Vaswani, A. (2017). Attention is all you need. *NeurIPS*.
"""

# Metadata packed with LaTeX special characters (the regression that broke 1.7.3
# preamble/pandoc-variable interpolation).
SPECIAL_MD = """---
title: "Cost & Benefit_Analysis of 50% Tax #Reform"
author: "Anne_Marie O'Brien & Co."
date: "July 2026"
institution: "Ludwig & Maximilian University"
department: "Dept. of R&D"
degree: "Master of Science"
advisor: "Prof. Dr. Smith & Jones"
project_type: "Master Draft"
generated_by: "OpenDraft AI"
---

## Abstract
Body with 100% coverage & R&D notes (Vaswani et al., 2017).

# 1. Introduction
Text.

# 4. References

Vaswani, A. (2017). Attention is all you need. *NeurIPS*.
"""


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _assert_valid_standalone_tex(tex_path: Path):
    assert tex_path.exists()
    tex = tex_path.read_text(encoding="utf-8")
    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex
    assert "\\end{document}" in tex
    # References/bibliography must be embedded
    assert "References" in tex
    # Environments balanced
    begins = re.findall(r"\\begin\{([^}]+)\}", tex)
    ends = re.findall(r"\\end\{([^}]+)\}", tex)
    from collections import Counter
    assert Counter(begins) == Counter(ends)
    return tex


def test_export_latex_produces_standalone_tex(tmp_path):
    md = _write(tmp_path, "clean.md", CLEAN_MD)
    tex = tmp_path / "clean.tex"
    assert export_latex(md_file=md, output_tex=tex) is True
    _assert_valid_standalone_tex(tex)


def test_export_latex_escapes_special_chars(tmp_path):
    md = _write(tmp_path, "special.md", SPECIAL_MD)
    tex = tmp_path / "special.tex"
    assert export_latex(md_file=md, output_tex=tex) is True
    text = _assert_valid_standalone_tex(tex)
    # The title's special chars must be escaped in the source.
    assert "\\& Benefit\\_Analysis of 50\\% Tax \\#Reform" in text
    # No raw, unescaped ampersand should remain inside the title-page metadata.
    assert "Ludwig \\& Maximilian" in text


def test_latex_escape_helper():
    assert _latex_escape_text("A & B_C 50% #x") == "A \\& B\\_C 50\\% \\#x"
    assert _latex_escape_text(None) == ""
    assert _latex_escape_text("plain") == "plain"


def test_export_latex_wrong_extension_rejected(tmp_path):
    md = _write(tmp_path, "clean.md", CLEAN_MD)
    # A .txt target must not be written by the LaTeX exporter.
    out = tmp_path / "bad.txt"
    assert export_latex(md_file=md, output_tex=out) is False
    assert not out.exists()


@pytest.mark.skipif(not XELATEX, reason="xelatex not installed")
def test_special_char_tex_compiles(tmp_path):
    md = _write(tmp_path, "special.md", SPECIAL_MD)
    tex = tmp_path / "special.tex"
    assert export_latex(md_file=md, output_tex=tex) is True
    proc = subprocess.run(
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]
    assert (tmp_path / "special.pdf").exists()
