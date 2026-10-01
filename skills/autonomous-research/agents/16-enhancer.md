# Draft enhancer (optional)

This is an optional final pass over a complete draft. It adds a limitations section, future-research directions, and a glossary; it checks that tables and diagrams will survive PDF export; and it confirms that no `{cite_<doi>}` placeholder was lost along the way. It does not add new empirical claims, case studies, or word-count padding.

**Reads:** `full_draft.md`, `research/citations.json`, `outline_formatted.md`
**Writes:** `full_draft.md`

`outline_formatted.md` is read for one thing only: the `## Venue format` block at its top, which is where the citation style and the draft's language were recorded at stage 6. Nothing about the format decisions is re-made here.

## Skip this agent unless asked

The draft produced by the compose and validate stages is already complete: it has an introduction, body sections, a discussion, and a conclusion. Run this agent only when the user explicitly asks for a limitations section, future-research directions, a glossary, or a final export-safety pass. Do not run it by default, and do not treat "enhance" as a synonym for "make longer." A shorter draft that says what it needs to say is not a defect.

## What the draft looks like at this stage: placeholders, not a bibliography

The draft you are handed has no rendered references section, and it is not supposed to have one yet. Its sources live inline as `{cite_<doi>}` placeholders, one at each point of claim. The bibliography is rendered later, deterministically, by `scripts/citations.py compile`, which runs at the gate after stage 18: it reads the placeholders, looks each DOI up in `research/citations.json`, and emits the references section in the chosen citation style.

That ordering has three consequences for this pass, and getting them wrong is the most damaging thing this agent can do.

1. Do not look for a references section. Not finding one is the expected state, not an error, and not a reason to stop.
2. Do not write one. Hand-writing a bibliography, or a partial one, produces entries the compile step did not generate and the integrity check cannot match to any placeholder; it will be flagged, and the file will have to be repaired by hand.
3. Do not convert a placeholder into a rendered marker. `{cite_10.1234/example.2023}` stays exactly as it is. Turning it into `[3]` or `(Smith, 2023)` silently breaks the mapping the compile step depends on, and nothing downstream will tell you.

If the draft does contain something that looks like a references section, that is a defect from an earlier stage, not something to preserve or extend. Leave it untouched, add whatever was asked for, and say so in your output to the user.

Two other things are also missing at this stage, and for the same reason: this agent runs before stage 17 writes the abstract and before stage 18 writes the title. So the draft you are handed has no abstract and no title, and neither absence is an error. Do not write either one. If the draft carries an abstract placeholder, leave the placeholder exactly where it is; stage 17 replaces it.

## Non-negotiable: no new empirical claims

Everything you add in this pass must trace to content already in `full_draft.md` or to a source already in `research/citations.json`. That means:

- No invented statistics, percentages, sample sizes, p-values, effect sizes, or confidence intervals.
- No invented case studies ("Company X achieved a 23% improvement") and no invented projections, scenarios, or forecasts presented as findings.
- No new bibliography, reading list, or "additional resources" section listing books, tools, or URLs that are not sources already present in `research/citations.json` (which itself only holds DOIs checked via `scripts/sources.py verify`).
- No mathematical formulations, proofs, or theoretical frameworks beyond what the draft's own argument already establishes. The one set of equations the pipeline itself computes, the `{equations:evidence-index}` placeholder from stage 4.5, stays exactly where it is; do not add to it, restate it or move it.
- Any sentence you add that leans on a source needs a real `{cite_<doi>}` placeholder pointing at a DOI already present in `research/citations.json`. Never hand-write `[3]` or `(Smith, 2020)`, and never introduce a placeholder for a source that is not in the database.

If a legitimate addition would require a number, a result, or a claim you cannot trace this way, do not write it. Say in prose that the question is open, or drop the sentence.

## Never claim verification you have not done

Do not write "all citations are verified," "no hallucinations," "fact-checked," or any similar accuracy guarantee, anywhere in the draft, its metadata, or your own output to the user. A resolved DOI in `research/citations.json` proves the cited work exists. It does not prove the work supports the sentence citing it. State what was done ("citations checked against Crossref and DataCite"), never what it proves.

## Language consistency

Determine the draft's language from its existing headings before writing anything. Every section you add or rename must be in that language, including headings, table captions ("Table" / "Tabelle" / "Tabla" / "Tableau"), figure captions, and any section metadata you touch. Do not mix languages within one document. If the draft is in German, "## Limitations" is wrong; "## Einschränkungen" is correct, and it must stay that way in the finished file, not just in your draft of it.

The section headings this agent can introduce, in the four languages this pipeline names elsewhere:

| English | German | Spanish | French |
|---|---|---|---|
| Limitations | Einschränkungen | Limitaciones | Limitations |
| Future Research Directions | Zukünftige Forschungsrichtungen | Direcciones de Investigación Futura | Directions de Recherche Futures |
| Glossary | Glossar | Glosario | Glossaire |
| Table | Tabelle | Tabla | Tableau |
| Figure | Abbildung | Figura | Figure |

Before finishing, self-check a non-English draft by grepping the file for the English heading you should not have written. A hit means the section was added in the wrong language and needs fixing before this pass is done:

```bash
grep -n "^## Limitations\b" full_draft.md
grep -n "^## Future Research" full_draft.md
grep -n "^## Glossary\b" full_draft.md
grep -n "\bTable [0-9]" full_draft.md
grep -n "\bFigure [0-9]" full_draft.md
```

On a German, Spanish, or French draft, every one of those five should come back empty; a hit is the English word left behind in a non-English section. On an English draft, all five are expected to hit and the check does not apply.

## What to add

Add only the sections below, and only the ones the user asked for. Each is optional independently.

### 1. Limitations

One new top-level section, placed after the discussion and before the conclusion. Two to four subsections, each two to three paragraphs, drawn from what the draft's own methodology and evidence actually support. Four candidate axes, each with what to actually discuss inside it; include a subsection only when the draft's own argument genuinely supports something under that axis:

- **Methodological limitations.** Sample size and how sources were selected; what the measurement or evidence base can and cannot show; validity and reliability constraints the draft's own methodology section already implies.
- **Scope and generalizability.** Contextual specificity: what setting, discipline, or evidence base the draft actually drew on, stated plainly rather than hedged into meaninglessness. Populations, regions, or contexts the draft's evidence does not cover, named rather than gestured at.
- **Temporal and contextual constraints.** Whether the field is moving quickly enough that findings may date faster than usual, only when the draft's own literature review shows that pace (a wave of citations from the last two years is evidence of this; a field that has looked the same for a decade is not).
- **Theoretical and conceptual limitations.** Alternative perspectives, frameworks, or interpretations the draft did not take up, named specifically rather than as a generic "other views exist" disclaimer, and only when the draft's own discussion already gestures at one.

Do not pad this to a fixed subsection count or word target. A draft with two real limitations gets two subsections, not four manufactured ones, and an axis with nothing genuine to say gets skipped rather than filled with a paragraph of hedging.

### 2. Future research directions

One new top-level section after Limitations, before the conclusion. Three to five directions, each a short paragraph, each grounded in a gap the draft itself identifies (in the literature review, the discussion, or the limitations you just wrote). Do not invent directions unrelated to the draft's actual argument, and do not force a specific count.

Five recurring shapes a genuine direction tends to take, offered as a checklist for what to look for in the draft, not a template to fill in regardless of fit. Use only the ones the draft's own gaps actually support, in the draft's own terms:

- Empirical validation or larger-scale testing of a claim the draft currently supports only with a small or narrow evidence base.
- Longitudinal or comparative study, when the draft's evidence is cross-sectional or single-context and a question about change over time or across contexts is left open.
- Technological or methodological integration, when the draft names a tool, technique, or method that could extend the work but that none of the cited sources have applied yet.
- Policy or implementation translation, when the draft's discussion already raises a practical or policy implication without saying how it would be carried out.
- A direction specific to the draft's own domain, arising from a gap the literature review or discussion names but does not resolve.

A direction that does not trace to one of these shapes can still be legitimate if it traces directly to the draft's own text; the five above are where to look first, not a ceiling.

### 3. Glossary of terms

An appendix, placed after the conclusion, at the end of the file. The compiled references section is appended after it later, so leave the glossary as the last thing in the file when you finish. An alphabetical list of technical terms the draft actually uses, each with a one- to two-sentence definition, typically 20 to 30 terms for a full-length paper and fewer for a shorter one. This carries no fabrication risk: it defines vocabulary already in the text. Include a term only if the draft uses it; do not introduce new terminology here. Do not define a term using another term also being defined in the glossary ("X: a form of Y" next to "Y: a form of X" tells the reader nothing); write each definition so it stands on its own without pointing to a second glossary entry to complete the meaning.

### 4. Synthesis table (only if the draft already compares sources)

If the draft's body already discusses several cited sources on the same axis (for example, several studies' reported outcomes on the same intervention), you may add one table that lays out what those sources already say, each cell citing its source with `{cite_<doi>}`. This is a restatement of claims already in the draft's prose, in table form, not new analysis. Do not add a table that introduces a metric, comparison, or row that is not already stated in the draft's text.

Four recurring shapes this table tends to take, useful for deciding which axis the table should organize around once you've confirmed the draft actually supports a table at all:

- **Comparative analysis.** Several sources' positions or approaches lined up against the same set of dimensions.
- **Quantitative metrics.** Several sources' reported measurements on the same outcome, restated from the prose rather than recomputed.
- **Framework implementation.** Phases, steps, or components of a process the draft's methodology or theory section already lays out in prose.
- **Case-study data.** Several sources' findings about the same kind of case or application, restated side by side.

Pick the one shape that matches what the draft's prose already does; do not build a table that mixes two of these into one, and do not build one that fits none of them.

### 5. One conceptual diagram (only if the draft already describes a framework in prose)

If the draft's methodology or theoretical framework section already describes a structure or process in prose, you may add one ASCII diagram that visualizes it. Use only ASCII characters (`+ - | / \ # * = > < v ^` and alphanumerics and spaces); Unicode box-drawing characters break some PDF export pipelines. Do not add a diagram that introduces a step, relationship, or component the prose does not already describe.

Box-and-arrow template, adapt the labels to the draft's own framework rather than copying these words:

```
+------------------------------------------+
|               MAIN CONCEPT               |
+--------------------+---------------------+
                     |
         +-----------+-----------+
         |                       |
   +-----v-----+           +-----v-----+
   | ELEMENT A |           | ELEMENT B |
   +-----+-----+           +-----+-----+
         |                       |
         +-----------+-----------+
                     |
              +------v------+
              |   OUTCOME   |
              +-------------+
```

Alternative styles, all still ASCII-only: boxes as `+---+`, `*---*`, or `#---#`; a horizontal line as `-`; a vertical line as `|`; an arrow as `-->`, `==>`, or a bare `v` / `^` marking the direction of flow; a diagonal connector as `/` or `\`.

Before outputting any diagram, run this three-step check rather than eyeballing it:

1. Confirm it contains only these characters: `+ - | / \ # * = > < v ^`, plus letters, digits, and the spaces and line breaks that lay out the rows.
2. Confirm it does not contain Unicode box-drawing characters (`┌ ─ │ └ ┬ ▼ ◄ ►` and the rest of that block) or any character above code point 127.
3. Confirm every box is square, by counting rather than by eye. For each box, its
   top border, its text row and its bottom border must be the same number of
   characters, and the `|` on each text row must sit in the same column as the
   `+` at each end of the borders above and below it. A box whose top border is
   one character short of its text row is the most common way an ASCII diagram
   goes wrong, and it is invisible until someone opens the file in a different
   editor.

The template above was checked against all three steps, not just the first two:
every character in it is one of `+`, `-`, `|`, `v`, a letter, a space, or a line
break; it contains no Unicode box-drawing character; and all three of its boxes
have matching border and text-row widths with their pipes on their corners.

## Citation placeholders: preserve every one of them

The `{cite_<doi>}` placeholders scattered through the draft are what the bibliography will be built from. Every one that disappears in this pass is a source that silently vanishes from the finished paper, taking the support for whatever sentence carried it. Losing them is the single most damaging failure this pass can produce, and it is quiet: the prose still reads fine, and the compiled references section simply comes out shorter than it should.

Before you write anything else:

1. Count the distinct DOIs appearing in `{cite_<doi>}` placeholders across the whole file, and count the total number of placeholder occurrences. Both numbers matter: distinct DOIs is how many sources the paper draws on, occurrences is how many claims are supported.

```bash
set -o pipefail   # without this, a missing file still prints 0 and exits 0
grep -o '{cite_[^}]*}' full_draft.md | sort | uniq -c | sort -rn
grep -o '{cite_[^}]*}' full_draft.md | sort -u | wc -l
grep -o '{cite_[^}]*}' full_draft.md | wc -l
```

Zero is never a correct answer here. A draft that reached stage 16 has citations
in it, so a count of zero means the file is missing or its name is wrong, not
that the paper has no sources. Without `pipefail` the exit status of each line
belongs to `wc`, which succeeds on empty input, so the broken case and the
alarming case both print a clean 0 and neither is distinguishable from a real
answer. That turns the check below into a comparison of 0 against 0, which
passes.

2. Note both counts before editing.
3. After you finish adding sections, run the same commands and confirm neither count has dropped. A count that rose is expected if you added a synthesis table or a cited sentence. A count that fell means an edit swallowed a placeholder; find it and restore it before finishing.

If your edit would truncate the file (for example, because you are close to an output limit), stop adding new appendix content rather than letting the file end early. A truncated draft loses every placeholder past the cut. If you have to cut something to fit, cut the glossary or the synthesis table, and never let the file end anywhere but where it ended before this pass.

## Export-safety formatting

If you add tables, keep them renderable:

- Header cells: no more than about 30 characters.
- Data cells: no more than about 50 characters.
- A cell that interprets or annotates a data cell (an "Impact" or "Significance" column, say): no more than about 100 characters.
- 100 characters is the absolute ceiling for any cell in the table, interpretation column or not.
- Each cell must contain unique content; do not repeat the same text across cells to fill space.
- Any longer explanation belongs in a paragraph before the table or a note after it, never inside a cell.

Correct, every cell inside the ceilings above:

```markdown
| Dimension | Approach A | Approach B | Impact |
|---|---|---|---|
| Speed | Fast, days | Slow, weeks | High |
| Cost | Low | High | Medium |
```

Incorrect, a data cell carrying what should be a paragraph:

```markdown
| Dimension | Mechanism |
|---|---|
| Impact | This cell explains every detail of the mechanism at length, well past a hundred characters, which is exactly the kind of cell that bloats the file and breaks PDF export |
```

The escape hatch for that second case: write one or two paragraphs of explanation before the table, keep the cell to a short label, and put any note that does not fit a cell in a footnote after the table. Never write the long version into the cell itself.

If you add a diagram, use only ASCII characters as described above and run the three-step validation check before finishing; do not rely on eyeballing it.

## Optional: export metadata

If the user wants YAML frontmatter for PDF or DOCX export, add only fields that describe the document, not fields that grade it or promote the tool that produced it:

```
---
title: ""
date: "[Draft date]"
language: "[the Language key from outline_formatted.md]"
citation_style: "[the Citation style key from outline_formatted.md]"
---
```

Two of those fields come from the venue format block in `outline_formatted.md` rather than from the draft, because the draft does not carry them: the language is recorded there and the citation style is a decision stage 6 made, not something readable from text that is still full of `{cite_<doi>}` placeholders.

The `title` field stays empty here, and that is deliberate. Stage 18 writes the title after this pass, so any title written now would be invented. Leave the key present and its value blank, and say in your output to the user that the title is filled in after stage 18. If the user asked for frontmatter and no venue format block exists, write the keys with empty values rather than guessing them, and name the missing block.

Do not add a quality score, a "citations verified" claim, a word- or page-count boast, marketing copy about the system that generated the draft, or a call to action. None of that describes the document, and the citation-verification claim specifically violates the rule above.

## Output structure

The finished file keeps every original section unchanged, in its original order, and appends only what you were asked to add:

```markdown
## Introduction
[unchanged]

## Literature Review
[unchanged]

## Methodology
[unchanged]

## Results / Analysis
[unchanged]

## Discussion
[unchanged]

## Limitations
[new, if requested]

## Future Research Directions
[new, if requested]

## Conclusion
[unchanged]

## Glossary
[new, if requested]
```

The file ends there. No references section appears in this diagram because none exists in the draft at this stage; `scripts/citations.py compile` appends it later, after stage 18, from the `{cite_<doi>}` placeholders left inline throughout the text above.

Do not rename existing section headers to something generic like "## Content." Do not shorten or rewrite existing sections; this pass only adds, it does not edit prior material.

## Done when

- Every section that existed in `full_draft.md` before this pass still exists, unchanged, in the same order.
- The count of distinct `{cite_<doi>}` DOIs and the count of placeholder occurrences are both at least what they were before this pass, checked by running the counts again rather than by impression.
- No `{cite_<doi>}` placeholder was converted into a rendered marker, and no references section, bibliography or reading list was hand-written; the draft still ends where it ended before this pass.
- Every new sentence that states a fact traces either to the draft's existing text or to a `{cite_<doi>}` placeholder for a DOI present in `research/citations.json`.
- No invented numbers, case studies, projections, or external resource lists appear anywhere in the new material.
- No sentence anywhere in the file claims that citations are verified, fact-checked, or free of hallucination.
- The whole file is in one language, matching the language the draft was in before this pass and the `Language` key in `outline_formatted.md`; on a non-English draft, the grep self-check for the five English headings came back empty.
- No title and no abstract were written, and any abstract placeholder is still in place for stage 17.
- If export frontmatter was added, its `title` is empty and its language and citation style were copied from the venue format block rather than inferred.
- Any table added respects the cell-length ceilings above (30 header, 50 data, 100 interpretation, 100 absolute), and no two cells repeat the same content; any diagram added uses only the characters named above, and the three-step validation check was actually run against it rather than eyeballed.
- Any glossary added stays within roughly 20 to 30 terms for a full paper, is alphabetical, and no definition depends on a second glossary entry to complete its meaning.
- Any future-research direction added traces to a gap the draft's own text names, whether or not it matches one of the five recurring shapes above.
