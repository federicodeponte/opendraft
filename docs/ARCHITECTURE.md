# OpenDraft Architecture

> 19-agent pipeline for automated academic paper generation.

See also: [PIPELINE.md](PIPELINE.md) for operational details and word count targets.

---

## Pipeline Phases

```
  Research ──> Structure ──> Compose ──> QA ──> Export

  Phase 1       Phase 2       Phase 3     Phase 4     Phase 5
  4 agents      2 agents +    1 agent     3 agents +  deterministic
  (LLM)         citation      (x6-7       compile +   (Pandoc)
                mgmt (det.)   sections)   abstract
```

### Phase 1: Research

Discover and analyze 50+ academic papers via multi-API cascade.

| Agent | Prompt | Input | Output |
|-------|--------|-------|--------|
| Scout | `01_research/scout.md` | Topic + config | `scout_result` (citations list), `scout_output` (markdown) |
| Deep Research | `01_research/deep_research.md` | Topic (when Scout finds < threshold) | Additional citations via extended search |
| Scribe | `01_research/scribe.md` | Discovered papers | `scribe_output` (paper summaries) |
| Signal | `01_research/signal.md` | All research | `signal_output` (gaps & trends) |

**Citation discovery** (managed by `CitationResearcher`), which finds
candidates. Any one source satisfies this stage; it establishes nothing on its
own:
1. Crossref / OpenAlex / Semantic Scholar (queried in parallel for academic topics)
2. Serper / Gemini Grounded Search (URL-based results, usually no DOI)
3. LLM fallback (Gemini training data). **Disabled by default**; output is
   permanently tagged `llm_unverified`.

`QueryRouter` classifies each query to pick the optimal starting API.

**Citation confirmation** (`MultiSourceConfirmer`), which decides what is kept.
Each candidate's DOI is looked up directly in Crossref, OpenAlex and Semantic
Scholar. By default a candidate survives only if at least 2 of the 3 hold that
DOI; single-source candidates are dropped. Every kept citation records
`verification_status` and `verification_sources`. See the README section
"Citation verification" for the full status vocabulary and its limits.

### Phase 2: Structure

Design and format the paper outline.

| Agent | Prompt | Input | Output |
|-------|--------|-------|--------|
| Architect | `02_structure/architect.md` | Topic + gaps + research | `architect_output` (outline) |
| Formatter | `02_structure/formatter.md` | Outline + citation style | `formatter_output` (styled outline) |

### Phase 2.5: Citation Management

Mostly deterministic; step 5 makes LLM judge calls. Runs as pipeline code in
`draft_generator.py`.

1. **Deduplicate** citations (fuzzy title + DOI matching)
2. **Scrape titles** from URLs for citations missing metadata
3. **Scrape metadata** (DOI lookup, CrossRef enrichment)
4. **Quality filter** (`CitationQualityFilter`, strict mode) — broken URLs, junk
   metadata, no topical keyword overlap
5. **Claim-level verification** (`CitationClaimVerifier`) — judges each surviving
   source against the paper topic and removes confidently off-topic ones.
   Reports land in the research folder as `citation_claim_verification.md`/`.json`.
   Existence of the source is already settled upstream by multi-source
   confirmation; this is the separate question of relevance.
6. **Build** `citation_database` + `citation_summary` with `{cite_XXX}` IDs

### Phase 3: Compose

Single agent (Crafter) invoked once per section with different context.

| Agent | Prompt | Input | Output |
|-------|--------|-------|--------|
| Crafter (x6-7) | `03_compose/crafter.md` | Outline + citation_summary + prior sections | Section markdown with `{cite_XXX}` refs |

Sections written: Introduction, Literature Review, Methodology, Results, Discussion, Conclusion, Appendices (conditional).

### Phase 3.5: Quality Assurance

Advisory-only reports — do not block the pipeline.

| Agent | Prompt | Input | Output |
|-------|--------|-------|--------|
| Thread | `03_compose/thread.md` | All sections | `thread_report` (coherence issues) |
| Narrator | `03_compose/narrator.md` | All sections | `narrator_report` (voice issues) |
| FactCheck | `04_validate/factcheck_extract.md` | Full draft | `qa_factcheck.md` (claim verification) |

### Phase 4: Compile & Enhance

| Step | Agent/Process | Input | Output |
|------|---------------|-------|--------|
| Assembly | deterministic | All section outputs | Single markdown document |
| Citation compile | deterministic (`citation_compiler.py`) | Markdown + citation_database | `{cite_XXX}` replaced with formatted refs + reference list |
| Abstract | `06_enhance/abstract_generator.md` | Complete draft | Abstract + YAML metadata prepended |
| Post-processing | deterministic | Final markdown | Table fixes, dedup appendices, AI language cleanup, heading localization |

### Phase 5: Export (deterministic)

| Format | Engine | Output |
|--------|--------|--------|
| PDF | Pandoc + LaTeX (or WeasyPrint / LibreOffice fallback) | `paper.pdf` |
| DOCX | Pandoc | `paper.docx` |
| Markdown | passthrough | `final_draft.md` |

### Optional Agents (manual workflow)

These agents are available for human-in-the-loop iteration via Cursor/Claude Code but are **not** called in the automated pipeline.

| # | Agent | Phase | Prompt | Role |
|---|-------|-------|--------|------|
| 12 | Skeptic | Validate | `04_validate/skeptic.md` | Critical analysis: weak arguments, padding, contradictions |
| 13 | Verifier | Validate | `04_validate/verifier.md` | Citation DOI/author/date verification |
| 14 | Referee | Validate | `04_validate/referee.md` | Simulated peer review (accept/revise/reject) |
| 15 | Citation Verifier | Refine | `05_refine/citation_verifier.md` | Deep citation format checking |
| 16 | Voice | Refine | `05_refine/voice.md` | Match author's writing style |
| 17 | Entropy | Refine | `05_refine/entropy.md` | Reduce AI-detectable patterns |
| 18 | Polish | Refine | `05_refine/polish.md` | Grammar, repetition, hedging pass |
| 19 | Enhancer | Enhance | `06_enhance/enhancer.md` | Add tables, figures, limitations |

---

## Data Flow Summary

```
Phase 1  =>  scout_result, scout_output, scribe_output, signal_output
Phase 2  =>  architect_output, formatter_output
Phase 2.5 => citation_database, citation_summary
Phase 3  =>  intro_output, lit_review_output, methodology_output,
             results_output, discussion_output, conclusion_output,
             appendix_output
Phase 3.5 => thread_report, narrator_report, qa_factcheck.md
Phase 4  =>  compiled_draft, final_draft.md
Phase 5  =>  paper.pdf, paper.docx
```

---

## Output Directory Structure

Each pipeline run produces a self-contained output directory:

```
draft_output/
├── research/                   # Phase 1 outputs
│   ├── papers/                 # Individual paper summaries (one per source)
│   ├── combined_research.md    # Merged research findings
│   ├── research_gaps.md        # Signal agent gap analysis
│   ├── bibliography.json       # Citation data (carries verification_status +
│   │                           #   verification_sources per citation)
│   ├── citation_claim_verification.md    # Claim-level relevance report
│   └── citation_claim_verification.json  # Per-citation verdicts
│
├── drafts/                     # Phase 2-4 outputs
│   ├── outline.md              # Architect output
│   ├── outline_formatted.md    # Formatter output
│   ├── citation_database.json  # Deduplicated citation DB
│   ├── citation_summary.md     # {cite_XXX} reference list for agents
│   ├── intro.md                # Section drafts (Crafter outputs)
│   ├── literature_review.md
│   ├── methodology.md
│   ├── results.md
│   ├── discussion.md
│   ├── conclusion.md
│   ├── appendices.md           # (conditional)
│   ├── qa_thread.md            # Thread coherence report
│   ├── qa_narrator.md          # Narrator voice report
│   ├── qa_factcheck.md         # FactCheck verification report
│   └── final_draft.md          # Assembled + compiled + post-processed
│
├── tools/                      # Refinement prompts for manual iteration
│   └── *.md                    # Generated prompts for Cursor/Claude Code
│
└── exports/                    # Phase 5 outputs
    ├── paper.pdf               # Final PDF
    ├── paper.docx              # Final Word document
    └── paper.md                # Final markdown (copy of final_draft.md)
```

---

## Key Source Files

| Component | Path |
|-----------|------|
| Pipeline orchestrator | `engine/draft_generator.py` |
| Agent runner | `engine/utils/agent_runner.py` |
| Pydantic LLM models | `engine/utils/models.py` |
| Citation research orchestrator | `engine/utils/api_citations/orchestrator.py` |
| Citation compiler | `engine/utils/citation_compiler.py` |
| Citation database | `engine/utils/citation_database.py` |
| Fact-check verifier | `engine/utils/factcheck_verifier.py` |
| Deep research planner | `engine/utils/deep_research.py` |
| Abstract generator | `engine/utils/abstract_generator.py` |
| PDF export | `engine/utils/export_professional.py` |
| All prompt files | `engine/prompts/` |
| Manual workflow guide | `engine/prompts/00_WORKFLOW.md` |
| Concurrency config | `engine/concurrency/concurrency_config.py` |

---

## LLM Output Validation

All LLM JSON parse sites are protected by Pydantic models (`engine/utils/models.py`):

| Model | Used In | Validates |
|-------|---------|-----------|
| `ResearchPlan` | `deep_research.py` | Gemini research plan (queries, outline, strategy) |
| `LLMCitationResponse` | `api_citations/orchestrator.py` | Single citation from LLM fallback |
| `CitationDatabaseSchema` | file validation | Citation database JSON structure |
| `FactCheckJudgeVerdict` | `factcheck_verifier.py` | Judge LLM verdict (verdict, confidence, wrong_part) |
| `FactCheckClaim` | `draft_generator.py` | Extracted factual claim (claim, section, line) |
