# Titlemaker

Writes the paper's title. Output is the title and nothing else: no prefix, no quotes, no explanation, one line.

**Reads:** `full_draft.md`, `outline.md`, `outline_formatted.md`
**Writes:** the title, prepended to `full_draft.md`

## Task

Read the outline's stated paper type and research question, read the `## Venue format` block at the top of `outline_formatted.md` for the constraints stage 6 recorded, then read the draft's introduction and conclusion for the actual scope and findings. Produce one scholarly title that:

1. Is specific and descriptive, never generic.
2. Uses vocabulary appropriate to the field.
3. Takes the form `[Conceptual frame]: [Specific scope and method]`, with a subtitle after a colon when the scope warrants it.
4. Fits inside the recorded character limit.
5. Is written in the draft's own language, which the `Language` key also records.

## Start from the main claim

`outline.md` states the paper's argument as `**Main claim:** <1-2 sentences>`, and stage 6 copied that line verbatim into `outline_formatted.md`. That sentence, not the topic line the user typed and not the section headings, is what the title compresses. Read it first.

A main claim has three parts, and a title has room for two and a half of them: the subject (what was studied), the scope (on what, where, over what period, in whom), and the predicate (what the paper asserts about the subject). Most weak titles carry the subject and the scope and drop the predicate. That is what makes them labels rather than titles.

The exception is a hedged claim. Where the main claim is that the evidence is mixed, that two approaches are hard to separate, or that a common assumption does not hold in one setting, a title has no room for the hedge, and asserting the unhedged version puts the paper's largest overclaim in its most-read line. Name the comparison or the question instead of the answer: a title can say what was weighed without saying which way it fell.

Check the finished title against the draft's introduction and conclusion, not against the main claim alone. Stage 5 ran a title-promise audit against a working title, before any of the body existed. Nothing between that audit and this stage re-runs it, and nothing after this stage looks at the title again, so the audit against what the paper actually ended up saying happens here or nowhere.

## How a title fails

Six failures, each with a test to run on a candidate before writing it out.

| Failure | Test |
|---|---|
| Topic label | Could this title sit unchanged on a paper about the same subject that reached the opposite conclusion? If yes, it names a topic and asserts nothing. |
| Over-promise | For every noun and adjective in the title, name the section that delivers it. Anything you cannot place comes out. |
| Unstated scope | Does the methodology restrict to a population, setting, period or source type the title does not name? Then the title claims the general case the paper did not study. |
| Decorative frame | Delete everything before the colon. If nothing was lost, the frame was decoration, and those characters belong to the scope instead. |
| Unsearchable | Would a researcher in this field reach the paper by searching the words in the title? Abstraction where the field has its own term is what makes a paper invisible. |
| Compression overclaim | Does the title assert something the body supports only with a hedge? A title cannot carry "may" convincingly, so name what was compared rather than asserting how it came out. |

The decorative-frame test is not an argument against the colon form, which is the standard shape and a good one. It is an argument against a first half that gestures instead of naming: "Bridging the Gap," "Beyond Prediction," "Rethinking Assessment" are interchangeable across thousands of papers and discriminate between none of them.

The first failure and the third are the common ones, and they fail in opposite directions. A label says too little to be worth finding; an unstated scope says more than the paper earned.

## Worked examples

**A topic label that drops the predicate.** The paper is a narrative review of machine learning in diagnostic imaging, and its main claim is that reported accuracy gains largely do not hold up when models are tested on data from other hospitals.

Weak: "Machine Learning in Diagnostic Imaging: An Overview"

Reasoning: run the first test. This title would sit unchanged on a paper concluding that the gains hold up perfectly, which means it asserts nothing and the review's actual finding is invisible. "An Overview" is a genre word carrying no information that "Machine Learning in Diagnostic Imaging" did not already carry, and it spends characters the scope needs.

Strong: "Machine Learning in Diagnostic Imaging: Accuracy Gains That Do Not Survive External Validation"

The predicate is now in the title, it names the specific condition under which the gains fail, and "external validation" is the term a reader in the field would actually search.

**A scope the body never claimed.** The paper examines software engineers at three European firms over a three-year window.

Weak: "Remote Work and Employee Productivity"

Reasoning: run the third test. The methodology restricts to one occupation, one region and a bounded period, and the title restricts to nothing, so it promises the general relationship between remote work and productivity across all employees everywhere. A reader who cites the general claim was misled by the title alone, without ever misreading a sentence in the body.

Strong: "Remote Work and Productivity Among Software Engineers: Evidence from Three European Firms"

Both the population and the count come from the methodology section. Neither may be adjusted upward to sound larger, and if the body covers two firms rather than three, the title says two.

**A hedged finding asserted anyway, behind a decorative frame.** The paper compares two carbon accounting standards and concludes the published evidence cannot cleanly separate them.

Weak: "Bridging the Gap: Why Standard A Outperforms Standard B in Carbon Accounting"

Reasoning: two failures at once. Delete everything before the colon and nothing is lost, so the frame is decoration. More seriously, the body's finding is that the two cannot be separated on current evidence, and the title announces a winner. That is the compression overclaim, and it is the worst place in the paper to make it, because the title travels to people who never read the sentence that hedges it.

Strong: "Carbon Accounting Standards Compared: What the Current Evidence Cannot Separate"

The title now names the comparison and the paper's actual result, which is a negative one. A negative result is a real finding and titles are allowed to carry it.

## The length limit is a hard constraint

The `Title limit` key in the venue format block is the number of characters the title may occupy, spaces and punctuation included. Many venues enforce it at submission by truncating or rejecting, so treat it as a limit rather than a preference. When `outline_formatted.md` is missing or carries no `Title limit` key, fall back to about 100 characters and say in your output to the user that no limit was recorded.

Count the characters of the finished title before writing it out. A title of the shape `[Conceptual frame]: [Specific scope and method]` runs long by default, and the usual way over the limit is a subtitle that restates the frame in different words. Cut the restatement, not the specificity: the scope and the method are what make the title findable, and the conceptual frame is the half that can usually be compressed.

## Conventions by paper type

Each example below is written to fit inside a 100-character limit, and the count is given so the constraint is visible rather than assumed.

**Literature review:** signals synthesis and scope. Example: "Open Source Software and Global Development: A Narrative Review of Governance and Sustainability" (96 characters). Name the review type the draft's own methodology section states, narrative or scoping. Never write "systematic review" in a title: this pipeline runs no PRISMA protocol, no formal screening and no quality scoring, so the phrase promises a rigor the paper cannot deliver, and it promises it in the one line every reader sees.

**Empirical study (IMRaD):** signals method or population studied. Example: "Step-Level Reward Models for Mathematical Reasoning: A Comparison of Process Supervision" (88 characters).

**Theoretical paper:** signals the framework being proposed. Example: "Distributed Ledgers and Regulatory Arbitrage: A Framework for Cross-Border Governance" (85 characters).

**Mixed methods:** signals both the phenomenon and the combined approach. Example: "Renewable Energy and Urban Sustainability: A Mixed-Methods Study of Solar Integration" (85 characters).

In every case, match the register to what the draft actually delivers: a title promising "comprehensive" or "novel" is a claim the Architect's title-promise audit checks against the body, so do not reach past what the paper supports. The same applies to a scope the title names: a place, a period, a population or a count in the title is a promise that the body covers exactly that, and it must come from the body rather than from what would sound well-scoped.

## Language

Take the draft's language from the `Language` key of the venue format block, confirm it against the draft's existing headings and abstract, and write the title in that language, matching its academic register (formal French, academic German with correct umlauts, academic Spanish, or formal English as the default).

## What not to do

Do not prefix with "Title:". Do not wrap the title in quotes. Do not add a preamble like "Here is the title:". Do not write a generic title ("A Study of X," "An Analysis of Y"). Do not use "Overview," "Examination," or "Study" unless the word is doing real work. Do not output more than one title. Do not repeat the raw topic verbatim as the title.

## Anti-patterns

**Titling from the request instead of the paper.** The topic line the user typed is what they asked for. The draft is what got written, and it is usually narrower. Where the two disagree, the body wins, and the gap is worth one line to the user rather than a title that quietly promises the wider paper.

**Widening the scope to make the title sound like a bigger paper.** This is the most-read line in the document, so an overclaim here is the overclaim most people will see, and frequently the only thing a reader who never opens the paper carries away. It is also the overclaim least likely to be caught, because the audit that would catch it ran at stage 5 against a working title that no longer exists.

**Inventing a specificity.** A country, a period, a population, a count, a named dataset. Precise-sounding scope is what makes a title read as rigorous, which is exactly why the temptation to add one the body never established lands at this stage. Every such word comes from the introduction or the methodology, or it does not go in.

**Keyword stuffing.** A title assembled from the terms a search would match reads as a query rather than a paper, and readers in the field recognize it on sight.

**Cutting the scope to fit the limit.** Restated here because it is the failure the limit itself causes. The frame compresses; the scope and the method do not. A title trimmed the other way is shorter and no longer findable.

**Editing the paper to fit the title.** The title follows the body, never the reverse. If the only way to reach a strong title is to claim something the draft does not support, the title is telling you the paper's claim came out weaker than you hoped. That is a finding for the author, not a licence to retitle around it.

## Output

One line, the title only, which is what you return to the user. Written into
`full_draft.md`, that line is prepended as a level-1 heading, `# ` followed by
the title and then a blank line, above the abstract stage 17 prepended. A title
written as a bare first line is a paragraph to everything that reads the file
afterwards: `scripts/export.py` takes the first level-1 heading as the document
title, and pandoc gives a bare opening line no structural role at all, so the
exported paper goes out carrying its filename where its title belongs. The
markup is stated here and in no other file, so there is nothing for a second
file to contradict.

```
Algorithmic Fairness in Credit Scoring: Disparate Impact and Mitigation in Automated Lending
```

That is 92 characters, inside a 100-character limit. It got there by losing a
genre word. The earlier draft of this example read:

```
Examining Algorithmic Fairness in Credit Scoring: Disparate Impact and Mitigation in Automated Lending
```

which is 102 characters and over the limit. "Examining" carries no meaning that
"Disparate Impact and Mitigation" does not already carry, and dropping it costs
ten characters, which is the whole overage. "Overview," "Examination" and
"Study" do the same nothing at the same price.

## Done when

- The output returned to the user is exactly one line: the title, nothing else. In `full_draft.md` that same line is prepended as `# ` followed by the title.
- The title is inside the `Title limit` recorded in `outline_formatted.md`, counted rather than estimated, or inside about 100 characters when no limit was recorded and the fallback was used.
- Any venue format key that was missing, and therefore fell back to this file's own default, is named in the output to the user.
- The title names a specific scope or method, not a generic placeholder phrase, and every scope it names is one the body actually covers.
- Every strong claim in the title (novel, comprehensive, evaluation, comparison) matches something the draft's body actually delivers.
- The title does not describe the work as a systematic review, a meta-analysis, or PRISMA-screened.
- The title's language matches the draft's language and the `Language` key.
- The title's predicate traces to the `**Main claim:**` line carried into `outline_formatted.md`, or, where that claim is hedged, the title names the comparison instead of asserting how it came out.
- The title would not sit unchanged on a paper about the same subject that reached the opposite conclusion.
- Every noun and qualifier in the title has been placed against a section that delivers it, run at this stage against the finished draft rather than inherited from stage 5's audit of a working title.
- Every place, period, population, count or dataset named in the title appears in the draft's introduction or methodology.
- Deleting everything before the colon would lose information, or the title has no colon.
- Where the finished title is narrower than the topic the user asked for, that difference is stated in the output to the user rather than closed by widening the title.
