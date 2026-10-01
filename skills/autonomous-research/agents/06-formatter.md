# Formatter

Applies a concrete academic style and submission structure to the Architect's outline: format family, section numbering, citation style, table/figure numbering, and length targets. A structurally sound outline still reads as unsubmittable without this pass.

**Reads:** `outline.md`, `research/citations.json`, the user's own brief
**Writes:** `outline_formatted.md`, `research/brief.json`

## Supported formats

**IMRaD** (most science journals): abstract, introduction, materials and methods, results, discussion, conclusion (sometimes folded into discussion), references.

**IEEE** (engineering, computer science): abstract, index terms, introduction, body sections, conclusion, acknowledgments, references.

**APA** (humanities/social sciences): title page, abstract, introduction (unheaded), body sections, discussion, references.

**Chicago/Turabian** (humanities): title page, abstract, introduction, chapters, conclusion, bibliography.

Pick the format the target venue expects; default to IMRaD if none is specified and the field is empirical, APA if it's social science with no named venue.

## Citation style is metadata for the renderer, not something you write by hand

Decide the citation style the finished paper should render in (APA 7th in-text `(Author, Year)`, IEEE numeric `[n]`, or footnotes) and record that decision at the top of `outline_formatted.md`. This choice governs how `research/citations.json` gets rendered later; it does not change how anyone drafts text now. Every agent in this pipeline, including whoever writes full prose from this outline, keeps using `{cite_<doi>}` placeholders inline, at the exact point of the claim, never a hand-rendered `(Author, Year)` or `[3]`. Rendering into the chosen style happens deterministically from `research/citations.json`, not by hand, and not here.

If a claim is real, the section needs it, and a genuine search still turns up nothing to cite, mark it inline as `{cite_MISSING: short description of what's needed}` rather than attaching a citation that doesn't check out or dropping the claim silently. State this rule explicitly for whoever drafts from this outline next: "cite with `{cite_<doi>}` only; use `{cite_MISSING: ...}` for a real claim that a genuine search could not source; never render a citation by hand." Say plainly what that marker is not: it is not a fourth citation style and not a way to ship an unsourced claim: `scripts/citations.py compile` refuses to render it and reports every instance by name, and `scripts/integrity.py` counts each one as a critical issue, so the gate stops before export rather than after. State the companion rule in the same place, because it governs the other half of every cited sentence: "every number and every finding attributed to a source must appear in that source's entry in `research/summaries.md`; `research/citations.json` carries bibliographic metadata only and holds no findings."

For table footnotes and data sources, the same rule applies: `*Source: {cite_<doi>}, {cite_<doi>}.*`, not a hand-formatted author/year string.

Reference list requirements once rendering happens: DOI link (`https://doi.org/...`) when available, consistent formatting across all entries, alphabetical by first author, complete metadata pulled straight from `research/citations.json`.

Language-specific adaptations: a German-language thesis keeps German punctuation conventions while the underlying citation structure (APA, IEEE, whichever was chosen) stays the same; note this explicitly if the target language isn't English.

## The venue format block: what later stages read back

Three later stages need decisions that only this stage makes, and they have no way to infer them from a finished draft. Stage 17 writes the abstract and needs its word range and keyword count. Stage 18 writes the title and needs the character limit. Stage 7 drafts each section and needs the word basis. None of them can read your reasoning, only the file, so record the decisions in one block at the top of `outline_formatted.md`, under the heading `## Venue format`, in exactly these keys:

```markdown
## Venue format

- Format family: IMRaD
- Target venue: [name, or "none specified"]
- Citation style: APA 7th
- Word basis: default scale (or: proportional, target 8,000 words)
- Abstract length: 150-250 words
- Keywords: 3-6
- Title limit: 100 characters
- Language: English
```

Write every key every time, even when the answer is a default, because a stage reading this block cannot tell a considered default from an omission. Where no venue was named and no limit applies, write the value you are choosing anyway ("Title limit: none specified, keep under about 100 characters"), not a blank. A stage that finds a key missing falls back to its own built-in number, which is the outcome this block exists to avoid.

## `research/brief.json`: the same decisions, in the form the gate can read

The venue format block above is prose for the stages that follow. `research/brief.json` is the machine half of the same job, and it exists because the block cannot be checked: a stage that quietly drafts to the wrong length still produces a file whose `## Venue format` header reads correctly. Write both.

This file records what the user asked for, and only that. Every value in it comes from a sentence in the brief, or, where the brief left the choice open, from the document type's own skeleton in `references/paper-types.md`. Omit any key the brief does not settle; each one is checked only when it is present, and an invented requirement fails a correct paper exactly as loudly as a real one fails a wrong paper.

```json
{
  "word_range": [2700, 3300],
  "min_references": 24,
  "abstract_max_words": 250,
  "required_sections": ["Introduction", "Methodology", "Discussion", "Conclusion", "References"]
}
```

How to read a brief into those four keys:

- **`word_range`** is the main text, abstract and reference list excluded, because a brief that caps them separately is counting them separately. "About 3,000 words" becomes a band around three thousand; ten percent either side matches the tolerance `scripts/integrity.py` has always applied to `--target`. "1200-1500 words" is already a band, so copy it. "Caps the main text at 6,000" is a ceiling, so record the ceiling and a floor low enough not to invent a length nobody asked for.
- **`min_references`** is whichever is higher of the number the brief states and the per-type floor under "Reference URLs: cite the actual source, not the tool you found it with" below. "A couple of dozen sources at least" is 24. "Thirty or more works" is 30. Record the number as stated; it is not adjusted later to match what the searching happened to yield.
- **`abstract_max_words`** is the cap the venue or the brief states ("the abstract at 200"), and otherwise the upper end of the `Abstract length` key you just recorded in the venue format block. The two always agree, because they are the same decision written twice.
- **`required_sections`** is the sections the brief names. Some briefs name them as sections; more name them as questions ("the questions members keep asking: does it push traffic onto boundary roads, what happens to air quality"). A question the user says they need answered is a section the paper needs to contain, and the honest way to record it is under the heading the paper will actually use.

Check the file parses before moving on: `python3 -c "import json;print(json.load(open('research/brief.json')))"`.

## The main claim carries forward unchanged

`outline.md` states the paper's main claim as `**Main claim:** <1-2 sentences>`. Copy that line verbatim into `outline_formatted.md`, directly below the `## Venue format` block. Do not paraphrase it, shorten it, fold it into a section's content plan, or drop it because it looks like Architect's business rather than Formatter's: Crafter reads `outline_formatted.md`, not `outline.md`, and ties the Discussion back to this exact sentence. A formatting pass that reorganizes everything else and silently loses this one line leaves Crafter with no claim to draft toward, and nothing in this pipeline reads `outline.md` again afterward to notice it is gone.

## Formatted structure

Manuscript specifications to record: font and size (Times New Roman 12pt or Arial 11pt by default, absent a venue requirement), line spacing (double-spaced by default, or 1.5 where the venue calls for it), margins (1-inch on all sides by default), page number placement, whether headings are numbered. Record the actual values chosen, not a blank waiting to be filled by a later stage; where no venue dictates otherwise, write the default down as the decision. Heading levels: level 1 bold/centered/title case, level 2 bold/left-aligned/title case, level 3 bold/indented/sentence case.

**Title:** bold, centered, roughly 14pt equivalent. Keep under 100 characters, or under whatever lower limit the venue enforces. Record the number in the `Title limit` key of the venue format block; stage 18 writes the title against that number and has no other way to learn it.

**Author block:** name(s), affiliation(s), email(s), ORCID if used.

**Abstract:** 150-250 words for most journals (narrower than the Architect's 250-300 word planning range; trim to fit). `agents/17-abstract.md` owns the abstract's internal structure, and states it as four labelled paragraphs plus a keywords line. Do not record a different set of parts here: stage 17 reads two keys out of this block, the length and the keyword count, so a structure written alongside them is discarded without anyone being told, and the two files then describe the same abstract differently for as long as nobody reads them together. Follow with 3-6 keywords. Record both numbers in the `Abstract length` and `Keywords` keys of the venue format block. Stage 17 writes the abstract against those keys and falls back to its own wider range only when they are absent, so a venue with a hard 150-word abstract limit is enforced here or nowhere.

**Numbered sections**, each inheriting its content plan from `outline.md` and adding format detail. The per-section word ranges below are the default scale, to be used when no specific total length has been given. They are not a second opinion competing with the proportional table under "Length targets"; that table is the model to scale from once a target total is known, exactly as `references/paper-types.md` describes under "Word budget: two real tables, and how they relate". Pick one basis per paper, say which one you picked in `outline_formatted.md`, and derive every section range from it. Whichever basis is used, each range is a band around a target, never a floor: the gate checks word count as the target plus or minus ten percent, so a section that overshoots fails it as surely as one that undershoots.

1. **Introduction** (800-1200 words at default scale, or 12 percent of a specified target): background and motivation, problem statement, research objectives as a numbered list, contributions as bullets, paper organization as a closing paragraph.
2. **Related work / literature review** (1500-2500 words at default scale, or 28 percent of a specified target): thematic subsections, each pairing narrative with a comparison table where useful (`Table 1: summary of related work`, columns: study, method, findings, limitations), closing with a gap-analysis paragraph.
3. **Methodology** (1000-1500 words at default scale, or 12 percent of a specified target): research design (paragraph plus a framework figure), data collection (narrative plus a dataset specification table), analysis procedures as numbered steps.
4. **Results** (1500-2000 words at default scale, or 28 percent of a specified target): descriptive statistics (text plus table), main findings (one subsection per finding, each with its own visualization), additional analyses.
5. **Discussion** (1500-2000 words at default scale, or 14 percent of a specified target): interpretation, comparison with prior work, theoretical implications, practical implications, limitations and future work stated as an honest assessment, not hedged into vagueness.
6. **Conclusion** (500-700 words at default scale, or 5 percent of a specified target, no subsections): restate problem and approach, summarize key findings, state the contribution plainly, suggest future directions.

Acknowledgments (funding, contributors) if applicable.

## Content quality checks

Before handing the outline downstream, confirm the plan actually asks for these, section by section, rather than assuming a well-formatted outline gets them for free: the abstract summarizes the whole paper, not just the introduction; the introduction states a clear, answerable research question; the methodology gives enough detail that someone else could replicate what was done; the results are presented objectively, without the interpretation that belongs in discussion; the discussion interprets the findings rather than restating them in different words; the conclusion emphasizes the contribution plainly rather than trailing off into a summary alone. A section plan that fails one of these is a formatting problem no amount of correct spacing and numbering will fix.

## Reference URLs: cite the actual source, not the tool you found it with

Reference links must resolve to an authoritative destination. Priority order: DOI (`https://doi.org/...`, always preferred when available), the journal's own URL, PubMed (`https://pubmed.ncbi.nlm.nih.gov/...`), arXiv/bioRxiv/medRxiv for preprints, or the publisher's own URL as a last resort.

Never use a discovery tool's link as the primary reference: not Semantic Scholar, not Google Scholar, not ResearchGate, not Academia.edu. These are how you found the paper, not where it lives; using them as the citation destination looks like the author couldn't locate the actual source, and the links break whenever the discovery tool changes its URL scheme. `research/citations.json` should already carry a DOI for anything that has one; if a reference in the draft points at a discovery-tool URL instead, flag and fix it:

```
Forbidden reference link found

Reference [12]: semanticscholar.org/paper/...
  replace with: https://doi.org/10.1016/j.cell.2023.01.002

Reference [23]: researchgate.net/publication/...
  replace with: https://doi.org/10.1038/s41586-022-05165-3
```

Minimum reference count: roughly 20 for an empirical paper, 50+ for a literature review, drawn from `research/citations.json`. The count is this stage's to set. The pool's temporal shape is not: `agents/01-scout.md` already balanced it under "Quality filtering," in that section's "Balance temporally" step, to roughly 60 percent from the last five years, 30 percent from the five years before that, and a handful of older foundational work. Record the shape stage 1 actually achieved rather than restating a different split here, because a pool built correctly to stage 1's numbers would then fail this stage's, and neither stage would be wrong. Note also that the split is relative to the current year and never a fixed window such as "2020-2024", which quietly ages into a demand for stale sources.

One shape constraint does belong here, because nothing earlier looks for it: no more than about 10 percent of the references drawn from the paper's own prior work, since a reference list leaning heavily on self-citation reads as building a case for the author rather than surveying the field.

## Table and figure numbering: no duplicates, ever

Maintain one global counter for tables and one for figures across the entire document; neither restarts at a new section or chapter.

```
Wrong:  "Table 1" appears in both Section 2 and Section 4
Wrong:  figure numbers restart at the beginning of each chapter
Wrong:  "Table 1" in the main text and a separate "Table 1" in the appendix

Right:  Section 2: Table 1, Table 2
        Section 3: Figure 1, Figure 2
        Section 4: Table 3, Figure 3
        Appendix:  Table A1, Table A2 (prefixed, not restarted)
```

Every table and figure must be referenced in the body text, and the reference must match the actual number: "as shown in Table 3" has to actually point at Table 3. If numbering changes during editing, update every cross-reference, not just the caption. If you find a duplicate:

```
Duplicate numbering found

"Table 1" appears at:
  line 145 (section 2.1)
  line 298 (section 4.2)

Renumber sequentially as Table 1, Table 2, ... Table N across the whole document
and update every place that refers to them by number.
```

## Style guide

**Tone.** Use: "the results indicate," "we observed," "this suggests." Avoid: "obviously," "clearly," "it's interesting that": these assert rather than demonstrate.

**Tense by section.** Introduction: present (current state of the field). Literature review: past (what others found). Methods: past (what was done). Results: past (what was found). Discussion: present (what it means now).

**Voice.** Active for clarity ("we analyzed the data"), passive where objectivity matters more than agency ("the data were analyzed"). Prefer active as the default; switch deliberately, not by habit.

## Length targets

This table is the proportional model, used when a specific total length is known: a venue's word limit, a thesis chapter's requirement, or a length the user asked for. It is not an alternative set of numbers competing with the per-section ranges under "Formatted structure"; those are the default scale, used when no total was specified. Read the column below as shares first and word counts second, and scale the shares to the actual target.

| Section | Words | Share |
|---|---|---|
| Abstract | 250 | 1% |
| Introduction | 2500 | 12% |
| Literature review | 6000 | 28% |
| Methodology | 2500 | 12% |
| Results | 6000 | 28% |
| Discussion | 3000 | 14% |
| Conclusion | 1000 | 5% |
| Total | 21000 | 100% |

Scale proportionally for a shorter target length; keep the literature review and results as the two largest sections regardless of overall scale, that balance is what makes a paper read as evidence-driven rather than opinion-driven.

The subtotals sum to 21,250 against the stated 21,000, roughly 250 words over. That is inside the noise of a proportional model and is not worth reconciling to the last word; treat the total as approximate and the shares as the real content of the table.

The share column is the half that does reconcile, and it has to, because the line above calls it the real content. Each share is its row's words over the 21,250 actually listed, and the seven round to exactly 100. Note that this puts the two largest sections at 28 percent rather than 29: 6,000 of 21,250 is 28.2 percent, and 29 is the share against a 21,000 base these rows do not sum to. Carrying 29 made the column total 102 under a Total row asserting 100, which is a table disagreeing with itself in the column it tells you to trust.

Each scaled number is the centre of a band, not a minimum. Write the range into `outline_formatted.md` as a range, and say so in words for whoever drafts from it, because a section instructed to treat its number as a floor will be padded past the gate's tolerance and fail the same check that a short section fails.

## When the target venue requires it

Data availability statement, conflict of interest statement, author contributions (multiple authors), funding statement, figure format (commonly PNG/TIFF at 300dpi minimum), tables in an editable format rather than as images, numbered equations. A submission package commonly also wants a cover letter, 3-5 highlight bullets, and a graphical abstract; include these only if the target venue actually asks for them, don't pad a generic outline with requirements nobody requested.

## Done when

- `outline_formatted.md` opens with a `## Venue format` block carrying every key listed above, filled in with a value rather than left blank: format family, target venue, citation style, word basis, abstract length, keyword count, title limit, and language.
- The `**Main claim:** <1-2 sentences>` line from `outline.md` appears in `outline_formatted.md`, verbatim, below the `## Venue format` block. `grep -c '^\*\*Main claim:\*\*' outline.md outline_formatted.md` reports the same nonzero count for both files.
- The word basis is stated once and every section range derives from it: either the default per-section scale or the proportional table scaled to a named target, never a mixture of the two.
- Every section from `outline.md` carries a section number, a word range stated as a range rather than a minimum, and explicit heading-level formatting.
- The table/figure numbering scheme is stated as one global counter per type, with the appendix-prefix convention noted.
- Reference URL priority is stated, and nothing in the draft points at a discovery-tool link as a primary citation.
- The draft text itself still uses `{cite_<doi>}` placeholders throughout; nothing has been hand-rendered into the chosen citation style yet.
- Manuscript specifications (font, spacing, margins) are recorded as the actual values chosen, not left blank.
- The content quality checks have been run section by section, not assumed from correct formatting.
- The reference pool's shape (recent versus foundational, self-citation share) is recorded alongside its minimum count.
- `research/brief.json` exists, parses, and carries a key for every number the brief actually stated and no key for anything it did not. Its `abstract_max_words` agrees with the `Abstract length` key in the venue format block, and its `min_references` is at or above the per-type floor.
- Whoever drafts from this outline has been told to use `{cite_MISSING: ...}`, never `[UNVERIFIED: ...]`, for a real claim a genuine search could not source.
