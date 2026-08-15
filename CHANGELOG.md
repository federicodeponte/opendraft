# Changelog

All notable changes are documented in this file.

## Unreleased

### Added
- **Claim-level citation verification** (`engine/utils/citation_claim_verifier.py`).
  Judges whether a citation is topically relevant to the claim it is attached
  to, which DOI/existence checking cannot detect. Runs in the citation phase
  against the paper topic (the only claim available before a draft exists) and
  writes `citation_claim_verification.md`/`.json` to the research folder.
  Verdicts are language-model judgements over title and abstract, not proofs;
  `UNCERTAIN` means unchecked, not passing.
- **Multi-source confirmation** (`engine/utils/api_citations/multi_source.py`).
  Looks a candidate's DOI up directly in Crossref, OpenAlex and Semantic
  Scholar and counts how many hold it.
- `get_paper_by_doi()` on the Crossref and Semantic Scholar clients (OpenAlex
  already had one).
- `verification_status`, `verification_sources` and `verification_notes` on
  `Citation`, persisted to `bibliography.json`. `verification_sources` is
  written even when empty so an unconfirmed citation cannot serialize to look
  like a confirmed one.
- `ENABLE_CLAIM_VERIFICATION`, `CLAIM_VERIFICATION_DROP_IRRELEVANT` and
  `CLAIM_VERIFICATION_MIN_CONFIDENCE`.

### Changed
- **BREAKING (behaviour):** `CitationResearcher.require_multi_source` defaults
  to `True`. A citation is kept only if at least 2 of {Crossref, OpenAlex,
  Semantic Scholar} independently hold its DOI. Single-source results are now
  dropped. **Expect fewer citations per draft.** Set
  `require_multi_source=False` for the old first-responder behaviour; those
  citations are then tagged `not_checked` rather than confirmed.
- **BREAKING (behaviour):** `CitationResearcher.enable_llm_fallback` defaults to
  `False`. Nothing external checks an LLM assertion. If enabled, its output is
  permanently tagged `llm_unverified`. `CitationCompiler` no longer enables it.
- DOI-less web-search results are dropped by default; set
  `allow_unconfirmed_web_sources=True` to keep them (kept tagged).
- The citation phase now uses `CitationQualityFilter(strict_mode=True)`,
  matching the class default. It previously overrode it to `False`.
- `CitationResearcher` raises at construction if multi-source confirmation is
  required but fewer databases are enabled than the threshold needs.

### Fixed
- `CitationResearcher.close()` now closes the OpenAlex client; its session was
  left open for the life of the process.

### Documentation
- README, `docs/ARCHITECTURE.md`, `docs/PIPELINE.md` and `llms.txt` now
  describe discovery and confirmation as separate stages, and state the limits:
  confirmation shows a DOI is registered and indexed, not that the work
  supports the claim; OpenAlex and Semantic Scholar both ingest Crossref
  metadata, so the three are not fully independent.
- Removed the claim that citations are verified against **arXiv**. There is no
  arXiv API client in this engine; arxiv.org appears only as an allowlisted
  web-search domain and as a Semantic Scholar externalId.
- Removed the unsupported "95%+ success rate" figure from this subsystem rather
  than replacing it with a new unmeasured number. Citation-count figures in the
  README and `EVALUATION.md` are marked as predating this change.

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
