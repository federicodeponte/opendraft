# Abstract

Writes the paper's abstract from its finished content. This is the only thing this stage touches: it does not edit the introduction, body, conclusion, or references, and it does not add citations.

**Reads:** `full_draft.md`, `outline_formatted.md`, `research/brief.json`
**Writes:** the abstract, prepended to `full_draft.md`

## Scope

Read the whole draft: introduction, body sections, discussion, and conclusion. Two things are absent at this stage and neither is an error. The draft has no compiled references section, because its sources are still inline `{cite_<doi>}` placeholders that `scripts/citations.py compile` renders at the gate. And it has no title, because stage 18 writes the title after this stage; so the paper's scope has to be read out of the introduction and conclusion rather than off a title line, and nothing here should be phrased as an echo of a title that does not exist yet. The abstract summarizes what is already there; it does not introduce a claim, a number, a source, or a contribution that the body does not already make. Every sentence in the abstract has to already exist, in substance, somewhere in `full_draft.md`; if it does not, it belongs in the body first, not in the summary of the body. If the draft currently has an abstract placeholder (for example "## Abstract" followed by a note that it will be generated later), replace that placeholder with your output. Do not touch anything else in the file.

## The venue decides the length, not this file

Stage 6 recorded the target venue's requirements in a `## Venue format` block at the top of `outline_formatted.md`. Read that block first. Two of its keys govern this stage:

- `Abstract length` is the word range to write to. A journal that caps abstracts at 150-250 words caps them, and an abstract written to this file's default instead will be rejected at submission, which is a failure nobody in the pipeline catches.
- `Keywords` is how many keyword terms to supply, commonly 3 to 6.

Use the numbers below only as a fallback, and only when `outline_formatted.md` is missing or its venue format block does not carry the key. When you fall back, say which key was missing in your output to the user, so the omission surfaces at stage 6 rather than at submission.

Where the user's own brief stated a cap, that cap outranks both. Stage 6 copied it into the `abstract_max_words` key of `research/brief.json`, so read that file before writing and treat its number as the ceiling: a brief that says "an abstract of at most 200 words" has asked for at most 200 words, and a 280-word abstract written to this file's fallback has not answered it. When the recorded venue range and the brief's cap disagree, write to the brief's cap and note the difference in your output to the user.

Then count, rather than judging by eye. `python3 scripts/integrity.py full_draft.md --stats` prints an `abstract words` line for the block as it now stands in the file, and a run of it after prepending the abstract is what turns "about 200 words" into a number you can compare against the cap. Compress and re-count until the figure is inside the range; the gate at the end of the pipeline counts the same way, so a block that is over here is over there too.

The structure below stays the same at every length. At a shorter recorded range, keep all four labelled parts and compress each to one or two sentences rather than dropping a part; at the fallback range, two to three sentences each is right.

## Structure: four paragraphs plus keywords, 250 to 300 words as the fallback range

**Paragraph 1, research problem and approach (2-3 sentences).** What problem does the paper address, why does it matter, what approach does the paper take. Draw this from the introduction.

**Paragraph 2, methodology and findings (2-3 sentences).** How the work was done and what it found. Draw this from the methodology and results/discussion sections, and describe the method in the words that section uses: if the methodology section says narrative review, the abstract says narrative review.

**Paragraph 3, key contributions (2-3 sentences, numbered).** Three contributions as `(1) ..., (2) ..., and (3) ...`. Draw this from the conclusion and discussion; be specific rather than generic, naming the mechanisms and scope the body itself names ("a comparison of the CO2-pricing mechanisms and member states the results section actually covers," not "a comprehensive analysis"). Specificity means copying the body's scope, not inventing a sharper-sounding one.

**Paragraph 4, implications (2-3 sentences).** What the findings mean for theory and for practice. Draw this from the discussion and conclusion.

**Keywords line.** As many comma-separated terms as the `Keywords` key records, 3 to 6 as the fallback, covering the paper's main topics, methods, and subfield, in the terms a reader would actually search for. Fewer, better-chosen terms beat a long list: a keyword line that names every noun in the paper indexes it under none of them.

Bold each paragraph's label, matching this shape:

```markdown
**Research Problem and Approach:** [2-3 sentences]

**Methodology and Findings:** [2-3 sentences]

**Key Contributions:** [2-3 sentences: (1) ..., (2) ..., (3) ...]

**Implications:** [2-3 sentences]

**Keywords:** term one, term two, term three, ...
```

Worked example, English, written to a recorded `Abstract length` of 150-250 words: that is the commonest journal cap and the value `agents/06-formatter.md` records by default, so it is the case worth showing. It runs about 180 words. Do not read it as the fallback length. At the 250-300 fallback each of the four parts carries its full two to three sentences and the whole runs correspondingly longer, which is why the "Done when" list below refuses anything under 200 words when the fallback was used.

```markdown
**Research Problem and Approach:** Open source software (OSS) has moved beyond its origins as a development methodology to become a candidate framework for addressing global infrastructure challenges. This paper examines whether OSS's collaborative and decentralized structure translates into measurable gains in equitable technology access and sustainability outcomes.

**Methodology and Findings:** The paper presents a narrative review of governance, economic, and adoption studies of open-source projects, identified through the search strategy described in the methodology and compared against [the access and sustainability indicators the body actually uses]. It finds that [the relationship the body's analysis section actually reports, in the terms the body reports it].

**Key Contributions:** This paper makes three contributions: (1) a comparative framework for evaluating OSS governance models against sustainability outcomes, (2) [the second contribution as the conclusion states it], and (3) a set of governance indicators usable by funders assessing OSS investments.

**Implications:** The findings suggest that policy and funding decisions aimed at OSS sustainability should weight governance structure ahead of license choice. This has direct relevance for public-sector procurement guidelines and for foundations funding digital public infrastructure.

**Keywords:** open source software, governance, sustainability, digital public infrastructure, licensing
```

Three things about that example are load-bearing.

The methodology sentence says "narrative review" and "search strategy," never "systematic review," "systematic search protocol," or "PRISMA screening." This pipeline has no formal screening or quality-scoring mechanism, so those words claim a rigor that was not exercised, and an abstract is the most-read sentence in the paper to claim it in. `references/paper-types.md`, under "Review type: three names, two supported," states the rule and the substitutes.

The bracketed slots are slots. Every number, every project or study count, and every stated finding gets filled from what the body of `full_draft.md` actually says, in the terms it says it. No count appears in the example because the correct count is whatever the body reports, and an abstract that names a figure the body does not contain is a fabrication that reviewers check first.

That risk is sharpest here because the template sentence around each bracket is already finished, real prose; a paragraph that already reads well makes it tempting to finish the bracket to match its tone rather than open `full_draft.md` and copy out what the body actually says. Resolve every bracket from the draft itself, not from what would sound right next to the sentence around it: the finding, the count, and the contribution in the bracket all have to be traceable to a specific sentence already in the body, the same way a number in a section traces to a specific entry in `research/summaries.md`. If the body reports a finding without a number, the abstract reports it without a number too.

The keyword line has five terms, not fifteen, because five is inside the usual 3-6 venue range. Count them against the `Keywords` key before writing the line.

Worked example, compressed to a shorter recorded range (for example, a venue whose `Abstract length` key records 100-150 words instead of the 250-300 fallback):

```markdown
**Research Problem and Approach:** [Field] increasingly relies on [the technique the introduction names], yet its effect on [the outcome the introduction frames as the open question] remains contested. This paper tests that relationship using [the approach the methodology section states].

**Methodology and Findings:** [The data or source set the methodology section actually names] were analyzed with [the specific method the methodology section states]. The analysis finds [the finding, in the terms the results or discussion section actually reports it].

**Key Contributions:** (1) [the first contribution as the conclusion states it], (2) [the second contribution as the conclusion states it], and (3) [the third contribution as the conclusion states it].

**Implications:** These findings suggest [the implication the discussion draws], with direct relevance for [the audience or decision the discussion names].

**Keywords:** [term one], [term two], [term three]
```

Same four labelled parts, same keywords line, every bracketed slot filled from the body exactly as in the longer example above; the only thing that changes at a shorter recorded range is that each paragraph compresses to one sentence instead of two or three. Do not drop a labelled part to fit a shorter range; compress every part instead.

## Language

Write in the draft's own language, taken from the `Language` key of the venue format block and confirmed against the draft's headings. There is no title to read it off yet. Keep the paragraph labels in that language too (`Schlüsselwörter:` for a German draft, not `Keywords:`), and follow that language's own academic and punctuation conventions.

## What not to do

Do not write in first person ("we," "our," "I"). Do not add a `{cite_<doi>}` placeholder or any citation; an abstract summarizes the paper's own claims and does not cite the paper's own sources. Do not copy sentences verbatim from the body. Do not use an abbreviation before defining it. Write the abstract under a single `## Abstract` heading. That heading is the only markup it gets: the bolded paragraph labels are not headings, and the keywords line is not a section of its own. Do not add frontmatter, a title, or any other section. The heading level is stated here because it is the one piece of markup this stage has to agree on with the stages after it. Stage 18 prepends the title above this block as the document's only level-1 heading, and `scripts/export.py` reads the first level-1 heading as the exported document's title, so an abstract that arrives under a `#` heading of its own takes that slot and titles the finished paper "Abstract". Do not add a meta-comment like "Here is the abstract." Do not describe the paper as a systematic review, a meta-analysis, or a PRISMA-screened review; write "narrative review" or "scoping review," whichever the draft's own methodology section states, and use "search strategy" and "source selection" for how sources were found. Do not state a number, a count of studies or projects, or a finding that does not already appear in the body.

Do not exceed the recorded `Abstract length` range, and never exceed the brief's own `abstract_max_words` cap where one was stated. When falling back because no range was recorded and the brief stated no cap, do not exceed 350 words or fall under 200. Do not skip this stage: every paper this pipeline produces opens with an abstract, and a draft that reaches the gate without one is missing its first section rather than running a leaner pipeline.

## Done when

- The output is exactly four bolded-label paragraphs plus one keywords line, inside the `Abstract length` range recorded in `outline_formatted.md`, or 250-300 words (200-350 acceptable) when no range was recorded and the fallback was used.
- The brief's `abstract_max_words` cap, where `research/brief.json` records one, is not exceeded, and the figure was checked by running `python3 scripts/integrity.py full_draft.md --stats` rather than estimated.
- The keyword count matches the recorded `Keywords` key, or is 3 to 6 when the fallback was used.
- Any venue format key that was missing, and therefore fell back to this file's own numbers, is named in the output to the user.
- Paragraph 3 uses the numbered `(1) (2) (3)` form.
- Every claim in the abstract also appears, in substance, somewhere in the draft's body; nothing here is new. Every number in the abstract appears in the body, in the same terms.
- The abstract does not call the work a systematic review, a meta-analysis, or a PRISMA-screened review, and does not describe source selection as a systematic search protocol.
- No citation placeholder and no first-person pronoun appears anywhere in the output.
- The abstract's language matches the draft's language, including the keywords label.
- Nothing outside the abstract placeholder was modified.
