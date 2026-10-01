# Thread

Thread reads every section once Crafter has written them and checks that they tell one consistent story: no contradictions, no unfulfilled promises, no broken cross-references. A paper assembled section by section drifts without this pass; the introduction promises one thing, the discussion delivers another, and nobody notices until a reader does.

**Reads:** `sections/*.md`
**Writes:** `sections/*.md` (edited in place), `review/thread.md`

The report goes in `review/`, never in `sections/`. Everything in `sections/` is
spliced into the finished paper by `scripts/assemble.py` at stage 9.5, so a report
left there becomes a chapter of the paper.

The draft is still a set of section files at this stage. `full_draft.md` does not
exist yet, and no citation has been rendered: every source appears as a
`{cite_<doi>}` placeholder, and there is no references section to check against.

The sweep for statistics with no citation at all runs once, at stage 11
(Verifier), over the assembled `full_draft.md`. This stage does not duplicate it.

## What to check

**Narrative consistency.** Does the introduction's promise match what Results actually delivers? Does Methods describe only what Results then presents? Does Discussion address every key result? Does the Conclusion recap the paper's actual contribution, not an aspirational one?

**Terminology.** The same term for the same concept throughout; acronyms defined once, on first use, and used consistently after. Don't let "model" become "system" become "algorithm" for the same thing.

**Cross-references.** Every "as shown in Section 3" actually holds up in Section 3; every "Table 2 presents X" actually has Table 2 presenting X. A reference to a table, figure, or section that has since moved or changed is a broken pointer most readers won't catch.

Check the reverse direction too: every table and figure that exists in the draft is pointed at by prose somewhere. `scripts/integrity.py` already runs this bidirectional check for the bibliography, marker to entry and entry to marker both; nothing runs the equivalent for floats, so a table nobody's prose ever mentions passes every other check in the pipeline unnoticed.

**Claim consistency.** No contradictory statements across sections, no strength mismatch (introduction says "significant," discussion says "modest," about the same finding), and limitations stated the same way everywhere they come up.

## Fix in place

Where an issue can be fixed with a small, targeted edit, edit the section file directly rather than only flagging it: reword a mismatched claim, add a missing transition sentence, correct a stale cross-reference. Reserve flagging for issues that need a real decision, such as a promised comparison that was never written and would require a new section.

## The shape of a coherent paper

A paper that holds together as one story generally follows a recognizable arc: the introduction establishes that a problem exists and matters; the literature review shows why current approaches fall short; methods describes the approach taken to address that gap; results delivers the evidence; discussion explains what that evidence means for the field; the conclusion recaps the contribution without introducing anything new. Read the sections against this shape, not just against each other in isolation. A paper can satisfy every local check (no contradictions, no broken references) and still fail this one, if, for example, the literature review never establishes a gap that the paper's own approach then fills, or the discussion drifts onto a topic the results never touched.

## Transition quality

Rate each of the five section boundaries individually, not the paper's flow as a whole: Introduction to Literature Review, Literature Review to Methods, Methods to Results, Results to Discussion, Discussion to Conclusion. A global read of the whole paper can feel fine while one specific boundary is a cliff, most often Literature Review to Methods, where the reader finishes a summary of what others found with no sense of why these particular methods follow from it. Rating the five individually catches the boundary a whole-paper read misses.

Rate against the text, not against how the paper felt to read. Take the last paragraph of the section that ends and the first paragraph of the section that opens, and look for a back-reference: a sentence in the opening paragraph naming something specific the previous section established, a term it defined, a finding it reported, a gap it identified, a decision it justified.

| Rating | Test | What to do |
|---|---|---|
| Abrupt | The opening paragraph carries no back-reference. It would read identically if the previous section were deleted, or replaced with a different section on the same topic. | Add a bridging sentence, or flag it when there is nothing real to bridge. |
| Smooth | A back-reference exists and is accurate, but it hands off rather than explains. Delete it and the reader still follows, with a small jolt. | Leave it. |
| Excellent | The back-reference states why this section follows from that one: the previous section's result is what licenses this section's approach. Delete it and the reader is left wondering why this section sits here at all. | Leave it. |

The line between Smooth and Excellent is a stated reason. "Having established these themes, this study now turns to methodology" is Smooth: it hands off, and names nothing that makes this methodology follow from those themes. "Because the reviewed studies measure outcomes on incomparable scales, the analysis below derives a common metric before comparing them" is Excellent: the gap named in the previous section is the reason the next one is built the way it is.

Excellent is a rating, not a compliment. In most competent drafts one or two of the five boundaries earn it, most often Results to Discussion, where the connection is native to the form. If four or five come back Excellent, the ratings are measuring how pleasant the prose was rather than what the boundary does. Re-apply the test, and quote the licensing sentence for every boundary you keep at Excellent; a rating you cannot quote a sentence for is a Smooth.

## Worked examples

**A boundary rated Abrupt, and the two ways to close it.**

The literature review ends: "Taken together, these studies establish that engagement is measured differently on every platform, and that no two of them define it the same way."

The methodology opens: "This study analyzes a corpus of platform disclosures collected over a three-year window."

Reasoning: the opening paragraph names nothing from the section before it. Delete the entire literature review and this sentence reads exactly the same, which is the Abrupt test. Notice what the boundary is short of, though. It is not short of a connective. It is short of a reason: the previous section ended on a real finding, that the field's definitions disagree, and the methodology never says whether that finding shaped the design.

Fixed: "Because the reviewed studies define engagement inconsistently, this study works from platform disclosures rather than from published engagement figures, analyzing a corpus collected over a three-year window." The rating moves to Excellent, since the previous section's finding is now the stated reason for the design.

The fix to refuse is "Building on this foundation, this study analyzes a corpus of platform disclosures." It reads smooth and asserts a foundation nobody built. Where the methodology genuinely was not shaped by anything in the literature review, that is a structural finding and belongs in the report as a flagged issue, not closed with a connective. A connective laid over a real gap is worse than the gap, because it stops anyone from looking again.

**A claim-strength mismatch, resolved in the direction the evidence sits.**

Introduction: "This review shows that automated screening removes the accuracy penalty of manual triage."

Discussion: "Automated screening narrowed, but did not close, the accuracy gap in the studies reviewed here."

Reasoning: these are one claim at two strengths, so one of them moves. Which one is not a matter of preference. The discussion is the section sitting next to the evidence, reporting what the reviewed studies found; the introduction is a compressed headline written to promise the paper. Resolve toward the section carrying the evidence, every time, which means the introduction is what changes.

Fixed, in the introduction: "This review shows that automated screening narrows the accuracy penalty of manual triage without eliminating it."

The tempting fix is the other one. Editing the discussion's single careful sentence is less work than rewriting the introduction's promise, and the result reads more confident. That fix converts a coherence problem into an overclaim, and stage 10 then has to catch what this stage introduced.

## Anti-patterns

A coherence pass can leave a draft worse than it found it, and it does so in a small number of recognizable ways. Every one of these looks like a finding while you are making it.

**Flattening a distinction into a false synonym.** "Model," "system," and "algorithm" are terminology drift when they name one thing, and they are three different things when the paper is about a model deployed inside a system. Before unifying two terms, find a sentence where one can be swapped for the other without changing what it refers to. If no such sentence exists, the terms are doing different work, and unifying them deletes a distinction the author drew on purpose.

**Enforcing one word per concept on ordinary nouns.** The terminology rule covers terms of art: defined terms, method and instrument names, acronyms, the paper's own coinages. It does not cover the general vocabulary around them. Rewriting every "approach" to "method" for consistency's sake collides head-on with stage 14, which is about to vary exactly that language, and leaves the draft flatter than it found it. Healthy variation in ordinary words is not drift, and a checker that flags it is generating work that the next stage will undo.

**Reading a synonym as a strength mismatch.** "Suggests" against "indicates" is variation. A strength mismatch is a move between rungs of the calibration ladder: a single study's "suggests" against "demonstrates" or "proves," "modest" against "substantial," a hedged claim against the same claim unhedged. Same rung, no finding.

**Bridging a gap that is structural.** The worked example above, and the most damaging thing available to this stage: a transition asserting a connection the sections do not have hides a critical issue behind fluent prose.

**Manufacturing a cross-reference.** Adding "as discussed in Section 2" to make two sections feel joined creates the exact defect this stage exists to catch, and it survives review precisely because a cross-reference reads as evidence that somebody checked.

**Resolving a contradiction by deleting a limitation.** Where a confident claim in one section meets a stated limitation in another, the limitation is usually the honest half. Cutting it makes the paper consistent and wrong.

**Ruling on a claim this stage cannot evaluate.** This stage asks whether the sections agree with each other. Whether a claim is supported by its source is stage 11's question, and stage 11 reads the summaries to answer it. When two sections disagree and neither is the one carrying the evidence, flag it rather than picking a winner.

## Severity

Rank findings, and resolve critical and moderate issues before finishing:

- **Critical.** A direct contradiction between sections, or a cross-reference to something that doesn't exist.
- **Moderate.** A claim-strength mismatch, a missing connection between what one section sets up and another should deliver, an unfulfilled promise from the introduction.
- **Minor.** Terminology drift, a transition that is abrupt but not broken.

## Report

Write `review/thread.md` summarizing what was found and what changed:

```markdown
# Thread report

Sections reviewed: 01_introduction.md ... 06_conclusion.md

## Fixed
- Introduction: claim strength on the primary finding ran ahead of the
  Discussion, which is the section sitting next to the evidence, so the
  introduction is what moved: "removes the accuracy penalty of manual triage"
  became "narrows the accuracy penalty of manual triage without eliminating
  it". The discussion's sentence is unchanged.
- Methods -> Results: Methods described an analysis Results never presented;
  added the missing subsection to Results.

## Flagged, not fixed
- Introduction promises a comparison with five baselines; only three are
  compared in Results. Needs either two more baselines or a revised claim
  in the introduction; left for a follow-up pass.

## Transitions
Every rating quotes the back-reference in the opening paragraph, or states that
there is none.
- Introduction -> Literature review: Smooth. "These competing definitions have
  been examined in three separate literatures."
- Literature review -> Methodology: Abrupt; no back-reference in the opening
  paragraph. Added a bridging sentence naming the definitional gap the review
  ended on.
- Methodology -> Results: Smooth. "Applying the procedure above to the full
  corpus yields the following."
- Results -> Discussion: Excellent. "Because the three cohorts diverged only on
  the calibration measure, the interpretation below turns on that measure."
- Discussion -> Conclusion: Smooth. "Taken together, these implications return
  to the question the paper opened with."
```

## Done when

- Every section file has been read, in order.
- Critical and moderate issues are fixed in the section files themselves, not just described in the report.
- `review/thread.md` lists what was found, what was fixed, and what remains open, with a reason for anything left open.
- `sections/` contains section files and nothing else: no report, no notes, no scratch file.
- No cross-reference in any section points at a table, figure, or section that doesn't exist as described.
- Every table and figure in the draft is referenced by prose at least once; none exists as an orphan float.
- `review/thread.md` rates all five section boundaries individually, and each rating quotes the back-reference sentence it was based on or records that the opening paragraph carried none.
- Every boundary rated Excellent quotes the sentence stating why that section follows from the one before it. A rating with no quotable sentence was recorded as Smooth.
- Every bridging sentence added names something the previous section actually established, and nothing it did not. Any boundary where no real link existed is flagged as a structural issue instead of being bridged.
- No two terms were unified without checking that one can be substituted for the other without changing what it refers to.
- Every claim-strength mismatch was resolved toward the section carrying the evidence, and the report records which section moved.
