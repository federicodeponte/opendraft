# Referee

Simulates journal peer review, scoring the draft against the rubric a real reviewer uses and predicting the actual comments it would draw, so the paper meets that bar before a real reviewer finds the gap.

**Reads:** `full_draft.md`
**Writes:** `full_draft.md` (edited in place), `review/referee.md`

`full_draft.md` is the assembled draft from stage 9.5 and the only file to edit.
Judge it as a work in progress in two known respects, and do not spend a finding
on either: citations are still `{cite_<doi>}` placeholders with no rendered
markers and no references section, because `citations.py compile` runs at the
gate after stage 18; and there is no abstract or title yet, because stages 17 and
18 write them. A real reviewer would want all three, and all three arrive later.

The sweep for statistics with no citation at all runs once, at stage 11
(Verifier), before this stage ever sees the draft. This stage does not
duplicate it.

## Role

Score the draft as a journal reviewer would, then write out what two or three distinct reviewer personas would actually say, grounded in specifics from the draft rather than generic reviewer boilerplate.

## Rubric

Score each dimension 1 to 5, using the per-dimension split below to arrive at the number, then justify it in one sentence tied to something specific in the draft, not to how confident it sounds:

- Novelty: 5 groundbreaking, paradigm-shifting; 4 significant novel contribution; 3 incremental but solid advance; 2 minor novelty; 1 no novelty.
- Significance: 5 will transform the field; 4 important contribution; 3 useful addition; 2 limited impact; 1 negligible impact.
- Technical quality: 5 flawless methodology; 4 strong, rigorous work; 3 sound but some limitations; 2 methodological concerns; 1 fundamentally flawed.
- Clarity: 5 exceptionally clear; 4 well-written; 3 adequate; 2 needs improvement; 1 confusing.
- Reproducibility: 5 fully reproducible, code and data public; 4 reproducible with effort; 3 partially reproducible; 2 difficult to reproduce; 1 cannot reproduce.

## Per-dimension assessment

For any dimension scored below 5, write the split that produced the number, not a restatement of the score:

- **Novelty.** List what is novel, specifically, naming the contribution; then list what is incremental, naming the prior framework or method it builds on. A score of 4 or 5 needs a non-empty "novel" list. A score of 3 needs the "incremental" list longer than the "novel" one. This split is what keeps a novelty score honest: without it, "incremental" and "groundbreaking" are both just adjectives.
- **Significance.** Separate the potential impact (theoretical, practical, methodological, whichever applies) from the likely influence (who would actually build on or cite this, and for what).
- **Technical quality.** List strengths and weaknesses separately, each tied to a specific part of the methods or results, not a general impression.
- **Clarity.** Separate writing quality (sentence and paragraph level) from presentation issues (a specific figure, table, or undefined notation), since a paper can be well-written and still poorly laid out, or the reverse.
- **Reproducibility.** List what can be reproduced from what is written as it stands, and what cannot be without something not yet provided (code, data, an exact hyperparameter). A score above 3 needs the "cannot reproduce" list to be short or empty.

## Desk-reject scan

Before scoring, check for the failures that get a paper rejected without full review: out of scope for the stated venue, insufficient novelty, an obvious methodological flaw, incomplete experiments, no comparison to prior work, or writing too poor to evaluate. Any one of these is critical regardless of the rubric scores below it.

## Predicted reviewer comments

Write what two or three distinct reviewer personas would say, grounded in specifics from the draft rather than generic reviewer boilerplate. Three personas and their characteristic concerns, adapted to what this draft actually contains:

- **A domain expert** typically praises how the paper frames the problem within the field, asks about a recent competing method the related-work section may not cover, and requests an ablation study isolating which part of the approach drives the result.
- **A methodologist** typically questions sensitivity to hyperparameter choices, requests significance testing and error bars on the reported results rather than point estimates alone, and flags evaluation on a single dataset as a generalizability concern.
- **A practitioner** typically asks about computational cost relative to the baselines compared against, and requests a code release so the method can actually be adopted.

For each persona actually written, ground the concern in something specific the draft does or omits, and state: what they would praise, what they would question, and the single thing they would most likely request before recommending acceptance. Then separately predict the major-revision requests (an ablation study, a second dataset, a comparison to a specific recent method, error analysis, code release) and the minor-revision requests (a figure caption, undefined notation, a formatting inconsistency) a real review is likely to produce.

## Worked example

Technical quality scored 3/5: "sound but missing ablation studies, which component drives the improvement is not isolated." That sentence is the justification a real reviewer writes, tied to a specific missing artifact, not a restatement of the score. The predicted comment that follows from it: "a methodologist reviewer will ask how sensitive results are to each component, and will request an ablation study before recommending acceptance," which is a moderate issue, not a critical one, because the paper is still sound, just short of one experiment a reviewer will name explicitly.

## Severity

- Critical: a desk-reject flag, or any rubric score of 1 or 2 on novelty, significance, or technical quality.
- Moderate: a rubric score of 3 on any dimension; a predicted major-revision request, missing ablation, single-dataset generalizability concern, no statistical significance testing.
- Minor: a predicted minor-revision request, unclear figure caption, undefined notation, inconsistent formatting.

## Output: review/referee.md

```
## Scores
| Criterion | Score | Justification |
|---|---|---|
| Novelty | n/5 | ... |
| Significance | n/5 | ... |
| Technical quality | n/5 | ... |
| Clarity | n/5 | ... |
| Reproducibility | n/5 | ... |
| Overall | avg/5 | arithmetic mean of the five dimension scores above, rounded to one decimal place |

## Desk-reject risks
<list, or "none found">

## Issues
### Issue N
Severity: critical | moderate | minor
Location: <section>
Reviewer concern: <what a reviewer would flag, and why>
Fix: <the specific addition or change that pre-empts it>

## Predicted reviewer comments
<by persona: praise, questions, the one thing each would request>
```

## Orchestrator loop

Apply every critical fix, desk-reject risks first, then any rubric dimension scored 1 or 2, to `full_draft.md` before anything else, then re-run this stage. Moderate issues should be fixed or explicitly waived with a stated reason ("single dataset; a second dataset is out of scope for this venue's page limit"); do not leave a predicted major-revision request unaddressed and unmentioned. Because Overall is always the arithmetic mean of the five dimension scores, it moves automatically as each dimension improves; there is nothing to separately negotiate about it. Repeat until a fresh run shows zero critical issues and an Overall average that meets the acceptance floor stated in `SKILL.md`.

## Done when

- No desk-reject risk remains, or each one is explicitly waived with a stated reason.
- No rubric dimension scores below 3 without a recorded waiver.
- Every dimension scored below 5 has its per-dimension split written out, not just a restated number.
- The Overall score in `review/referee.md` is the arithmetic mean of the five dimension scores, not a separately judged number.
- Each written reviewer persona's praise, question, and top request is grounded in something specific the draft does or omits, not generic reviewer boilerplate.
- Every predicted major-revision request is either fixed in `full_draft.md` or explicitly deferred with a stated reason in `review/referee.md`.
