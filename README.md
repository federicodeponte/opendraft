<h1 align="center">OpenDraft — AI Research Draft Generator</h1>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Open%20Source-100%25-brightgreen.svg" alt="Open Source">
  <img src="https://img.shields.io/github/stars/federicodeponte/opendraft?style=social" alt="GitHub stars">
</p>

<p align="center">
  <b>Free, open-source AI engine that generates source-grounded research drafts with <em>verified</em> citations.</b><br>
  19 specialized agents · CrossRef, OpenAlex, Semantic Scholar, arXiv · PDF/DOCX/LaTeX export
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Human%20Review-Required-orange.svg" alt="Human Review Required">
  <img src="https://img.shields.io/badge/Citations-Verified-blue.svg" alt="Verified Citations">
</p>

<p align="center">
  <a href="https://openpaper.dev"><strong>🚀 Try the free hosted version on OpenPaper.dev →</strong></a><br>
  <sub>3 free papers per day · No credit card required</sub>
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
| **Sources** | CrossRef, OpenAlex, Semantic Scholar (200M+), arXiv |
| **Languages** | 57+ languages including English, Spanish, German, French, Chinese, Japanese |
| **Export** | PDF, Microsoft Word (.docx), LaTeX |
| **Cost** | **Free** (self-hosted, MIT license) or **free tier** at [OpenPaper.dev](https://openpaper.dev) (3 papers/day) |
| **Typical output** | 5–80+ pages, 10k–20k+ words, 30–50+ verified citations |
| **Time to draft** | 10–20 minutes |
| **API cost per draft** | ~$0.35 (Gemini Flash) to ~$3.00 (Claude Opus) |

---

## Table of Contents

- [At a Glance](#at-a-glance)
- [What is OpenDraft?](#what-is-opendraft)
- [Try it free — no installation](#try-it-free--no-installation)
- [Why OpenDraft Exists](#why-opendraft-exists)
- [OpenDraft for Open Source Maintainers](#opendraft-for-open-source-maintainers)
- [What OpenDraft is NOT](#what-opendraft-is-not)
- [OpenDraft vs ChatGPT](#opendraft-vs-chatgpt)
- [How It Works](#how-it-works)
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

Unlike general-purpose chatbots such as ChatGPT, OpenDraft does not hallucinate citations. Every source is checked against CrossRef, OpenAlex, Semantic Scholar, and arXiv before being included in the bibliography.

- **OpenDraft is** a command-line tool and Python library for drafting academic papers.
- **OpenPaper is** the free hosted SaaS version of OpenDraft (3 papers per day, no credit card required).
- **Best for:** Researchers drafting literature reviews, journal submissions, structured research papers, and thesis first drafts.
- **Price:** 100% free and open source (MIT license).
- **Setup time:** 10 minutes for local installation.
- **SaaS version:** [OpenPaper.dev](https://openpaper.dev) — run it in your browser, 3 free papers/day.

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

Not ready to self-host? **OpenPaper.dev** is the free, hosted version of OpenDraft:

- ✅ **3 research papers per day** on the free plan
- ✅ Searches CrossRef, OpenAlex, Semantic Scholar, and arXiv
- ✅ **PDF + DOCX export**
- ✅ No credit card required
- ✅ Upgrade to Pro ($9/mo) or Max ($25/mo) for more daily credits

<p align="center">
  <a href="https://openpaper.dev"><img src="https://img.shields.io/badge/Try%20Free%20on-OpenPaper.dev-6366f1?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Try OpenPaper.dev for free"></a>
</p>

---

## Why OpenDraft Exists

We built OpenDraft after repeatedly encountering AI writing tools that produced confident-sounding research drafts with hallucinated or unverifiable citations.

Academic research requires trust, sources, and accountability.

OpenDraft explores a different approach: instead of a single general-purpose model, it uses multiple specialized agents, each responsible for a specific step in the research drafting process, grounded in real academic literature.

We open-sourced OpenDraft so researchers can inspect, critique, and improve how these systems actually work.

### What Problem Does OpenDraft Solve?

1. **Hallucinated citations** — ChatGPT and similar LLMs invent citations 30–50% of the time. OpenDraft verifies every source.
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
| Does it search real papers? | No | **Yes (CrossRef, OpenAlex, Semantic Scholar, arXiv)** |
| Academic structure? | Generic | **Chapters & sections** |
| Export to PDF/Word? | No | **Yes** |
| Free? | Limited | **100% free (self-host)** |
| Open source? | No | **Yes (MIT license)** |
| Hosted SaaS? | ChatGPT Plus $20/mo | **OpenPaper.dev — 3 free/day** |

**Bottom line:** If you need an AI for academic writing with real citations, OpenDraft is a free, open-source alternative to ChatGPT.

---

## How It Works

OpenDraft uses **19 specialized AI agents** that work like a research team:

```
📚 RESEARCH PHASE    → Finds relevant papers from CrossRef, OpenAlex, Semantic Scholar, arXiv
🏗️ STRUCTURE PHASE   → Creates research outline with chapters
✍️ WRITING PHASE     → Drafts each section with academic tone
🔍 CITATION PHASE    → Verifies every source exists (CrossRef, arXiv)
✨ POLISH PHASE      → Refines language and formatting
📄 EXPORT PHASE      → Generates PDF, Word, or LaTeX
```

**Result:** A complete research draft in 10-20 minutes instead of weeks.

---

## Features

### AI That Doesn't Make Up Citations
Every citation is verified against CrossRef, OpenAlex, Semantic Scholar, and arXiv. If a paper doesn't exist, it's not included.

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

📄 **[Download Sample PDF](https://openpaper.dev/examples/genai-software-engineering)** — view a live example with verified citations

📝 **Try the free hosted version:** [OpenPaper.dev](https://openpaper.dev)

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
**Yes.** OpenDraft is 100% free and open source under the MIT license. You can self-host it with your own API keys (a typical draft costs ~$0.35–$3 in API fees). There is also a free hosted version at [OpenPaper.dev](https://openpaper.dev) with 3 papers per day and no credit card required.

### Is OpenDraft better than ChatGPT for writing a thesis?
**Yes, for research drafts.** ChatGPT frequently hallucinates citations and cannot produce documents longer than a few thousand words. OpenDraft generates 20,000+ word research drafts with every citation verified against real academic databases.

### Can OpenDraft write a full PhD dissertation?
**OpenDraft can generate a complete first draft** of a PhD dissertation (100+ pages) in 10–20 minutes. However, it is a drafting assistant, not an autonomous author. You must review, edit, and add your own analysis before submission.

### Does OpenDraft make up citations?
**No.** OpenDraft verifies every citation against CrossRef, OpenAlex, Semantic Scholar, and arXiv. If a paper does not exist, it is not included in the bibliography.

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

You can also use the free hosted version at **[OpenPaper.dev](https://openpaper.dev)** — 3 papers per day, no credit card required.

### Is this better than ChatGPT for academic writing?

**For research drafts, yes.** ChatGPT often hallucinates citations. OpenDraft verifies every citation against CrossRef, OpenAlex, Semantic Scholar, and arXiv.

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
| **OpenDraft** | Free | ✅ Yes | ✅ Yes | ✅ Yes | ✅ OpenPaper.dev (3/day) |
| ChatGPT Plus | $20/mo | ❌ No | ❌ No | ❌ No | ❌ No |
| Jasper | $49/mo | ❌ No | ❌ No | ✅ Yes | ❌ No |
| Jenni AI | $20/mo | ❌ No | ⚠️ Partial | ✅ Yes | ❌ No |

**OpenDraft is a free, open-source research draft generator with verified citations.**

---

## Tech Stack

- **Engine:** Python 3.10+, multi-agent orchestration
- **Models:** Google Gemini 3, Anthropic Claude Sonnet 4.5 / Opus 4.5, OpenAI GPT-5.5 / GPT-5
- **Citations:** CrossRef API, OpenAlex API, Semantic Scholar API, arXiv API
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

- 🌐 **Website:** [OpenPaper.dev](https://openpaper.dev)
- 🚀 **Free Hosted Version:** [OpenPaper.dev](https://openpaper.dev)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/federicodeponte/opendraft/discussions)
- 🐛 **Issues:** [Report Bug](https://github.com/federicodeponte/opendraft/issues)
- 🗒️ **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- 📜 **License:** [MIT](LICENSE)

---

## Summary

**OpenDraft** is a free, open-source Python engine for generating academic research drafts. It uses 19 specialized AI agents to create drafts with citations verified against real databases (CrossRef, OpenAlex, Semantic Scholar, arXiv).

**Keywords:** AI research draft generator, open source academic writing, ChatGPT alternative, multi-agent AI, verified citations, Python research engine, literature review generator, OpenPaper, source-grounded citations, academic workflow automation

---

<p align="center">
  <b>If OpenDraft helps your research, please star the repo!</b><br><br>
  <a href="https://github.com/federicodeponte/opendraft">⭐ Star on GitHub</a>
</p>
