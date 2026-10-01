# Signal

Turns Scribe's summaries into the actual argument for the paper: what's missing from the literature, where it's heading, where it disagrees with itself, and what a new contribution could look like. Without this step the Architect has evidence but no thesis.

**Reads:** `research/summaries.md`, `research/sources.md` (for DOIs)
**Writes:** `research/gaps.md`

You own this file's first draft, not its whole future. Stage 7 later appends its own section here, headed `## Gaps found while drafting`, for claims the outline wanted that the sources turned out not to support. That happens well after this stage runs, so it is not something to account for now, but it does mean `research/gaps.md` is not exclusively yours after drafting starts: if you are ever re-run on this file, add to what you wrote or correct it in place, and leave stage 7's section alone rather than treating a re-run as licence to rewrite the file wholesale.

## Analysis framework

**Gap analysis.** Look across the summaries for: methodological gaps (approaches nobody has tried), empirical gaps (phenomena nobody has studied), theoretical gaps (concepts nobody has formalized), application gaps (domains nobody has applied this to), and temporal gaps (recent developments the literature hasn't caught up to).

**Trend detection.** Growing interest, declining areas, methods that are new since roughly 2022, and ideas being imported from adjacent fields. State every trend as a count, not an impression: "growing interest in X" is not a finding, "[N] papers on X published in [recent year] against [M] in [earlier year]" is. The same discipline applies to an underused method: not "rarely used" but "used in only [N] of the [total] papers in the pool." If the summaries do not give you the dated counts to fill that in, the trend is not established yet, say so, and do not round it off to a vaguer claim instead.

**Contradiction mapping.** Where one source's finding conflicts with another's, which methodological choices are actually in dispute, and which theoretical framings compete for the same phenomenon.

**Opportunity identification.** Novel combinations (technique from source A applied to the problem in source B), small under-explored niches, interdisciplinary bridges, and findings important enough to deserve replication but only tested once.

## Domain-critical gaps

Every domain has known confounds a reviewer will ask about even if no source in the pool raises them. Check the summaries against the table for the relevant domain and flag anything missing.

**Epigenetics / DNA methylation**

| Topic | Why it matters | Must address |
|---|---|---|
| Cell composition confounding | Blood leukocyte proportions shift with age/disease | Deconvolution or cell-type-specific analysis |
| Batch effects | Technical variation between runs | Batch correction method used |
| Normalization | Raw data needs preprocessing | Pipeline used (e.g. BMIQ, SWAN) |
| Probe reliability | Some CpG probes are unreliable | Filtering criteria (cross-reactive, SNP-containing) |
| Platform | 450k vs EPIC vs sequencing | Platform named and implications discussed |

**Machine learning**

| Topic | Why it matters | Must address |
|---|---|---|
| Train/test split | Prevents inflated performance claims | Split strategy, no leakage |
| Cross-validation | Robust performance estimate | CV strategy used |
| Hyperparameter tuning | Affects reported numbers | How parameters were chosen |
| Overfitting | Train vs. test gap | Held-out performance reported |
| Baselines | Contextualizes performance | What it was compared against |

**Clinical / biomedical**

| Topic | Why it matters | Must address |
|---|---|---|
| Population specificity | Effects may not generalize | Study population demographics |
| Confounders | BMI, socioeconomic status, smoking affect outcomes | How they were controlled |
| Effect sizes | Statistical vs. clinical significance | Magnitude, not just p-values |
| Calibration | Predictions must be well-calibrated | Calibration curves if predictive |

**Any computational method:** software/package versions, hardware requirements, reproducibility information (code availability, seeds). **Any measurement:** protocol detail, quality control steps, known limits. **Any dataset:** source and access, preprocessing applied, inclusion/exclusion criteria.

If a domain-critical topic is absent from every summary, say so plainly and name which sources should have addressed it, so the Architect knows to flag it as a known limitation rather than pretend it isn't there. Worked example:

```
Domain-critical gaps: epigenetics pool

1. Cell composition confounding
   Summaries mention tissue heterogeneity in general terms ({cite_10.1000/a}, {cite_10.1000/b})
   but none report a deconvolution method or cell-type adjustment.
   A reviewer will ask: "did you control for cell composition?"

2. Platform and preprocessing
   {cite_10.1000/c} mentions "technical noise" but does not name a platform (450k/EPIC)
   or a normalization pipeline.

Recommendation: architect should plan a paragraph naming the deconvolution method,
normalization approach, and platform used, even if only to state it as a limitation
of the reviewed literature.
```

## Output format

```markdown
# Research gaps and opportunities

**Topic:** ...
**Sources analyzed:** N

## Executive summary
One or two sentences: the biggest opportunity, and the recommended direction.

## 1. Major gaps
### Gap N: [title]
Description, why it matters, which sources show this limitation (cite by {cite_<doi>}), difficulty (low/medium/high), and 1 to 2 concrete ways to address it.

## 2. Emerging trends
### Trend N: [name]
What's happening, the evidence stated as a dated count ("[N] papers in [recent year] vs [M] in [earlier year]", never "growing interest" on its own), key sources, maturity (emerging/growing/established), and the opportunity it implies.

## 3. Contradictions
### Debate N: [question]
Position A ({cite_<doi>}) vs. position B ({cite_<doi>}), why it's unresolved, and a study design that could resolve it.

## 4. Methodological opportunities
Underused methods, stated as a count against the pool ("used in only [N] of the [total] papers"), unexplored datasets, and novel combinations nobody in the pool has tried.

## 5. Interdisciplinary bridges
Where one field has solved a problem another field is still stuck on.

## 6. Replication and extension
Findings from a single study worth replicating; studies worth extending to a new dataset or population.

## 7. Temporal gaps
Recent developments (events, datasets, techniques) no source in the pool has caught up to yet; assumptions older sources make that newer capability has since made obsolete.

## 8. Novel research angles (3)
### Angle N: [title]
Which gaps it addresses, what's novel, why it's promising, feasibility, a short proposed approach (3 to 5 steps), and the expected contribution.

## 9. Risk assessment
Low-risk opportunities (incremental, established methods) vs. high-risk/high-reward ones (novel or unproven).

## 10. Recommended next actions
A flat list of concrete next steps (which papers to read closely, which gap to chase, what to draft first). No time buckets: this isn't a schedule.

## Confidence
Gap analysis confidence, trend confidence, and novel-angle viability, each rated low/medium/high with one line on why, given how many sources actually support the claim.
```

## Every claim needs a source

Cite every gap, trend, and contradiction back to the sources that support it, using `{cite_<doi>}` inline, never a hand-written marker. A gap claimed without pointing at which sources fail to address it is an assertion, not an analysis. If you cannot confirm a claim from the summaries, mark it `[UNVERIFIED: reason]` rather than stating it as settled.

## Done when

- `research/gaps.md` exists with at least 3 major gaps, 2 trends, and exactly 3 novel research angles.
- Every gap, trend, and contradiction is backed by `{cite_<doi>}` references to sources that actually appear in `research/summaries.md`.
- Every trend and every underused method is stated as a count, not an adjective: no "growing interest," no "rarely used," without the dated numbers or the fraction-of-pool figure next to it.
- Domain-critical topics relevant to the pool's field have been checked against the table above, and any absence is stated explicitly rather than implied.
- The confidence section honestly reflects source count: don't claim high confidence from 4 sources.
