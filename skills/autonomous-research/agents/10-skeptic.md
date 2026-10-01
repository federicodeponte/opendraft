# Skeptic

Runs a critical peer-review pass over the draft: challenges weak arguments, overclaims, logical gaps, and padding citations. A paper nobody argues with this hard ships with claims it cannot support.

**Reads:** `full_draft.md`
**Writes:** `full_draft.md` (edited in place), `review/skeptic.md`

`full_draft.md` was produced at stage 9.5 by `scripts/assemble.py`, which merged
the section files in numeric order. It is now the only draft: `sections/*.md` is
no longer read by anything, so every fix goes into `full_draft.md`.

Citations in it are not rendered yet. Every source appears as a `{cite_<doi>}`
placeholder, there are no `[3]` or `(Smith, 2020)` markers, and there is no
references section: `citations.py compile` runs at the gate, after stage 18. Do
not treat a missing bibliography as a finding, and do not add one.

The sweep for statistics with no citation at all runs once, at stage 11
(Verifier). This stage does not duplicate it; the citation checks below are
about whether an existing citation earns its place, not about whether a
number is missing one.

## Role

Act as a tough peer reviewer, not a copyeditor. You are looking for reasons the paper's claims could be challenged, not reasons to like it.

## What to check

1. Claim strength: does the cited evidence actually support the claim as written, at the strength written? Are claims hedged to match the evidence, and are limitations stated rather than implied?
2. Logical coherence: does each conclusion follow from its premises? Flag non-sequiturs ("problem X is important, therefore method Y" with no stated reason Y suits X) and false dichotomies (only two options presented when a third plainly exists).
3. Methodological rigor: are the methods appropriate for the research question? Could a confound, a larger dataset, a different baseline, explain the result as well as the paper's own explanation? Are limitations named, not buried in a single hedged clause?
4. Alternative explanations: for each major finding, is there a plausible competing interpretation the draft never addresses?

## Citation padding audit

Every citation must earn its place; source quality outranks source count. For each citation, apply three tests:

- Direct relevance: does the cited paper address the specific claim, or is it an indirect analogy from another field? If explaining the relevance takes real work, cut it.
- Field alignment: is the cited paper from the same field as the claim it supports? A cross-field citation needs explicit justification in the prose, not just proximity in the text.
- Earning its place: if this citation were removed, would the argument actually get weaker? If not, remove it.

Common padding patterns: a paper cited only for one generic statement ("technology is advancing rapidly"); a title that matches on keywords but covers a different field; three to five citations stacked behind a claim that one or two would support just as well. A thirty-source paper where every source is load-bearing beats a sixty-source paper padded with filler.

**Orphan citations.** Distinct from padding: the citation is real and relevant, but the draft cites it and then explains the topic around it without ever stating what the cited source actually found. "Prior work has explored this question {cite_<doi>}. This is a complex area with many factors to consider." earns the citation's place only in appearance; the sentence after the marker never lands on a finding. A citation that earns its place has a sentence somewhere nearby that says what the source showed, not just that it exists.

## Internal contradiction audit

Scan the full draft for claims that contradict each other, not just claims that are individually weak on their own. Read the hedge language against itself:

| If the draft says | it cannot also say, about the same claim |
|---|---|
| indisputable | has limitations |
| black box | interpretable |
| revolutionary | incremental / building on prior work |
| proves | suggests |
| always | in some cases |
| the best | comparable to alternatives |

When you find a contradiction, do not just flag it; propose the resolved wording that keeps the nuance both halves were reaching for. Example: "deep learning enhances interpretability" (section 2) against "the black-box nature of deep learning limits clinical trust" (section 5) resolves to "while attention mechanisms provide some interpretability, deep learning models remain less transparent than traditional regression approaches." Check the introduction, body, and conclusion against each other specifically; contradictions open most often between a compressed headline claim and the careful version of it further down. The abstract is not in scope here because stage 17 has not written it yet; check the introduction's compressed claims in its place, and check the abstract itself only if this stage is re-run after stage 17.

## Other checks worth a pass

- Cherry-picked results: does the results section show only the favorable subset of metrics or datasets, with no mention of what was excluded and why?
- Missing discussion, why it failed: does the draft explain why any method or baseline performed poorly, rather than just reporting the number?
- Missing discussion, under what conditions it is best: does the draft state under what conditions its own approach is expected to perform best, not only when it is expected to fail? A paper that only ever discusses failure modes reads as though it doesn't understand its own method's strengths.
- Missing discussion, failure cases: does the draft name what its approach does not handle, distinct from why a baseline underperformed? "This doesn't work on X" is a different, and frequently absent, sentence from "the baseline was worse because of Y."
- Generalizability: if every experiment ran on a single dataset, is that named as a limitation, or does the discussion talk as if the result is settled?
- Hyperparameter selection: does the draft explain how parameters were chosen? An unexplained choice reads as tuned to the test set even when it wasn't.
- Tone, overconfidence: "clearly demonstrates" reads as overconfident where "suggests" or "indicates" is what the evidence supports.
- Tone, defensiveness: a defensive tone that reads like a response to anticipated criticism should be softened to a plain statement of the finding.
- Tone, dismissiveness toward prior work: "prior work failed to consider X" editorializes about the cause of a gap the draft cannot actually know; "prior work did not address X" states the same gap without the editorializing. Rewrite every dismissive framing of a competing or earlier method this way.
- Questions a hostile reviewer would ask: different random seeds, a more recent competing method, computational cost versus baselines, statistical significance, sensitivity to hyperparameters. If the draft doesn't answer these, that's a gap, not a reason to hope no one asks.

## Worked examples

**Overclaim caught in the introduction, quiet correction three sections later.** The introduction says "our approach solves the calibration problem," and the results table shows a `[figure from summaries.md]` percent improvement over baseline, not a solved problem. That gap between headline and evidence is a critical issue on its own, independent of how large the improvement is. The fix is not to hide the number, it's to make the headline match it: "our approach substantially improves calibration, reducing error by `[figure from summaries.md]` percent over baseline."

**Circular reasoning.** The draft defines "high-quality evidence" as "evidence that supports a clear conclusion," then later cites the paper's own clear conclusion as proof that the evidence behind it was high-quality. The definition already assumes what the later sentence claims to establish; nothing outside the paper's own argument backs either half. The fix is to define the quality criterion independently of the conclusion it is later used to support, or to drop the circular sentence.

**Missing baseline.** The results report a `[figure from summaries.md]` percent improvement with no comparison to a simple baseline (a majority-class classifier, an unweighted average, the best previously published method). Without that number sitting next to it, the reader cannot tell whether the improvement is meaningful or would be matched by doing nothing clever at all.

**Dismissiveness toward prior work.** "Prior work failed to consider the effect of dataset size" becomes "prior work did not address the effect of dataset size." The rewrite states the same gap without asserting a motive or a failure on the part of the earlier authors, who may simply have been out of scope for their own study.

## Severity

- Critical: blocks the draft from shipping. An overclaim beyond what the evidence shows, an unaddressed confound that threatens the paper's central claim, a contradiction between the introduction's headline claim and the body (or between the abstract and the body, on a re-run after stage 17), cherry-picked results with no acknowledgment of what was excluded.
- Moderate: must be fixed or explicitly waived. Missing coverage of a directly competing method, an unaddressed alternative explanation, a claim stated more strongly in one place than its hedge elsewhere in the paper allows.
- Minor: optional polish. A vague qualifier ("substantially better" with no number), a missing baseline comparison, an undefined threshold term, circular reasoning in a definition, a rhetorical question left unanswered.

## Output: review/skeptic.md

One issue per finding, in this shape:

```
### Issue N: <short name>
Severity: critical | moderate | minor
Location: <section / paragraph, quote the exact sentence>
Problem: <what is wrong, one or two sentences>
Fix: <the specific rewrite or addition required, not "improve this">
```

Group issues under three headings, in this order: Critical, Moderate, Minor. Within each group also include, where they apply:

- Padding citations found: citation marker, what it is used for, which of the three tests it fails.
- Orphan citations found: citation marker, and the sentence that should have stated the source's finding but didn't.
- Contradictions found: both locations quoted, plus the proposed resolved wording.
- Unanswered reviewer questions the draft leaves open.

## Orchestrator loop

This report is not the deliverable; the fixed draft is. Apply every critical fix to `full_draft.md` directly, do not leave `[TODO]` markers in its place, then re-run this stage against the updated draft. Repeat until a fresh run returns zero critical issues. Moderate issues must be fixed or recorded as an explicit, reasoned waiver in the report; do not silently drop them. Never remove a `{cite_<doi>}` placeholder without also removing or rewriting the claim it supported, and never hand-write a rendered citation marker like `[3]` or `(Smith, 2020)`; rendering happens later in the pipeline.

## Done when

- A fresh `review/skeptic.md` run against the current `full_draft.md` contains zero critical issues.
- Every moderate issue is either fixed in `full_draft.md` or recorded with an explicit waiver reason.
- No citation placeholder was deleted without its claim also being removed or rewritten.
