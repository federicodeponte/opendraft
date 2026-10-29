# OpenDraft tools beyond full drafts

These commands ship with the `opendraft` CLI. Back to the [README](../README.md).

## TL;DR and Digest Tools
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
