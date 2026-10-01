# Paper types and length

This pipeline varies a paper along two independent axes: **paper type**, which determines section order and what each section has to argue, and **scale**, which determines how long the paper and its source list should be. They combine freely: a literature review can be short or thesis-length, exactly as an empirical study can. Read this file at stage 5, alongside `agents/05-architect.md`, and again at stage 6 when the word basis and venue format are settled.

Cross-references in this file name a file and a section heading, never a line number. Line numbers in a prompt bundle go stale the first time anyone edits the file above them, and a stale pointer into a neighbouring agent's instructions is worse than no pointer, because it reads as precise. The one exception is the historical note at the end, which cites line numbers in a different project's source repository; those are a record of where something was, not an instruction to go and read it.

## Paper type: section order

Four structural templates, named in `agents/05-architect.md` under "Paper types":

| Paper type | Section order |
|---|---|
| Literature review | Introduction, methodology, themes, discussion, conclusion |
| Empirical study (IMRaD) | Introduction, methods, results, discussion |
| Theoretical paper | Introduction, background, framework, implications, conclusion |
| Mixed methods | Introduction, literature review, methods, results, discussion, conclusion |

None of these four carries its own separate word-count table. The word budgets below apply across all four; what changes between them is section naming and which sections exist at all (an empirical study has no separate "literature review" heading, a theoretical paper has no "results").

## Review type: three names, two supported

Within "literature review," this pipeline distinguishes three review types, stated explicitly in `agents/05-architect.md` under "Review type: say which one this is":

- **Narrative review.** Curated exploration of the literature. The default.
- **Scoping review.** Systematic mapping without formal quality assessment. Supported.
- **Systematic review.** Not supported. It requires a PRISMA protocol with formal screening and quality scoring, and this pipeline has no mechanism for that. If a systematic review is requested, say so plainly, offer "comprehensive literature review" or "scoping review" as the alternative, and record in `outline.md` that the approach taken is narrative. In the methodology, write "search strategy" and "source selection," never "systematic search protocol" or "PRISMA screening": those words promise a rigor this pipeline cannot deliver.

The prohibition is not confined to the methodology section, and the places it is most often breached are the places most people read. Nothing this pipeline produces may be called a systematic review anywhere: not in the title stage 18 writes, not in the abstract stage 17 writes, not in a section heading, not in a caption, and not in what any stage reports back to the user. Two stages have this written into their own instructions, `agents/17-abstract.md` under "What not to do" and `agents/18-titlemaker.md` under "Conventions by paper type," because a single sentence in an abstract is enough to make the whole paper overclaim.

## Word budget: two real tables, and how they relate

Two word-count tables exist in this pipeline's own agent files, produced at two different stages, and they are not the same numbers. Both are real; neither is wrong; they serve different purposes.

**The planning range**, from `agents/05-architect.md` under "Structure" (used when first structuring the outline, and when no specific total length was requested):

| Section | Words |
|---|---|
| Abstract | 250-300 |
| Introduction | 800-1,200 |
| Literature review | 1,500-2,500 |
| Methodology | 1,000-1,500 |
| Results / analysis | 1,500-2,000 |
| Discussion | 1,500-2,000 |
| Conclusion | 500-700 |
| **Total (sum of the ranges above, not stated as a single figure in the source)** | **~7,050-10,200** |

**The proportional model**, from `agents/06-formatter.md` under "Length targets" (used once a format and venue are chosen and a specific total is known, and explicitly meant to be scaled):

| Section | Words | Share |
|---|---|---|
| Abstract | 250 | 1% |
| Introduction | 2,500 | 12% |
| Literature review | 6,000 | 28% |
| Methodology | 2,500 | 12% |
| Results | 6,000 | 28% |
| Discussion | 3,000 | 14% |
| Conclusion | 1,000 | 5% |
| Total | 21,000 | 100% |

(The listed subtotals sum to 21,250, about 250 words over the stated 21,000 total; the discrepancy is small and the formatter table itself frames these as a proportional model to scale from, not an exact accounting, so treat the 21,000 as approximate rather than reconciling it to the last word. The share column does reconcile exactly: each share is its row against the 21,250 actually listed, and the seven sum to 100. That is why the two largest sections read 28 percent and not 29.)

The planning range's Introduction row is itself divided into five finer parts in `agents/05-architect.md` under "Structure" (hook and context, problem statement, research question, contribution, organization, roughly 200/200/150/250/100 words), which sum to roughly 900 words inside the 800-1,200 total above. Treat those five as the centres of their own small bands, not as five independent floors stacked on top of the section total.

**How to use the two together.** The formatter's own instruction, verbatim from `agents/06-formatter.md` under "Length targets," is: "Scale proportionally for a shorter target length; keep the literature review and results as the two largest sections regardless of overall scale." Read the 21,000-word table as the proportions (roughly 1/12/28/12/28/14/5 percent), not as a fixed target. For a specific target length, multiply those shares by the actual word count wanted. The architect's smaller range is a reasonable default for a standard paper when no other length has been specified; the formatter's table is what to reach for once a specific target (a venue's word limit, a thesis chapter's length requirement) is known and the sections need to be scaled to fit it.

**Pick one basis, and say which.** These are two bases for the same decision, not two opinions to average. A paper uses the architect's default ranges or the formatter's scaled shares, never some sections from each. `agents/06-formatter.md` records the choice in the `Word basis` key of the venue format block it writes at the top of `outline_formatted.md`, and the per-section numbers in its own "Formatted structure" list are the default-scale reading of that same decision, not a competing third table.

**Every number here is a band, never a floor.** `scripts/integrity.py` checks word count as the target plus or minus ten percent, so a section written to exceed its number fails the same check a short section fails. `agents/07-crafter.md` states this in its own terms under "Word count": a section that comes in short is reporting thin evidence, and the response is to record the gap rather than to pad toward the number.

In both tables, literature review and results are consistently the two largest sections (28% each in the formatter table; the two widest ranges in the architect table). That balance holds across scale: a paper padded in the introduction or discussion instead reads as opinion-driven rather than evidence-driven, which is exactly what the formatter's note is warning against.

## Scale: matching pipeline depth and source count to what was asked

Three tiers, stated in `SKILL.md` under "Scale":

| Tier | Word count | Stages | Sources |
|---|---|---|---|
| Short piece | 1,500-3,000 words | 1-7, then 9.5, 10, 11, 15, 17 (skips 8, 9, 12-14, 16, 18) | 10-15 |
| Full paper (default) | Formatter's scaled table, ~21,000 words at full scale | All 18, plus 9.5, and 4.5 for a review | 25-50 |
| Thesis chapter or long review | Formatter's scaled table, scaled up; a long review runs 8,000-12,000 words | All 18, plus 9.5, and 4.5 for a review, with stage 7 (drafting) run once per subsection rather than once per section | 60+ for a long review, 50+ otherwise |

Stage 9.5 appears in every tier above and is never one of the skipped stages. It is `scripts/assemble.py`, and stages 10, 11 and 15 all read `full_draft.md`, which does not exist until assembly has run. A tier list that drops it is not a shorter pipeline, it is one that stops at stage 10 with nothing to read.

Stage 17 appears in every tier for the same kind of reason. Both word-count tables above open with an abstract row, so every paper this pipeline produces has an abstract as its first section, and the tier that skipped stage 17 was not producing a shorter paper, it was producing one whose opening section nobody wrote. Scale changes its length and the document type changes its name (an article's abstract, a committee paper's summary, an evidence brief's key findings), never whether it is there. Where the brief states a cap on it, that cap governs; `agents/17-abstract.md` carries the fallback range for when none was stated.

`agents/06-formatter.md`, under "Reference URLs: cite the actual source, not the tool you found it with," gives the corresponding citation-count floor by paper type rather than by scale tier: roughly 20 references for an empirical paper, 50 or more for a literature review, drawn from `research/citations.json`. The temporal shape of that pool is stage 1's to set, not the formatter's: `agents/01-scout.md` fixes it under "Quality filtering," in that section's "Balance temporally" step, relative to the current year rather than to a fixed window, and `agents/06-formatter.md` records what stage 1 achieved instead of specifying a second split against it.

When the two disagree, the paper type's floor governs. A literature review written at the full-paper tier gathers fifty or more sources, not the 25-50 its tier row suggests: the tier band describes the usual case for a paper of that length and is not a cap, while the per-type floor is the point below which a review has not surveyed enough of the literature to be one. This is worth stating rather than leaving to judgement, because a narrative review at the default scale is the commonest thing this pipeline is asked for, so the two numbers collide in the default case and not in some edge case a reader can be trusted to notice.

That floor is a floor on sources gathered, which is the one number in this file that genuinely is one, and it is not a licence to cite a source the drafting stage has not read. `research/summaries.md` marks each source as fully read or metadata-only, and a metadata-only source can be cited for its existence and its topic but never for a finding, a method or a number. A reference list that clears 50 while most of its entries are metadata-only is a list of things that exist, not a body of evidence, and the honest place to say so is the paper's limitations.

## "Thesis chapter" is a scale, not a paper type

There is no fifth structural template for a thesis chapter. A thesis chapter is the "thesis chapter or long review" scale tier above, applied to whichever of the four paper types actually fits the chapter's content (a literature-review chapter uses the literature-review structure; a methods-and-results chapter uses the empirical-study structure). The only structural difference at this scale is that stage 7 drafts one subsection at a time instead of one section at a time, so a 6,000-word literature-review section, say, might be drafted as four or five separately-written 1,200-1,500-word subsections rather than one pass.

## Where OpenDraft's original axis went

The source project this pipeline is ported from (OpenDraft) used a different, more granular axis: `academic_level` (`research_paper`, `bachelor`, `master`, `phd`), each with its own word-count table enforced in code at `engine/draft_generator.py:312-380` of the source repository, plus a separate coarser floor-check in `engine/utils/quality_gate.py:81-87`. That axis is not carried into this port: `agents/05-architect.md` and `agents/06-formatter.md` use the single scalable model documented above instead, combined with the three-tier "scale" system in `SKILL.md`. The source numbers are recorded here only as historical context, not as anything this pipeline enforces:

| academic_level (source project only, not this pipeline) | Total words | Min. citations |
|---|---|---|
| research_paper | 3,000-5,000 | 10 |
| bachelor | 10,000-15,000 | 15 |
| master | 25,000-30,000 | 25 |
| phd | 50,000-80,000 | 50 |

If a user asks for output shaped like one of these four tiers specifically (for example, "write this at bachelor's-thesis length"), treat it as a request for a target word count and citation floor to plug into the scale system above, not as a fifth paper type or a mode this pipeline has separate code for.

## Checklist for stage 5

- Name the paper type (one of the four above) and, if it's a review, the review type (narrative or scoping, never systematic).
- State the paper's main claim and instantiate the argument flow's X, Y, Z and W in the paper's own terms, per `agents/05-architect.md` under "Main claim and argument flow"; a structure with sections but no stated claim gives the drafting and review stages nothing to argue toward.
- Pick a scale tier, or a specific target word count if the user gave one.
- Derive each section's word budget either from the architect's default range (no target length given) or by scaling the formatter's percentage table to the target (a specific length was given).
- Set the citation-count floor from the per-paper-type guidance in `agents/06-formatter.md` under "Reference URLs: cite the actual source, not the tool you found it with," adjusted upward if the scale tier is "thesis chapter or long review."
- Check the planned results table against `research/summaries.md` before writing it into the outline: every metric column has to be one that at least two sources' entries actually report, and a source marked metadata-only there fills no metric row at all. If the pool reports no common metric, plan the comparison the pool supports and say so, rather than planning the table the template suggests.
- Write no example statistic into `outline.md`. Where a value is needed to show a claim's shape, leave a bracketed slot; a number invented to illustrate an outline is inherited by the drafting stage as though it had a source.
- Record all of the above explicitly in `outline.md`, per `agents/05-architect.md`'s own "Done when" list.
