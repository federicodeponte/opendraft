# Narrator

Narrator makes the whole paper read as though one person wrote it: consistent tone, person, tense, and vocabulary across every section. Crafter writes each section somewhat independently, so left unchecked, one section drifts casual while another over-hedges, or the document calls itself a "paper" in one place and a "thesis" in another. A paper is worse without this pass because the seams between sections show.

**Reads:** `sections/*.md`
**Writes:** `sections/*.md` (edited in place), `review/narrator.md`

The report goes in `review/`, never in `sections/`. Everything in `sections/` is
spliced into the finished paper by `scripts/assemble.py` at stage 9.5, so a report
left there becomes a chapter of the paper. It would also be read back as a section
by this stage on a re-run.

This is the last stage that works on section files. `full_draft.md` does not exist
yet, and no citation has been rendered: every source appears as a `{cite_<doi>}`
placeholder, and there is no references section yet.

The sweep for statistics with no citation at all runs once, at stage 11
(Verifier), over the assembled `full_draft.md`. This stage does not duplicate it.

## Voice standards

**Tone.** Objective and fact-based, confident without being arrogant, formal without being stiff.

**Person.** First person plural ("we analyzed," "our results show") for describing the paper's own work; third person for general statements ("the model performs," "this approach enables"). Avoid "I," "you," and "one."

**Tense by section.** Introduction in present tense, describing the current state of things. Literature review, methods, and results in past tense: what others found, what was done, what was observed. Discussion and conclusion in present tense: what it means, what the contribution is now.

## Document type

Pick one term for what this document is, and use it everywhere: "paper," "study," and "section" for a research paper; "thesis," "dissertation," and "chapter" for a thesis; "review" and "article" for a review article; "report" for a technical report. Check every section for terms outside the chosen set; a document that calls itself "this paper" in the introduction and "this thesis" in the discussion reads as unedited.

Wrong, mixed: "This paper presents..." (introduction) / "As demonstrated in this thesis..." (discussion)
Right, consistent: "This paper presents..." (introduction) / "As demonstrated in this paper..." (discussion)

## Common issues to fix

Too casual: "The results are pretty good" becomes "The results demonstrate strong performance."
Too emotional: "Surprisingly, we found..." becomes "The analysis revealed..."
Too hedging: "It seems like maybe this could potentially suggest..." becomes "This suggests..."
Too absolute: "This proves beyond doubt..." becomes "The evidence strongly supports..."

## Sentence rhythm is not this stage's job

Rhythm belongs to stage 14, which runs over the assembled draft with counted
bands, a run rule and a report. This stage does not set a length distribution and
does not chase one. Two stages measuring the same axis against different targets
is worse than one measuring it, because whichever runs first is edited over by
the second, and the numbers in this file would be the ones that lose: stage 14
plans for roughly 30 percent short, 50 percent medium and 20 percent long, and
it is the stage with the checkable definition of a run.

What this stage does do about sentences is register work that happens to be local
to one. Where a passive construction buries who did what ("data was collected"
rather than "we collected data"), convert it to active unless the passive is
doing real work, such as when the actor genuinely doesn't matter to the sentence.
That is a person-and-voice correction, which is this stage's subject, and it is
in scope regardless of what it does to any length count.

If a section reads as a metronome, note it in `review/narrator.md` for stage 14
rather than fixing it here. A note costs nothing and stage 14 reads the reports.

Grade level is a register signal here, not a number to hit. Graduate academic prose lands around Flesch-Kincaid 16. A section reading well below that usually means sentences too short and simple for the register, which is a register problem and therefore this stage's; well above usually means sentences too long or too clause-heavy to follow, which is a fault in the writing rather than a sign of rigor, and which stage 15 measures and acts on. Stage 15 owns the exit bands and the numbers in them; if a readability tool is available, note the estimate in the report and leave the judgement about whether it is out of band to the stage that states the band.

Never use a contraction in the paper's own prose: "do not" not "don't," "cannot" not "can't," "it is" not "it's." A contraction is a register slip in formal academic writing, distinct from a quote that legitimately contains one. Expand every one found, in every section.

As a last check on a section, read it as if aloud. Prose that trips over itself in the mouth, a clause that has to be re-read to land, a sentence that runs out of breath before its verb, usually trips a reader's eye too, even when every sentence individually passed the tone, person, tense and passive-voice checks above. This is a holistic check, not reducible to any rule above it.

## Fix in place

Edit the section files directly for tone, person, tense and register corrections; these are almost always small, local edits, a sentence rewritten, a verb tense changed, a passive construction flipped to active. Note in the report which sections needed the most adjustment, since a section far out of voice from the rest is often a sign it needs another look for other reasons too.

## Report

Write `review/narrator.md`:

```markdown
# Narrator report

Voice: first person plural, objective, formal but accessible.
Document type: "paper" / "study" / "section," used consistently.

## Fixed
- Results 4.2: "did really well" -> "achieved strong performance."
- Discussion 2 vs 5: paragraph 2 over-hedged, paragraph 5 overclaimed;
  both moderated to a consistent confidence level.
- Methods 3.1: "the researchers collected data" -> "we collected data."

## Vocabulary
- "significant" appeared 40+ times; varied with "meaningful," "substantial,"
  "considerable" where it was not a statistical-significance claim.
- "shows" appeared 30+ times; varied with "demonstrates," "indicates," "reveals."

## Register
- Estimated Flesch-Kincaid grade: [estimate, or "not measured"]. Recorded for
  stage 15, which owns the exit bands; nothing was edited here to move it.
- Contractions found and expanded: [count], all in [section].

## For stage 14
- [Section]: reads as a metronome, left for stage 14. / None noted.

## Notes
- All sections now consistently call this document "the paper."
```

## Done when

- Tone, person, and tense are consistent within each section and across all of them.
- The document uses one self-reference term throughout ("paper," "thesis," "review," or "report"), with none of the others appearing.
- `review/narrator.md` lists what was changed, and any heavily overused word that was varied.
- `sections/` contains section files and nothing else, so that stage 9.5 assembles the paper and only the paper.
- No section still contains casual, absolute, or over-hedged phrasing from the "common issues" list above.
- No sentence was split, joined or rewritten here for length or rhythm alone. Any section that reads as monotone is named in `review/narrator.md` for stage 14 instead of edited here.
- No contraction remains anywhere in the paper's own prose.
- Every section reads naturally when read aloud, and any grade-level estimate is
  recorded in the report for stage 15 rather than edited toward here.
