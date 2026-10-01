# Polish

Final copyedit pass: catches the two things a spellchecker cannot, confident wording that outruns the evidence, and repetition that reads as careless rather than considered. This is the last stage in the pipeline that touches prose; nothing downstream reviews wording again.

**Reads:** `full_draft.md`, `research/brief.json`
**Writes:** `full_draft.md` (edited in place), `review/polish.md`

`full_draft.md` is the assembled draft from stage 9.5. Citations in it are still
`{cite_<doi>}` placeholders and there is no references section to copyedit, since
`citations.py compile` runs at the gate after stage 18. Do not punctuate around a
marker that is not there yet, do not add a bibliography, and do not "fix" a
placeholder into a rendered marker; the compiler owns both.

## Role

Act as the copyeditor doing the last pass before submission: grammar, spelling, punctuation, flow, plus the two substantive checks below.

## Claim calibration

Marketing language destroys academic credibility. Every strong claim has to match the evidence actually cited for it.

| Overconfident | Calibrated replacement |
|---|---|
| indisputable | strong evidence suggests |
| proves conclusively | provides strong support for |
| without doubt | with high confidence |
| the only | among the few / a primary |
| the best | among the strongest / highly effective |
| revolutionary | represents a significant advance |
| paradigm shift | important development (unless citing Kuhn) |
| always | in most studied contexts / consistently |
| never | rarely / in no observed cases |
| perfect | highly accurate / near-optimal |
| solves | addresses / substantially mitigates |
| proves | supports / demonstrates |

Rules: match confidence to evidence strength, multiple studies and meta-analyses earn confident language, a single pilot study does not. An absolute claim ("always," "the best") needs evidence across every case it implies, not most of them; if you can't show "all," don't claim "all." A comparative claim ("superior performance," "significant improvement") needs the actual comparison and, where relevant, the effect size or p-value, not just the adjective. For each strong claim, ask whether a skeptical reviewer would accept the wording as written; if not, soften it to what the evidence actually supports, rather than deleting the claim outright.

## Repetition

Build a frequency count across the draft. Flag any phrase of three or more words that appears more than twice, and any single word, excluding technical terms and method names that have to repeat, appearing more than roughly five times per page. Watch especially for "significant/significantly," "important/importantly," "notable/notably," "clearly," "obviously," usually filler rather than precise claims. Vary the repeated language; don't just delete it if the idea still needs to be said.

## Grammar

- Subject-verb agreement with collective nouns: "data" is plural in academic writing ("the data show," not "the data shows"); "team" and "committee" are singular in US English.
- Tense by section: present tense for the introduction's framing and the discussion's implications, past tense for what the literature review found and what the methods and results did.
- Which versus that: "that" for a restrictive clause ("methods that improve accuracy"), "which" with a comma for a non-restrictive aside ("the Horvath clock, which was developed in 2013, remains widely used").
- Parallel structure in lists: "the study aims to identify biomarkers, validate their accuracy, and assess clinical utility," not a mix of gerund and infinitive forms in one list.
- Spelling convention: pick US or UK spelling and hold it throughout the whole draft (optimization, not a mix of optimization and optimisation).

## Punctuation

- Hyphenate a compound adjective when it sits directly before the noun it modifies: "state-of-the-art methods," "well-documented approach." Do not hyphenate the same phrase when it stands alone after a verb: "these methods are state of the art," not "state-of-the-art."
- Serial comma: pick one convention, with or without the comma before the final "and" or "or" in a list of three or more, and hold it throughout the whole draft. Do not mix.
- Add a comma after an introductory phrase or clause of four or more words ("Given these constraints, the model underperforms" needs the comma; "Overall the model underperforms" does not, because "overall" is one word).
- Expand an acronym in full at its first use in the draft, with the acronym in parentheses immediately after; use the acronym alone from then on.
- Consistent -ed forms, held to the same US-or-UK convention as spelling: "learned" not "learnt," "focused" not "focussed," if the draft is US English; the reverse if it is UK English.

## Flow

Three moves, applied where the draft's own seams call for them, not inserted on a schedule:

- **Transition at an abrupt seam.** Where one paragraph or section ends and the next opens on an unrelated note, add a transition that ties the content together, for example "Building on this foundation," or "This constraint shapes the analysis that follows." Do not reach for the stacked connectives entropy already flags as overused ("additionally," "furthermore," "moreover," "consequently"); a transition that restates what actually connects the two passages is both a better fix and the one that will not collide with the entropy stage's own rule against that scaffolding.
- **Split an over-long sentence.** A sentence carrying more than one independent claim, or running well past the rest of the paragraph's rhythm, splits into two without losing or softening either claim.
- **Reorder within a subsection.** When two or three sentences in the same subsection would read more logically in a different order, reorder them; do not reorder across a citation placeholder in a way that separates it from the claim it supports.

Exit bands, useful as a rough check on the pass as a whole rather than a target to hit sentence by sentence: a Flesch-Kincaid grade level around 15.8 reads as appropriate for academic prose, while something around 17.2 reads as too dense; a mean sentence length near 19 words is a reasonable landing point, which is stage 14's length mix (30 percent short, 50 percent medium, 20 percent long) averaged over band midpoints of roughly 10, 20 and 30 words rather than a second target competing with it; the midpoints are stated because two of stage 14's bands are open at one end, so an average over them is only as precise as the points you pick, and a figure carried to a decimal place would be claiming an accuracy the bands cannot support; a passive-voice share around 18 percent is acceptable for academic writing, not a defect to eliminate.

## Length: count the words before handing the draft on

This is the last stage that rewrites prose, so it is the last chance to make the draft the length the user asked for. Read the brief's own numbers from `research/brief.json` (stage 6 wrote them; `word_range` is the pair to work against) and count what is actually there:

```bash
python3 scripts/integrity.py full_draft.md --stats
```

That prints a `main text words` line, which counts the body and excludes the bibliography and the abstract, so it is the number a stated range is about. Compare it against the range and act on the difference:

- **Over the top of the range.** Cut. Take the cut out of whatever repeats an argument already made, restates a source's finding a second time, or explains at length what a sentence already established; those are the passages whose removal costs the paper nothing. A stated cap is a cap, and a draft that overruns it by half has answered a different request, however good the prose is. Never cut a `{cite_<doi>}` placeholder or the claim it supports to make the number: if the only way to reach the cap is to drop evidence, cut elsewhere first and say what had to go.
- **Under the bottom of the range.** Expand where the draft is genuinely thin, meaning a claim carried by one source that others also speak to, a mechanism asserted rather than explained, or a section whose implications stop short of what the discussion promised. Do not pad: repeating a paragraph in other words, restating the introduction in the conclusion, or stretching sentences adds words and subtracts credibility, and stage 14 will read the result as filler.
- **Inside the range.** Leave the length alone and get on with the copyedit.

Re-run the count after the pass rather than trusting the edit to have landed where you estimated. An estimate is how a draft arrives at 9,600 words against a 6,000-word cap; the command above is thirty seconds and settles it. `SKILL.md` under "Length is a number, not an impression" states the same rule for the pipeline as a whole.

## Worked examples

- Calibration: "epigenetic clocks show indisputable predictive power" next to a later "significant limitations remain, including population bias and tissue variability" is both an overconfidence problem and an internal inconsistency; soften the first to "epigenetic clocks show strong predictive associations, though generalizability varies across populations and tissue types" so the two sentences stop fighting each other.
- Grammar: "the model perform well" to "the model performs well" (subject-verb agreement); "data was collected" to "data were collected" (data is plural in academic usage); "methods which improve accuracy" to "methods that improve accuracy" (restrictive clause).
- Repetition: "significant" appearing twelve times across a ten-page draft is not twelve separate observations, it's one word doing the work of five; vary with "substantial," "considerable," "notable," "marked," and "appreciable" depending on which one the specific sentence actually means.
- Punctuation: "the field needed a state of the art approach to this problem" to "the field needed a state-of-the-art approach to this problem" (compound adjective before the noun it modifies); "Given the sample size the results should be read cautiously" to "Given the sample size, the results should be read cautiously" (comma after an introductory phrase).
- Flow: two adjacent sentences, "The model was trained on the full dataset. Additionally, hyperparameters were tuned via grid search, cross-validation was performed across five folds, and the resulting configuration was evaluated on a held-out test set that had not been seen during any prior stage of development," become "The model was trained on the full dataset, with hyperparameters tuned via grid search and cross-validation performed across five folds. The resulting configuration was then evaluated on a held-out test set that had not been seen during any prior stage of development." The stacked "Additionally" opener is gone, and the second sentence, which carried three separate claims, is split so each has room.

## What never changes

Never remove a citation or a `{cite_<doi>}` placeholder while polishing; if a sentence carrying a placeholder needs rewriting, rewrite around the placeholder and keep it attached to the same claim. Resolve a claim-calibration finding by softening the claim to what the evidence supports, not by deleting it outright if the underlying evidence still supports a weaker version. Never introduce a rendered citation marker like `[3]` or `(Smith, 2020)` by hand; rendering happens later in the pipeline.

## Output: review/polish.md

```
## Calibration fixes
Location | Before | After

## Repetition fixes
Phrase or word | Occurrences | Locations | Varied to

## Grammar fixes
Location | Before | After

## Punctuation fixes
Location | Before | After

## Flow improvements
Location | Move (transition added / sentence split / reordered) | Before | After

## Readability, before and after
Flesch-Kincaid grade | Mean sentence length | Passive voice share

## Open questions for the author
<anything ambiguous enough that guessing would be wrong, e.g. "significantly better" where it's unclear if the author means statistically significant>
```

## Done when

- No banned overconfident phrase from the table above remains unaddressed in `full_draft.md`.
- No phrase of three or more words appears more than twice, and no crutch word appears more than about five times per page.
- Tense is consistent within each section per the convention above, and every which/that and parallel-structure issue found is fixed.
- Every compound adjective directly before a noun is hyphenated, the serial-comma convention is held throughout, every introductory phrase of four or more words has its comma, every acronym is expanded at first use, and -ed forms match the draft's US-or-UK convention.
- Every abrupt seam got a transition that does not repeat the stacked connectives entropy already bans, every sentence carrying more than one independent claim was considered for a split, and no reorder separated a `{cite_<doi>}` placeholder from the claim it supports.
- `review/polish.md` reports before-and-after readability figures, even approximate ones, rather than omitting the section.
- Every `{cite_<doi>}` placeholder present before polish is still present after, attached to the same claim.
- The `main text words` figure, read from `python3 scripts/integrity.py full_draft.md --stats` after the pass, sits inside the `word_range` recorded in `research/brief.json`, or `review/polish.md` says which end it missed and why cutting or expanding further would have cost the paper evidence.
