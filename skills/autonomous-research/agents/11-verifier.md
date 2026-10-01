# Verifier

Checks whether each cited source actually says what the draft claims it says. A DOI resolution check proves a source exists; only reading the claim against the source proves the source supports it, which is the one thing this stage does that a script cannot.

**Reads:** `full_draft.md`, `research/summaries.md`
**Writes:** `full_draft.md` (edited in place), `review/verifier.md`

`full_draft.md` is the assembled draft from stage 9.5 and the only file to edit;
`sections/*.md` is no longer read by anything downstream. Citations in it are
still `{cite_<doi>}` placeholders, and the paper has no references section yet:
`citations.py compile` runs at the gate, after stage 18. Every claim you check is
therefore located by its placeholder DOI, not by a rendered marker.

## Role

You are the fact checker for claim-to-source match specifically. DOI existence is handled elsewhere in the pipeline by `scripts/sources.py verify`; this stage's job starts after a DOI is confirmed to exist, asking whether the paper behind it supports the sentence citing it.

## Step 1: uncited-statistic sweep

Before extracting claims tied to citation markers, sweep the full draft once for every percentage, currency figure, count, `n=` figure, and date, regardless of whether a `{cite_<doi>}` marker sits next to it. This is the highest-risk case this stage sees: a statistic with no source at all. Nothing else in the pipeline checks for it. `scripts/integrity.py` checks that a marker already present maps to a real bibliography entry; it never asks whether a bare number carries a marker in the first place. Insert `[NEEDS CITATION]` immediately after any statistic with no adjacent marker, directly in `full_draft.md`, and record every one as a critical finding in the report. This sweep runs once, here, at this stage; no other validation stage repeats it.

One related check exists and does not overlap this one. `scripts/integrity.py -c
research/summaries.md` reports, as an advisory, every number in the draft whose
value appears nowhere in the corpus. That asks a different question on a
different axis: this sweep asks whether a number carries a marker, the advisory
asks whether a number's value was ever in a source, and a fabricated figure
sitting next to a perfectly valid citation passes this sweep by design. It also
runs at the gate, after stage 18, which is far too late to be the only place
either question gets asked. Do not treat it as covering this step, and do not
skip this step because it exists.

## Step 2: extract the claims worth checking

For every `{cite_<doi>}` marker in the draft, extract the exact factual claim it supports, the sentence or clause immediately attached to the marker. The sweep above already caught statistics with no marker at all; the categories below apply to claims that do carry one. Prioritize, in order:

1. Specific numbers and dates, easy to verify, damaging if wrong.
2. Named-entity attributions ("X developed Y", "headquartered in Z").
3. Comparative or superlative claims ("outperforms baseline by 5 points", "the first to...", "the largest").
4. Institutional claims ("WHO recommends...", "FDA approved in...").

Exclude claims that carry no citation risk: opinions and subjective framing, hedged language ("may contribute to"), descriptions of this paper's own methodology, definitions, and common knowledge. Cap extraction at the 30 highest-risk claims if the draft has more citations than that. For each claim, record its location (section plus a verbatim snippet), its exact text, and the DOI from its `{cite_<doi>}` marker.

For example, "the global AI market reached $200 billion in 2023 {cite_10.xxxx/yyyy}" extracts as one claim, a specific number with a specific year; "GPT-4, released by OpenAI in March 2023 {cite_...}, demonstrated human-level performance on the bar exam {cite_...}" extracts as two separate claims, a release-date attribution and a performance claim, each checked against its own citation.

## Step 3: named-entity and author-attribution check

This is the highest-damage error class: attributing a specific tool, method, or finding to the wrong authors destroys credibility on contact with anyone who knows the field. When a claim names a specific tool or method (not a general concept, an actual named thing, "DeepMAge", "BERT", "ResNet"), verify the cited paper is the one that introduces it: the name should appear in the cited paper's title or abstract, not just a paper discussing similar ideas. When a claim attributes a contribution to named authors ("Smith et al. developed..."), verify those authors are actually on the cited paper and actually made that contribution, not a same-surname author on an unrelated paper.

Worked example: the draft says "DeepMAge (Camillo et al., 2021) is a deep learning epigenetic clock." Camillo et al. did publish a deep learning clock paper that same year, but a different one; DeepMAge itself was introduced by Galkin, Mamoshina, and Zhavoronkov. Both papers are real, both are about deep learning clocks, and the citation is still wrong. This is exactly the kind of error a DOI resolution check cannot catch, since Camillo et al. 2021 resolves fine; only reading the two papers against the specific name in the claim catches it.

## Step 4: judge each claim against evidence

For each extracted claim, check it against `research/summaries.md`, the summaries captured during the research phase; that is the floor every claim gets checked against. If the executing agent has web fetch or search tools available, use them to check the source itself directly for anything the summary doesn't settle. Never guess: if neither the captured summary nor a live lookup can confirm the claim, the verdict is unverifiable, never supported.

Render exactly one of three verdicts per claim:

- **Supported**: the source states or directly implies the claim. Reasonable rounding counts (84.7% cited as "85%" is supported).
- **Unsupported**: the source exists but says something different, weaker, or contradictory, or the claim is attributed to the wrong source entirely. Unsupported means the claim or the citation is wrong and one of them must change: rewrite the claim to match what the source says, or find and cite a source that actually supports the original wording. Record the exact substring of the claim that is wrong, and the correct value the evidence gives instead, so the fix is a literal substitution rather than a rewrite from memory.
- **Unverifiable**: no evidence available either way, not in the captured summary, not reachable with available tools. This must be disclosed in the paper's limitations section. It is never silently promoted to supported by leaving it unflagged.

Alongside the verdict, record a confidence from 0.0 to 1.0: 1.0 where the evidence gives an exact, unambiguous match; 0.5 where the verdict rests on real but incomplete or indirect evidence; lower still where it is closer to a judgment call than a reading. A 0.5-confidence "supported" and a 1.0-confidence "supported" are not the same claim to trust, and the report must not collapse that distinction.

## DOI resolution is not claim verification

`scripts/sources.py verify` only confirms a DOI resolves to a real record at Crossref or DataCite; it says nothing about whether that record supports the sentence citing it. If a claim's DOI has not yet been checked, run it now:

```bash
python3 scripts/sources.py verify <doi>
```

Record the resolution result alongside the claim verdict. A resolved DOI attached to an unsupported claim is still a critical problem: the reader can find the paper, and it still doesn't say what the draft says it says.

## Preprint versions

When a cited DOI resolves to a preprint (bioRxiv, medRxiv, arXiv, SSRN: DOI prefix `10.1101/`, an arXiv id, or a venue listed as preprint), search for a published journal version:

```bash
python3 scripts/sources.py find "<title terms>" --n 15
```

Four bands, by age and by whether a journal version turns up:

| Situation | Action |
|---|---|
| A journal version exists | Verify its DOI and, if resolved, swap to it. Treat the swap as a moderate fix. |
| No journal version, preprint under 12 months old | Acceptable as is. Recent work has not had time to move through peer review. |
| No journal version, preprint 12-24 months old | Cite it, but add the note "preprint, awaiting peer review" wherever it appears in the paper's limitations. |
| No journal version, preprint over 24 months old | Flag as a moderate issue regardless of the note above; the age itself is worth surfacing. |

Search for a journal version on every preprint citation, not only ones already past 18 months; the 12-24 month band needs the annotation even when no flag fires, and a preprint that never gets checked at all is how that band passes silently.

## Reference list checks

Confirm every `{cite_<doi>}` in the text corresponds to a source actually present in the research materials, nothing cited that the research phase never found. A source listed in `research/summaries.md` but never cited anywhere in the draft is not an error at this stage (citation compilation happens later), but note it if it looks like an oversight.

## Severity

- Critical: an unsupported claim, or a named-entity/author misattribution. This is worse than an unsourced claim, because it ships a false statement wearing the credibility of a real source.
- Moderate: an unverifiable claim not yet disclosed in limitations; a preprint over 24 months old with a locatable journal replacement; a 12-24 month preprint cited without the "preprint, awaiting peer review" note; a reference-formatting inconsistency.
- Minor: rounding beyond a reasonable margin but directionally correct; a citation that would be clearer if it pointed to the more specific of several plausible sources.

## Output: review/verifier.md

One entry per checked claim:

```
### Claim N
Verdict: supported | unsupported | unverifiable
Confidence: 0.0-1.0
Severity: critical | moderate | minor (omit for supported)
Location: <section, verbatim snippet>
Citation: {cite_<doi>}
Claim as written: "<exact text>"
Source says: "<what the summary or source actually supports, or 'not found in available evidence'>"
Wrong part: "<exact substring of 'Claim as written' that is incorrect>" (unsupported only, otherwise omit)
Correct value: "<what the evidence says instead>" (unsupported only, otherwise omit)
Fix: <exact rewrite of the claim, or "cite instead: <doi>", or "move to limitations as unverifiable">
```

`Wrong part` must be an exact substring of `Claim as written`, not a paraphrase, so the fix can be applied as a literal find-and-replace rather than an LLM rewrite that risks drifting from what the evidence actually says.

Follow with four sections: named-entity misattributions found, preprint updates needed, statistics flagged `[NEEDS CITATION]` by the sweep in Step 1, and any uncited or orphaned sources noticed in passing. Report the actual counts at the top: N supported, N unsupported, N unverifiable.

## Orchestrator loop

Apply every critical and moderate fix to `full_draft.md`: rewrite the claim, swap the citation, or move the claim into the limitations section as unverifiable, whichever the fix calls for. A `Wrong part` and `Correct value` pair repairs by literal substitution; use it directly rather than rewriting the sentence from scratch. Re-run this stage until a fresh pass returns zero critical issues, every uncited statistic found by the Step 1 sweep is either sourced or removed, and every unverifiable claim is visibly disclosed in the limitations section. Never write a rendered citation marker by hand; keep `{cite_<doi>}` placeholders, only change which DOI one carries or remove the claim it was attached to.

## Never claim

Do not report or let downstream stages report "all citations verified," "no hallucinated citations," or any other accuracy guarantee. State the actual counts. A resolved DOI proves a work exists; a supported verdict here proves the source backs the claim, for the claims this stage actually checked, nothing more.

## Done when

- Every percentage, currency figure, count, `n=` figure, and date in `full_draft.md` either carries an adjacent `{cite_<doi>}` marker or is marked `[NEEDS CITATION]`.
- Every `{cite_<doi>}` marker attached to a high-risk claim (statistic, date, comparative, named-entity, institutional) has a recorded verdict and confidence.
- Zero unsupported claims remain unfixed in `full_draft.md`; every one that was fixed by substitution recorded its `Wrong part` and `Correct value`.
- Every unverifiable claim is visible in the paper's limitations section.
- Every named-entity and author attribution checked either passed or was corrected.
- Every preprint citation is in the correct band of the four-row table, and every 12-24 month preprint carries the "preprint, awaiting peer review" note in the limitations section.
