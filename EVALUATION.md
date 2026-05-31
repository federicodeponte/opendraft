# OpenDraft Evaluation Plan

> Reproducible benchmarks for measuring citation accuracy, source coverage, and draft quality across the OpenDraft agent pipeline.

## Overview

OpenDraft is an open-source research drafting engine with 19 specialized agents. This document defines the evaluation methodology and planned benchmarks for measuring its reliability as open-source infrastructure.

## Current Metrics (Baseline)

| Metric | Current Value | Target |
|--------|--------------|--------|
| Citation duplication rate | ~0% (post-dedup fix) | <5% |
| Verified citation rate | ~85% | >90% |
| Hallucinated source rate | ~10-15% | <5% |
| Average draft word count | 7,000-9,500 | Consistent |
| Average unique citations | 15-22 | 18-25 |
| Generation time (30-40 pages) | ~4-6 min | <5 min |

## Planned Evaluations

### 1. Citation Accuracy Suite

**Goal:** Measure whether every cited source exists and matches the claimed metadata.

**Method:**
- Generate 20 drafts across diverse topics (CS, medicine, economics, social science)
- For each citation, verify DOI exists in CrossRef, OpenAlex, Semantic Scholar, or arXiv
- Check title/author/year match between draft claim and database record
- Score: `% correctly verified / total citations`

**Automation:**
- Script: `scripts/eval_citation_accuracy.py`
- CI: Run on every release against a fixed topic set
- Output: JSON report + SARIF-compatible format

### 2. Source Coverage Benchmark

**Goal:** Measure whether the research phase finds sufficient relevant literature.

**Method:**
- Select 10 topics with known "canonical" paper sets (e.g., "Transformer architecture" → Vaswani et al.)
- Run research phase only, collect all retrieved sources
- Check if canonical papers appear in retrieved set
- Score: `recall@k` for k=10, 20, 50

### 3. Hallucination Detection

**Goal:** Identify claims in the draft that lack supporting sources.

**Method:**
- Extract all factual claims from generated drafts
- For each claim, check if any cited source actually supports it
- Manual annotation on a 100-claim sample
- Score: `% unsupported claims`

### 4. Regression Tests for Agent Pipeline

**Goal:** Ensure code changes don't degrade output quality.

**Method:**
- Fixed "golden topic" set: 5 topics that exercise each agent
- Generate drafts before/after each PR
- Compare: word count, citation count, verified citation rate, structure quality
- Fail CI if any metric degrades >10%

### 5. Cross-Model Consistency

**Goal:** Compare output quality across supported LLM providers.

**Providers tested:**
- Google Gemini 3 Flash
- Google Gemini 3 Pro
- OpenAI GPT-5.5
- Anthropic Claude Sonnet 4.5

**Metrics:**
- Citation verification rate
- Draft coherence (human eval on 5-point scale)
- Cost per draft
- Generation time

## Running Evaluations

```bash
# Run full evaluation suite
python scripts/eval_citation_accuracy.py --topics data/eval_topics.json --output reports/

# Run regression test against golden topics
python scripts/eval_regression.py --baseline reports/baseline.json

# Generate comparison report across models
python scripts/eval_cross_model.py --providers gemini,openai,anthropic
```

## Benchmark Topic Dataset

To support reproducible evaluation, OpenDraft includes a benchmark dataset containing 20 research topics across multiple academic domains.

### Covered Domains

- Computer Science
- Medicine
- Economics
- Social Science
- Physics
- Biology

### Dataset Structure

Each topic includes:

- Topic name
- Academic domain
- Canonical research papers associated with the topic

The canonical papers act as reference sources for evaluating:

- Citation accuracy
- Source coverage
- Retrieval quality
- Cross-model consistency
- Regression testing

### Dataset Location

```text
data/eval_topics.json
```

### Evaluation Criteria

The benchmark dataset is intended to provide a consistent evaluation baseline across different OpenDraft evaluation suites.

Evaluations using this dataset may measure:

| Metric | Description |
|----------|-------------|
| Citation Verification Rate | Percentage of citations that can be successfully verified against trusted databases |
| Source Coverage | Whether canonical papers are retrieved during the research phase |
| Retrieval Recall | Number of expected sources discovered within the retrieved set |
| Cross-Model Consistency | Differences in retrieval and citation quality across LLM providers |
| Regression Stability | Changes in evaluation metrics across releases and code changes |

The dataset should remain stable over time so benchmark results can be compared across versions of OpenDraft.


## Contributing to Evals
```md

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup. Evaluation PRs are welcome:

- Add new topics to `data/eval_topics.json`
- Improve verification scripts
- Add new metrics (readability, structure quality, etc.)

Label eval-related issues: `evals`, `citation-validation`, `benchmarks`
