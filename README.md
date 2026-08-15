<h1 align="center">OpenDraft — AI Research Draft Generator</h1>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Open%20Source-100%25-brightgreen.svg" alt="Open Source">
  <img src="https://img.shields.io/github/stars/federicodeponte/opendraft?style=social" alt="GitHub stars">
</p>

<p align="center">
  <b>Free, open-source autonomous research engine: auto research from a prompt to a source-grounded draft with <em>verified</em> citations.</b><br>
  19 specialized agents · CrossRef, OpenAlex, Semantic Scholar · PDF/DOCX/LaTeX export
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Human%20Review-Required-orange.svg" alt="Human Review Required">
  <img src="https://img.shields.io/badge/Citations-Verified-blue.svg" alt="Verified Citations">
</p>

<p align="center">
  <b>Don't want to manage API keys and infra?</b><br>
  <a href="https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft"><strong>Use the hosted version → OpenPaper.dev</strong></a><br>
  <sub>Free to generate &amp; read with verified citations · No API keys · No setup · No credit card</sub>
</p>

<p align="center">
  <img src="assets/demo.gif" width="900" alt="OpenDraft generating a source-grounded research paper from a single prompt, with verified citations and a typeset PDF">
</p>

---

## At a Glance

| | |
|:---|:---|
| **What it is** | Open-source Python engine for AI-generated research drafts with verified citations |
| **Best for** | Literature reviews, research papers, thesis drafts, reproducible research workflows |
| **Agents** | 19 specialized AI agents (research, structure, writing, citation, polish, export) |
| **Sources** | CrossRef, OpenAlex, Semantic Scholar (200M+) |
| **Languages** | 57+ languages including English, Spanish, German, French, Chinese, Japanese |
| **Export** | PDF, Microsoft Word (.docx), LaTeX |
| **Cost** | **Free** (self-hosted, MIT license) or **free to generate &amp; read** at [OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft) (pay only to export) |
| **Typical output** | 5–80+ pages, 10k–20k+ words, 30–50+ citations ([measured before multi-source confirmation was made the default](#citation-verification)) |
| **Time to draft** | 10–20 minutes |
| **API cost per draft** | ~$0.35 (Gemini Flash) to ~$3.00 (Claude Opus) |

---

## Table of Contents

- [At a Glance](#at-a-glance)
- [What is OpenDraft?](#what-is-opendraft)
- [Try it free — no installation](#try-it-free--no-installation)
- [Self-hosted vs Hosted](#self-hosted-opendraft-vs-hosted-openpaper)
- [Why OpenDraft Exists](#why-opendraft-exists)
- [OpenDraft for Open Source Maintainers](#opendraft-for-open-source-maintainers)
- [What OpenDraft is NOT](#what-opendraft-is-not)
- [OpenDraft vs ChatGPT](#opendraft-vs-chatgpt)
- [How It Works](#how-it-works)
- [Citation verification](#citation-verification)
- [Features](#features)
- [Quick Start](#quick-start)
- [Which AI Model Should I Use?](#which-ai-model-should-i-use)
- [Example Output](#example-output)
- [People Also Ask](#people-also-ask)
- [FAQ](#faq)
- [Alternatives Comparison](#alternatives-comparison-2025)
- [Tech Stack](#tech-stack)
- [Contributing](#contributing)
- [Links](#links)

---

## What is OpenDraft?

**OpenDraft is an open-source Python engine that generates source-grounded research drafts using 19 specialized AI agents.** It is designed for academic researchers who need long-form documents (10,000–20,000+ words) with citations verified against real databases.

Unlike general-purpose chatbots such as ChatGPT, OpenDraft does not invent its citations. By default a source is only included once its DOI has been independently found in at least **two** of CrossRef, OpenAlex and Semantic Scholar, and every citation records which databases confirmed it. See [Citation verification](#citation-verification) for exactly what that does and does not establish.

- **OpenDraft is** a command-line tool and Python library for drafting academic papers.
- **OpenPaper is** the hosted SaaS version of OpenDraft — generate and read fully-cited papers for free (no credit card); pay only to export the finished file.
- **Best for:** Researchers drafting literature reviews, journal submissions, structured research papers, and thesis first drafts.
- **Price:** 100% free and open source (MIT license).
- **Setup time:** 10 minutes for local installation.
- **SaaS version:** [OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft) — run it in your browser. Free to generate and read; pay only to export.

---

## OpenDraft for Open Source Maintainers

OpenDraft is not just a drafting tool — it is a **reproducible research-agent pipeline** that open-source maintainers can extend, audit, and improve.

We use Codex and OpenAI models to maintain OpenDraft itself:

- **Automated PR review** — Codex reviews contributor changes for agent logic, prompt quality, and citation handling
- **Regression test generation** — AI-assisted tests for citation accuracy, source coverage, and draft coherence
- **Issue triage** — Codex suggests labels, duplicates, and fixes for bug reports
- **Release workflow automation** — Automated changelogs, version bumps, and eval runs before each release
- **Contributor templates** — Codex-assisted onboarding for adding new agents, validators, and export formats

See [EVALUATION.md](EVALUATION.md) for the benchmark plan and [CONTRIBUTING.md](CONTRIBUTING.md) for maintainer guidelines.

---

## Try it free — no installation

Not ready to self-host? **OpenPaper.dev** is the hosted version of OpenDraft — free to generate and read, pay only to export:

- ✅ **Generate & read research papers with verified citations — free**
- ✅ Searches CrossRef, OpenAlex and Semantic Scholar, and requires 2+ of them to confirm each citation
- ✅ **Read-only share links** to send your draft
- ✅ No API keys, no setup, no credit card to start
- ✅ Export the finished file (**PDF / Word / LaTeX**) on a paid plan

<p align="center">
  <a href="https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft"><img src="https://img.shields.io/badge/Try%20Free%20on-OpenPaper.dev-6366f1?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Try OpenPaper.dev for free"></a>
</p>

### Self-hosted (OpenDraft) vs Hosted (OpenPaper)

Same engine, two ways to run it. Self-host for full control, or use the hosted version to skip the setup entirely.

| | **Self-hosted (OpenDraft)** | **Hosted ([OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft))** |
|---|---|---|
| **Setup** | Clone, install Python deps, configure `.env` (~10 min) | None — open the site and start writing |
| **API keys** | You bring your own (Gemini / OpenAI / Anthropic) | Included — nothing to manage |
| **Infra** | You run it locally or on your own server | Fully hosted in your browser |
| **Sources** | CrossRef, OpenAlex, Semantic Scholar | CrossRef, OpenAlex, Semantic Scholar |
| **Export** | PDF, Word (.docx), LaTeX | PDF, Word (.docx), LaTeX |
| **Support** | Community (GitHub issues) | Maintained service, email support |
| **Price** | Free (MIT) + your own API costs (~$0.35–$3 per draft) | Free to generate & read with verified citations · pay only to export (PDF/Word/LaTeX) |
| **Best for** | Developers, tinkerers, custom pipelines, full control | Researchers who just want the draft, no setup |

<p align="center">
  <b>Just want the draft without the setup?</b>
  <a href="https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft"><strong>Start free on OpenPaper.dev →</strong></a>
</p>

---

## Why OpenDraft Exists

We built OpenDraft after repeatedly encountering AI writing tools that produced confident-sounding research drafts with hallucinated or unverifiable citations.

Academic research requires trust, sources, and accountability.

OpenDraft explores a different approach: instead of a single general-purpose model, it uses multiple specialized agents, each responsible for a specific step in the research drafting process, grounded in real academic literature.

We open-sourced OpenDraft so researchers can inspect, critique, and improve how these systems actually work.

### What Problem Does OpenDraft Solve?

1. **Hallucinated citations** — ChatGPT and similar LLMs invent citations 30–50% of the time. OpenDraft confirms each source's DOI against multiple scholarly databases and drops the ones it cannot confirm.
2. **Length limits** — Most AI tools cannot produce documents longer than a few thousand words. OpenDraft generates 20,000+ word research drafts.
3. **Generic structure** — ChatGPT outputs lack proper academic chapter/section hierarchy. OpenDraft builds structured research outlines.
4. **No export options** — ChatGPT cannot export to PDF or Word with academic formatting. OpenDraft exports to PDF, DOCX, and LaTeX.
5. **Closed source** — Most academic AI tools are black boxes. OpenDraft is fully open source under the MIT license.

### Who Is OpenDraft For?

- **Researchers** preparing literature reviews, journal submissions, or structured first drafts.
- **Open-source maintainers** building tools on top of a reproducible research-drafting pipeline.
- **Graduate students** working on a master's thesis or PhD dissertation.
- **Academics** who want to verify that every citation in their AI-assisted draft links to a real paper.
- **Developers** extending the agent pipeline for custom research workflows, citation validators, and export formats.

---

## What OpenDraft is NOT

OpenDraft is intentionally **not** designed for:

- One-click generation of final papers
- Cheating on assignments
- Inventing citations or bypassing peer review
- Replacing human researchers

It is a research assistance and drafting tool, not an autonomous author.

---

## OpenDraft vs ChatGPT

| Question | ChatGPT | OpenDraft |
|----------|---------|-----------|
| Does it hallucinate citations? | Yes (often) | **Verified against real databases** |
| Can it write 20,000+ words? | No (hits limits) | **Yes** |
| Does it search real papers? | No | **Yes (CrossRef, OpenAlex, Semantic Scholar)** |
| Academic structure? | Generic | **Chapters & sections** |
| Export to PDF/Word? | No | **Yes** |
| Free? | Limited | **100% free (self-host)** |
| Open source? | No | **Yes (MIT license)** |
| Hosted SaaS? | ChatGPT Plus $20/mo | **OpenPaper.dev — free to generate & read** |

**Bottom line:** If you need an AI for academic writing with real citations, OpenDraft is a free, open-source alternative to ChatGPT.

---

## How It Works

OpenDraft uses **19 specialized AI agents** that work like a research team:

```
📚 RESEARCH PHASE    → Finds candidate papers via CrossRef, OpenAlex, Semantic Scholar, web search
🏗️ STRUCTURE PHASE   → Creates research outline with chapters
✍️ WRITING PHASE     → Drafts each section with academic tone
🔍 CITATION PHASE    → Confirms each DOI in 2+ of CrossRef/OpenAlex/Semantic Scholar,
                       then checks each source is on-topic for the paper
✨ POLISH PHASE      → Refines language and formatting
📄 EXPORT PHASE      → Generates PDF, Word, or LaTeX
```

**Result:** A complete research draft in 10-20 minutes instead of weeks.

---

## Citation verification

Citations are checked in two independent ways. They answer different questions
and neither substitutes for the other.

### 1. Does the work exist? (multi-source confirmation)

Discovery may find a candidate through any source. Confirmation then looks the
candidate's **DOI** up directly in each scholarly database and counts how many
hold a record for it.

**By default a citation is kept only if at least 2 of {CrossRef, OpenAlex,
Semantic Scholar} hold its DOI.** A single-source result is dropped and the drop
is logged. Accepting single-source results is an explicit opt-out
(`require_multi_source=False`), not the default.

To be exact about what "2 databases hold it" means: one of the two may be the
database that returned the candidate in the first place, which is taken at its
word rather than re-queried. The others are looked up directly by DOI. The
engine tracks this distinction internally (`confirming_sources` versus
`independently_confirmed_by`) and `verification_notes` on each citation spells
out which database found it and which ones confirmed it.

| Setting | Default | Effect |
|:---|:---|:---|
| `require_multi_source` | `True` | Drop citations fewer than `min_confirming_sources` databases hold |
| `min_confirming_sources` | `2` | How many of the three must hold the DOI |
| `allow_unconfirmed_web_sources` | `False` | Keep DOI-less web-search results (kept tagged if enabled) |
| `enable_llm_fallback` | `False` | Let the LLM assert a citation when every lookup fails |

Every citation in `bibliography.json` carries its provenance:

| `verification_status` | Meaning |
|:---|:---|
| `multi_source_confirmed` | The DOI is held by `min_confirming_sources` or more databases, listed in `verification_sources` |
| `single_source` | Exactly one database holds the DOI. Dropped under the default settings |
| `unconfirmed` | The DOI carries no record in **any** scholarly database. Dropped under the default settings |
| `web_search_unconfirmed` | No DOI, so no scholarly database could be queried. Zero databases confirmed it |
| `llm_unverified` | Asserted by the LLM with no external lookup of any kind. Nothing checked that it exists |
| `not_checked` | Confirmation was disabled for this run |

`verification_sources` is written out even when it is empty, precisely so an
unconfirmed citation can never serialize to look like a confirmed one.

**What this establishes, and what it does not.** A confirmation means the DOI is
registered and indexed in that many databases. It does not mean the work
supports the sentence it is attached to, and it is not three separately sourced
attestations of the same facts: OpenAlex and Semantic Scholar both ingest
Crossref metadata, so the three are not fully independent of one another.

arXiv is not queried as a citation database. `arxiv.org` can appear as a
web-search result and Semantic Scholar exposes arXiv IDs, but there is no arXiv
API client in this engine.

### 2. Does the source support the claim? (claim-level verification)

A real, correctly cited, multi-source-confirmed paper can still be attached to a
claim it says nothing about. Existence checking cannot detect that, so
`CitationClaimVerifier` judges each source against the claim it is cited for and
returns `RELEVANT`, `IRRELEVANT` or `UNCERTAIN`.

In the citation phase this runs against the **paper topic**, because that phase
executes before any draft text exists and the topic is the only claim available
at that point. Sentence-level checking needs a draft and is available through
`run_citation_claim_verification()`.

Reports are written to the research folder as
`citation_claim_verification.md` and `.json`. A citation judged `IRRELEVANT` is
removed only above a confidence floor (`CLAIM_VERIFICATION_MIN_CONFIDENCE`,
default `0.7`), and the engine refuses to empty the bibliography outright.

| Env var | Default | Effect |
|:---|:---|:---|
| `ENABLE_CLAIM_VERIFICATION` | `true` | Run claim-level verification at all |
| `CLAIM_VERIFICATION_DROP_IRRELEVANT` | `true` | Remove irrelevant citations rather than only reporting them |
| `CLAIM_VERIFICATION_MIN_CONFIDENCE` | `0.7` | Confidence needed before a removal happens |

**These verdicts are language-model judgements, not proofs.** The judge reads a
citation's title and abstract, not the paper's full text. `UNCERTAIN` means
unchecked, not passing. Treat the output as evidence for a human reviewer.

### Effect on how many citations you get

Requiring two independent confirmations necessarily lets fewer candidates
through than accepting the first responder did. That is the intended trade:
fewer citations, each one confirmed by more than one database.

Citation counts quoted elsewhere in this README and in `EVALUATION.md` were
measured before multi-source confirmation became the default and have **not**
been re-measured since. Treat them as historical. If you need the old
behaviour, set `require_multi_source=False` — and note that citations then
carry `verification_status: not_checked` rather than being labelled confirmed.

### Human review is still required

Neither check removes the need to read the draft. See
[What OpenDraft is NOT](#what-opendraft-is-not).

---

## Features

### AI That Doesn't Make Up Citations
By default a citation is kept only if its DOI is independently found in at least two of CrossRef, OpenAlex and Semantic Scholar. A source only one database knows about is dropped, not quietly accepted. Every citation in `bibliography.json` carries the list of databases that confirmed it, so an unconfirmed source can never look like a confirmed one. See [Citation verification](#citation-verification).

### Write Any Type of Academic Paper
- Research papers (5-15 pages)
- Literature reviews (20-40 pages)
- Thesis drafts (30-80 pages)
- Structured reports (10-100+ pages)

### 57+ Languages Supported
English, Spanish, German, French, Chinese, Japanese, Korean, Arabic, Portuguese, Italian, Dutch, Polish, Russian, and 40+ more.

### Export to Any Format
- **PDF** - LaTeX-quality formatting
- **Microsoft Word** (.docx)
- **LaTeX source** - for journals

### 100% Free and Open Source
MIT license. Self-host with your own API keys. No subscriptions, no paywalls, no limits.

### TL;DR and Digest Tools
OpenDraft includes two standalone tools for quickly understanding any research paper:

#### TL;DR: 5-Bullet Summary

Generate a concise 5-bullet summary of any paper in seconds:

```bash
# As a subcommand
opendraft tldr paper.pdf

# Or standalone
opendraft-tldr paper.pdf

# Output to file
opendraft tldr paper.pdf -o summary.md
```

Each bullet follows academic structure: thesis, key finding, method, implication, limitation.

#### Digest: 60-Second Audio Briefing

Generate a podcast-style audio summary you can listen to:

```bash
# Generate script + audio
opendraft digest paper.pdf

# Choose a different voice (rachel, adam, josh, elli, bella)
opendraft digest paper.pdf --voice adam

# Script only (no audio)
opendraft digest paper.pdf --no-audio

# Specify output directory
opendraft digest paper.pdf -o output/
```

**Requirements:**
- Digest audio requires an [ElevenLabs API key](https://elevenlabs.io/) set as `ELEVENLABS_API_KEY`
- PDF reading requires the optional `pdf` extra: `pip install opendraft[pdf]`

Both tools work with any academic paper (PDF, Markdown, or plain text), not just OpenDraft-generated documents.

---

## Data Fetching

Fetch research data from major statistical APIs directly into your workflow:

```bash
# Search for indicators
opendraft data search GDP

# Fetch World Bank data
opendraft data worldbank NY.GDP.MKTP.CD --countries USA;DEU --start 2020 --end 2023

# Fetch EU statistics (Eurostat)
opendraft data eurostat nama_10_gdp

# Fetch Our World in Data datasets
opendraft data owid covid-19
```

**Supported providers:**
- **World Bank** - Development indicators (GDP, population, education, health)
- **Eurostat** - European Union statistics
- **Our World in Data** - Open research datasets

Data is saved as CSV files for use in your research.

---

## Draft Revision

Revise existing drafts with AI assistance:

```bash
# Revise a draft with natural language instructions
opendraft revise ./output "Make the introduction longer and add more context"

# The revised draft is saved as draft_v2.md (with PDF/DOCX exports)
```

Features:
- Auto-detects draft files in output folders
- Preserves all citations during revision
- Automatic versioning (v2, v3, v4...)
- Quality scoring before/after
- PDF and DOCX export of revised version

---

## Research Expose Mode

Generate a quick research overview instead of a full draft:

```bash
opendraft "Neural Networks in Healthcare" --expose
```

This produces a research expose with:
- **Research Sources Overview** - Number of sources, publication years, key journals
- **Key Research Teams** - Major authors and research groups in the field
- **Structured Outline** - Chapter/section structure for a full paper
- **Complete Bibliography** - All sources with DOIs and journal info
- **Next Steps** - Guidance for developing into a full draft

Use expose mode when you want to:
- Quickly scope a research topic
- Validate there's enough literature
- Get a structured starting point
- Review sources before committing to a full draft

Expose mode is ~3x faster than full draft generation.

---

## TL;DR Mode

Generate a 5-bullet summary of any academic paper in seconds:

```bash
# Summarize a PDF
opendraft tldr paper.pdf

# Summarize a markdown file
opendraft tldr draft.md

# Save to file
opendraft tldr paper.pdf --output summary.md
```

Output:
```
📄 TL;DR: paper.pdf

• Main finding: Neural networks improve diagnostic accuracy by 23%
• Method: Retrospective analysis of 50,000 patient records
• Key limitation: Single-center study, needs external validation
• Implication: AI-assisted diagnosis could reduce misdiagnosis rates
• Future work: Multi-center trials planned for 2025
```

Works with any PDF, Markdown, or text file.

---

## Audio Digest

Generate a 60-second audio summary using ElevenLabs TTS:

```bash
# Generate audio digest (requires ElevenLabs API key)
opendraft digest paper.pdf

# Choose a voice
opendraft digest paper.pdf --voice adam

# Available voices: rachel (default), adam, josh, elli, bella
```

Output: `paper_digest.mp3` - a professional narration summarizing the key points.

**Setup:** Set `ELEVENLABS_API_KEY` in your environment or `.env` file.

---

## Quick Start

### Prerequisites
- Python 3.10+
- A free [Gemini API key](https://makersuite.google.com/app/apikey)

### 1. Clone & Install

```bash
git clone https://github.com/federicodeponte/opendraft.git
cd opendraft
pip install -r requirements.txt
```

### 2. Configure

Create a `.env` file with your API key:
```bash
GOOGLE_API_KEY=your-gemini-api-key
```

### 3. Generate a Draft

```python
from engine.draft_generator import DraftGenerator

generator = DraftGenerator()
draft = generator.generate(
    topic="The Impact of AI on Academic Research",
    paper_type="master",  # research_paper, bachelor, master, phd
    language="en"
)

# Export to different formats
draft.to_pdf("thesis.pdf")
draft.to_docx("thesis.docx")
draft.to_latex("thesis.tex")
```

See `engine/README.md` for detailed API documentation.

---

## Which AI Model Should I Use?

| Model | Speed | Quality | Cost/Draft | Best For |
|-------|-------|---------|------------|----------|
| **Gemini 3 Flash** | ⚡ Fast | Good | ~$0.35 | Most users |
| Gemini 3 Pro | Medium | Excellent | ~$1.40 | Important papers |
| GPT-5.2 | Medium | Excellent | ~$1.60 | OpenAI users |
| Claude Sonnet 4.5 | Medium | Excellent | ~$1.80 | Nuanced writing |
| Claude Opus 4.5 | Slow | Best | ~$3.00 | Maximum quality |

**Recommendation:** Start with Gemini 3 Flash for most use cases. Use Gemini 3 Pro or Claude Sonnet 4.5 for important papers.

---

## Example Output

See what OpenDraft produces:

📄 **[Download Sample PDF](https://openpaper.dev/examples/genai-software-engineering?utm_source=github&utm_medium=readme&utm_campaign=opendraft)** — view a live example with verified citations

📝 **Try the free hosted version:** [OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft)

Generated in ~15 minutes with verified citations from real academic papers.

---

## Project Structure

```
opendraft/
├── engine/
│   ├── draft_generator.py    # Main 19-agent pipeline
│   ├── config.py             # Model & API settings
│   ├── prompts/              # Agent instruction templates
│   ├── utils/                # Citations, export, helpers
│   └── opendraft/            # Core agent modules
├── examples/                 # Sample research outputs
├── requirements.txt          # Python dependencies
└── README.md
```

---

## People Also Ask

### Is OpenDraft free?
**Yes.** OpenDraft is 100% free and open source under the MIT license. You can self-host it with your own API keys (a typical draft costs ~$0.35–$3 in API fees). There is also a hosted version at [OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft) where generating and reading fully-cited papers is free (no credit card); you pay only to export the finished file (PDF, Word, or LaTeX).

### Is OpenDraft better than ChatGPT for writing a thesis?
**Yes, for research drafts.** ChatGPT frequently hallucinates citations and cannot produce documents longer than a few thousand words. OpenDraft generates 20,000+ word research drafts with every citation verified against real academic databases.

### Can OpenDraft write a full PhD dissertation?
**OpenDraft can generate a complete first draft** of a PhD dissertation (100+ pages) in 10–20 minutes. However, it is a drafting assistant, not an autonomous author. You must review, edit, and add your own analysis before submission.

### Does OpenDraft make up citations?
**Citations are not invented, and the engine records exactly how each one was established.** By default a citation must have its DOI independently confirmed in at least two of CrossRef, OpenAlex and Semantic Scholar; single-source results are dropped. The LLM-asserted fallback is off by default and, if you switch it on, everything it produces is permanently tagged `llm_unverified`. Note what this proves: that the cited work is registered and indexed, not that it supports the sentence it is attached to. A separate claim-level check covers that, and its verdicts are LLM judgements for a human reviewer. See [Citation verification](#citation-verification).

### What is the difference between OpenDraft and OpenPaper?
**OpenDraft** is the open-source Python engine you run locally. **OpenPaper** is the hosted SaaS version that runs OpenDraft in the cloud so you can use it in your browser without installing anything.

### How long does it take to generate a thesis with OpenDraft?
**10–20 minutes** for a full master's thesis (50–80 pages). A shorter research paper takes 5–10 minutes.

### What file formats does OpenDraft export to?
**PDF, Microsoft Word (.docx), and LaTeX source.**

### Can I use OpenDraft for commercial purposes?
**Yes.** The MIT license permits commercial use, modification, and distribution without restriction.

---

## FAQ

### Is this really free?

**Yes.** OpenDraft is 100% open source under the MIT license. Self-host with your own API keys. A typical research draft costs ~$0.35-$3 depending on the model.

You can also use the hosted version at **[OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft)** — free to generate and read with verified citations (no credit card); pay only to export.

### Is this better than ChatGPT for academic writing?

**For research drafts, yes.** ChatGPT often hallucinates citations. OpenDraft confirms each citation's DOI in at least two of CrossRef, OpenAlex and Semantic Scholar before keeping it.

### Can I use this for my university thesis?

OpenDraft generates **research drafts**—starting points you should review, edit, and build upon. Always:
- Verify all sources yourself
- Add your own analysis and insights
- Check your institution's AI policy

### How is this different from other AI writing tools?

Most AI tools use a single model. OpenDraft uses **19 specialized agents**—one for research, one for citations, one for structure, etc. This produces higher quality output.

### Can I use this commercially?

**Yes.** MIT license allows commercial use. Build products, offer services, modify the code—no restrictions.

---

## Alternatives Comparison (2025)

| Tool | Price | Open Source | Verified Citations | Long Documents | Hosted Free Tier |
|------|-------|-------------|-------------------|----------------|------------------|
| **OpenDraft** | Free | ✅ Yes | ✅ Yes | ✅ Yes | ✅ OpenPaper.dev (free to generate & read) |
| ChatGPT Plus | $20/mo | ❌ No | ❌ No | ❌ No | ❌ No |
| Jasper | $49/mo | ❌ No | ❌ No | ✅ Yes | ❌ No |
| Jenni AI | $20/mo | ❌ No | ⚠️ Partial | ✅ Yes | ❌ No |

**OpenDraft is a free, open-source research draft generator with verified citations.**

---

## Tech Stack

- **Engine:** Python 3.10+, multi-agent orchestration
- **Models:** Google Gemini 3, Anthropic Claude Sonnet 4.5 / Opus 4.5, OpenAI GPT-5.5 / GPT-5
- **Citations:** CrossRef API, OpenAlex API, Semantic Scholar API
- **Export:** WeasyPrint (PDF), python-docx (Word)

---

## Contributing

Contributions welcome!

**Ideas:**
- Add new AI model support
- Improve citation accuracy
- Add export formats
- Translate prompts

Maintainer workflow docs:
- Push/auth runbook: `docs/MAINTAINER_PUSH_RUNBOOK.md`
- Automated push preflight: `scripts/push-preflight.sh`

---

## Links

- 🌐 **Website:** [OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft)
- 🚀 **Free Hosted Version:** [OpenPaper.dev](https://openpaper.dev?utm_source=github&utm_medium=readme&utm_campaign=opendraft)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/federicodeponte/opendraft/discussions)
- 🐛 **Issues:** [Report Bug](https://github.com/federicodeponte/opendraft/issues)
- 🗒️ **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- 📜 **License:** [MIT](LICENSE)

---

## Summary

**OpenDraft** is a free, open-source Python engine for generating academic research drafts. It uses 19 specialized AI agents to create drafts whose citations are confirmed against real databases (CrossRef, OpenAlex, Semantic Scholar).

**Keywords:** AI research draft generator, open source academic writing, ChatGPT alternative, multi-agent AI, verified citations, Python research engine, literature review generator, OpenPaper, source-grounded citations, academic workflow automation

---

<p align="center">
  <b>If OpenDraft helps your research, please star the repo!</b><br><br>
  <a href="https://github.com/federicodeponte/opendraft">⭐ Star on GitHub</a>
</p>
