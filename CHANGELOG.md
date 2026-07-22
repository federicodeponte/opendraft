# Changelog

All notable changes are documented in this file.

## 1.7.4 - 2026-07-22

### Added
- LaTeX (`.tex`) output alongside the existing PDF, DOCX, and Markdown exports.
  Every generated paper (and research exposé) now also produces a standalone,
  compilable `<name>.tex` next to `<name>.pdf`/`<name>.docx`, bundled into the
  ZIP. The `.tex` reuses the same Pandoc pipeline, preprocessing, and preamble as
  the PDF path, so it carries the same style-formatted References/bibliography
  (APA/IEEE/Chicago/MLA) as the PDF and compiles with XeLaTeX. It ships with a
  `% !TeX program = xelatex` header. If Pandoc is not installed the `.tex` step
  logs a warning and is skipped; the run still completes with its PDF/DOCX
  (graceful degradation, never crashes the run).

### Fixed
- Title-page metadata (title, author, institution, department, advisor, ...) was
  interpolated into the LaTeX preamble and Pandoc `--variable` values without
  escaping, so a value containing `&`, `%`, `_`, `#`, `$`, `{`, or `}` produced a
  document that Pandoc accepted but XeLaTeX rejected ("File ended while scanning
  use of `\@argdef`"). Special characters are now escaped for both the PDF and the
  new `.tex` output.

## 1.7.3 - 2026-07-20

### Fixed
- P1: `pip install opendraft` shipped no prompt files, so the Scribe phase crashed
  with `FileNotFoundError` loading `prompts/01_research/scribe.md` right after the
  Scout/citation phase succeeded (reinstalling did not help). The prompt markdown
  lived in a top-level `prompts/` directory that was never declared as package data
  for the wheel built from `engine/pyproject.toml` (only the sdist-only `opendraft`
  glob was set). This is a regression of issue #26. The `prompts/` directory is now
  a proper `prompts` package shipped as package data in both the wheel and the sdist,
  and `load_prompt` resolves prompts via `importlib.resources` with filesystem
  fallbacks so it works from an installed wheel, a source checkout, or zipimport.
- Scout "Success Rate" could exceed 100% (e.g. 190%) because it divided total
  citations by the number of research topics. It now reports the fraction of topics
  that yielded at least one citation, capped at 100%.

### Guarded
- Added regression tests that assert the real PyPI publisher (`engine/pyproject.toml`)
  ships the prompts and that `prompts/__init__.py` exists.

## 2026-02-16

### Added
- CI quality gate workflow: `.github/workflows/quality.yml`
- Maintainer push/auth runbook: `docs/MAINTAINER_PUSH_RUNBOOK.md`
- Automated push preflight checker: `scripts/push-preflight.sh`

### Changed
- Migrated Gemini runtime usage from legacy SDK to `google-genai` wrappers across engine modules.
- Replaced deprecated `google-generativeai` dependency pins with `google-genai>=1.0.0`.
- Stabilized pytest harness with strict markers and integration test separation.

### Fixed
- Output cleaning regression that could strip real references sections.
- Live factcheck integration tests now skip safely in offline/restricted environments.

### Verification
- `python3 -W error::SyntaxWarning -m compileall -q engine tests` passed.
- `python3 -m pytest tests -q` passed (`286 passed, 4 deselected`).
- Push preflight passed with clean sync and correct maintainer account.

### Follow-up
- Aligned CLI/npm requirement consistency (`6e74e75`).
- Hardened live script execution paths (`python tests/test_live_crafter.py`, `python tests/audit_output.py`) with prerequisite-aware skip behavior.
- Expanded CI quality workflow to execute `python -m pytest tests -q`.
- Added secret-gated live-validation workflow (`.github/workflows/live-validation.yml`) for weekly/manual execution of API-backed checks.
- Fixed live audit model selection to use `GEMINI_MODEL` override with `gemini-2.0-flash` fallback (`f8b8a6c`).
- Verified live-validation workflow success on GitHub Actions (`run 22061717973`).
- Fixed quality CI pytest collection error by removing stale `genai.GenerativeModel` annotation from `engine/utils/citation_compiler.py`.
