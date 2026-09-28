# OpenDraft Agent Pipeline

> **19 specialized AI agents** organized in 6 phases to produce a complete academic paper.

---

## Pipeline Overview

```
INPUT: Topic + Academic Level + Citation Style + Language
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 1: RESEARCH                                                  │
  │                                                                     │
  │  ┌──────────────┐   ┌─────────┐   ┌──────────┐                     │
  │  │  Scout + Deep │──>│  Scribe │──>│  Signal  │                     │
  │  │  Research     │   │         │   │          │                     │
  │  └──────────────┘   └─────────┘   └──────────┘                     │
  │  Find 50+ papers     Summarize     Identify gaps                    │
  │  via API cascade     each paper    & trends                         │
  └─────────────────────────────────────────────────────────────────────┘
                           |
              scout_result (citations[])
              scribe_output (summaries)
              signal_output (gap analysis)
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 2: STRUCTURE                                                 │
  │                                                                     │
  │  ┌────────────┐   ┌────────────┐                                    │
  │  │  Architect  │──>│  Formatter │                                    │
  │  └────────────┘   └────────────┘                                    │
  │  Design outline     Apply academic                                  │
  │  from gaps +        style formatting                                │
  │  topic              (APA/IEEE)                                      │
  └─────────────────────────────────────────────────────────────────────┘
                           |
              formatter_output (structured outline)
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 2.5: CITATION MANAGEMENT  (deterministic, no LLM)           │
  │                                                                     │
  │  Deduplicate citations -> Scrape titles -> Scrape metadata          │
  │  Build citation_summary with {cite_XXX} IDs for writing agents      │
  └─────────────────────────────────────────────────────────────────────┘
                           |
              citation_database + citation_summary
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 3: COMPOSE                                                   │
  │                                                                     │
  │  Same agent (Crafter), invoked 6-7 times with different prompts:    │
  │                                                                     │
  │  ┌───────────────┐  ┌──────────────────┐  ┌───────────────┐        │
  │  │ 1. Intro      │  │ 2.1 Lit Review   │  │ 2.2 Methods   │        │
  │  └───────────────┘  └──────────────────┘  └───────────────┘        │
  │  ┌───────────────┐  ┌──────────────────┐  ┌───────────────┐        │
  │  │ 2.3 Results   │  │ 2.4 Discussion   │  │ 3. Conclusion │        │
  │  └───────────────┘  └──────────────────┘  └───────────────┘        │
  │  ┌───────────────┐                                                  │
  │  │ 4. Appendices │  (conditional)                                   │
  │  └───────────────┘                                                  │
  │                                                                     │
  │  Each section receives: outline + citation_summary + prior sections  │
  │  Each section outputs:  markdown with {cite_XXX} placeholders       │
  └─────────────────────────────────────────────────────────────────────┘
                           |
              intro_output, body_output, conclusion_output, appendix_output
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 3.5: QUALITY ASSURANCE                                       │
  │                                                                     │
  │  ┌──────────┐   ┌────────────┐                                      │
  │  │  Thread   │   │  Narrator  │                                      │
  │  └──────────┘   └────────────┘                                      │
  │  Cross-section    Voice & tone                                      │
  │  coherence,       consistency,                                      │
  │  contradictions,  tense, hedging                                    │
  │  references                                                         │
  └─────────────────────────────────────────────────────────────────────┘
                           |
              QA reports (advisory, not blocking)
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 4: COMPILE & ENHANCE                                         │
  │                                                                     │
  │  1. Assemble all sections into single markdown                      │
  │  2. Citation Compiler (deterministic):                              │
  │     {cite_001} -> "(Smith et al., 2023)" or "[1]"                   │
  │     Generate reference list at end                                  │
  │  3. Abstract Generator (LLM agent):                                 │
  │     Reads full draft, writes abstract + YAML metadata               │
  │  4. Post-processing (deterministic):                                │
  │     fix tables, dedup appendices, clean AI language,                │
  │     localize headings                                               │
  └─────────────────────────────────────────────────────────────────────┘
                           |
              final_draft.md (complete paper)
                           |
                           v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PHASE 5: EXPORT  (no LLM)                                         │
  │                                                                     │
  │  Markdown ──> PDF  (via Pandoc + LaTeX)                             │
  │           └──> DOCX (via Pandoc)                                    │
  └─────────────────────────────────────────────────────────────────────┘
                           |
                           v
OUTPUT: paper.pdf + paper.docx
```

---

## Agent Reference

### Active Agents (13 used in automated pipeline)

| # | Agent | Phase | Prompt File | Role |
|---|-------|-------|-------------|------|
| 1 | **Scout** | 1: Research | `01_research/scout.md` | Find 50+ papers via Semantic Scholar, Crossref, Serper, Gemini Grounded |
| 2 | **Deep Research** | 1: Research | `01_research/deep_research.md` | Extended search when Scout finds too few papers |
| 3 | **Scribe** | 1: Research | `01_research/scribe.md` | Summarize each discovered paper |
| 4 | **Signal** | 1: Research | `01_research/signal.md` | Identify research gaps and emerging trends |
| 5 | **Architect** | 2: Structure | `02_structure/architect.md` | Design paper outline from topic + gaps |
| 6 | **Formatter** | 2: Structure | `02_structure/formatter.md` | Apply academic formatting rules to outline |
| 7 | **Crafter** (x6) | 3: Compose | `03_compose/crafter.md` | Write each section (Intro, Lit Review, Methods, Results, Discussion, Conclusion) |
| 8 | **Thread** | 3.5: QA | `03_compose/thread.md` | Check cross-section coherence and contradictions |
| 9 | **Narrator** | 3.5: QA | `03_compose/narrator.md` | Check voice, tone, tense consistency |
| 10 | **Citation Compiler** | 4: Compile | *(deterministic)* | Replace `{cite_XXX}` with formatted citations |
| 11 | **Abstract Generator** | 4: Compile | `06_enhance/abstract_generator.md` | Generate abstract from complete draft |

### Optional Agents (6 available via manual workflow)

These agents have prompt files and are documented in `00_WORKFLOW.md` but are **not called** in the current automated pipeline. They are designed for the manual Cursor/Claude Code workflow where a human iterates on the draft.

| # | Agent | Phase | Prompt File | Role |
|---|-------|-------|-------------|------|
| 12 | **Skeptic** | 4: Validate | `04_validate/skeptic.md` | Critical analysis: weak arguments, reference padding, contradictions |
| 13 | **Verifier** | 4: Validate | `04_validate/verifier.md` | Citation verification: DOIs, author names, dates |
| 14 | **Referee** | 4: Validate | `04_validate/referee.md` | Simulated peer review with accept/revise/reject decision |
| 15 | **Citation Verifier** | 5: Refine | `05_refine/citation_verifier.md` | Deep citation format checking against style guide |
| 16 | **Voice** | 5: Refine | `05_refine/voice.md` | Match author's personal writing style (optional) |
| 17 | **Entropy** | 5: Refine | `05_refine/entropy.md` | Reduce AI-detectable patterns |
| 18 | **Polish** | 5: Refine | `05_refine/polish.md` | Final grammar, repetition, and hedging pass |
| 19 | **Enhancer** | 6: Enhance | `06_enhance/enhancer.md` | Add tables, figures, limitations, future research |

---

## Data Flow Between Phases

```
Phase 1 outputs:
  scout_result     -> dict with 'citations' list (50+ Citation objects)
  scout_output     -> raw markdown of all found papers
  scribe_output    -> summarized research findings (markdown)
  signal_output    -> research gaps analysis (markdown)

Phase 2 outputs:
  architect_output -> structured outline (markdown)
  formatter_output -> formatted outline with style applied (markdown)

Phase 2.5 outputs:
  citation_database -> CitationDatabase with deduplicated, enriched citations
  citation_summary  -> formatted citation list with {cite_XXX} IDs for agents

Phase 3 outputs:
  intro_output       -> Chapter 1 markdown with {cite_XXX} refs
  lit_review_output   -> Section 2.1 markdown
  methodology_output  -> Section 2.2 markdown
  results_output      -> Section 2.3 markdown
  discussion_output   -> Section 2.4 markdown
  conclusion_output   -> Chapter 3 markdown
  appendix_output     -> Chapter 4 markdown (conditional)

Phase 3.5 outputs:
  thread_report   -> narrative consistency issues (advisory)
  narrator_report -> voice consistency issues (advisory)

Phase 4 outputs:
  compiled_draft  -> full markdown, {cite_XXX} replaced with formatted citations
  final_draft     -> compiled + abstract + post-processing cleanup

Phase 5 outputs:
  paper.pdf       -> final PDF via Pandoc + LaTeX
  paper.docx      -> final DOCX via Pandoc
```

---

## Citation Discovery and Confirmation (Scout Detail)

`CitationResearcher` runs two stages. Discovery finds candidates; confirmation
decides which candidates are kept. Discovery alone proves nothing.

```
STAGE 1 - DISCOVERY (any one source can answer)

For each research topic:

  1. Crossref / OpenAlex / Semantic Scholar   (parallel for academic topics)
         |
         | (if nothing found)
         v
  2. Serper / Gemini Grounded Search  ──> URL-based results, usually no DOI
         |                                 (Serper preferred if USE_SERPER=true)
         | (if all lookups fail)
         v
  3. LLM Fallback  ──> Gemini asserts a citation from training data.
                       DISABLED BY DEFAULT. Nothing external checks it, so
                       anything it produces is tagged `llm_unverified`.


STAGE 2 - CONFIRMATION (default: 2 of 3 required)

For each candidate carrying a DOI:

  Look the DOI up directly in Crossref, OpenAlex and Semantic Scholar
         |
         v
  >= min_confirming_sources hold it  ──> keep, `multi_source_confirmed`
  exactly one holds it               ──> DROP, `single_source`
  no DOI at all (web result)         ──> DROP unless
                                         allow_unconfirmed_web_sources=True,
                                         tagged `web_search_unconfirmed`
```

Confirmation proves the DOI is registered and indexed in that many databases.
It does not prove the work supports the claim it is cited for; that is
`CitationClaimVerifier` in Phase 2.5. Note also that OpenAlex and Semantic
Scholar both ingest Crossref metadata, so the three are not fully independent.

Smart routing (`QueryRouter`) classifies each query to pick the best starting API:
- Known-item queries (DOI, exact title) -> Crossref first
- Broad topic queries -> Semantic Scholar first
- Recent/niche topics -> Gemini Grounded / Serper first

---

## File Locations

| Component | Path |
|-----------|------|
| Pipeline orchestrator | `engine/draft_generator.py` |
| Agent runner | `engine/utils/agent_runner.py` |
| Citation research | `engine/utils/api_citations/orchestrator.py` |
| Citation compiler | `engine/utils/citation_compiler.py` |
| Citation database | `engine/utils/citation_database.py` |
| Deep research planner | `engine/utils/deep_research.py` |
| Abstract generator | `engine/utils/abstract_generator.py` |
| All prompt files | `engine/prompts/` |
| Workflow guide (manual) | `engine/prompts/00_WORKFLOW.md` |
| Concurrency config | `engine/concurrency/concurrency_config.py` |

---

## Word Count Targets by Academic Level

Configured in `get_word_count_targets()` (`draft_generator.py:590`):

| Level | Total Words | Min Citations | Deep Research Sources | Chapters |
|-------|-------------|---------------|-----------------------|----------|
| Research Paper | 3,000-5,000 | 10 | 20 | 3-4 |
| Bachelor | 10,000-15,000 | 15 | 40 | 5-7 |
| Master | 25,000-30,000 | 25 | 50 | 7-10 |
| PhD | 50,000-80,000 | 50 | 100 | 10-15 |
