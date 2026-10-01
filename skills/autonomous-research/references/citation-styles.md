# Citation styles

What each of the six styles actually produces, so you can choose one, check the output, and answer a question about it without reading the compiler. Every rendering shown below was produced by running `scripts/citations.py compile` on a fixture database, and pasted here unchanged.

Read this when you are choosing a style at stage 6, or when you are looking at a compiled bibliography and deciding whether it is right.

## The rule that comes before everything else

Never write a rendered citation marker while drafting. Not `[3]`, not `(Smith, 2020)`, not a reference list entry, not for any style, not "just this one" because a style looks awkward. You write `{cite_<doi>}` at the exact point of the claim, and `scripts/citations.py compile` turns every one of them into a marker and builds the bibliography beneath the text by dictionary lookup.

There is no hand-rendering pass in this pipeline and no style that needs one. All six styles are implemented, all six are accepted by `--style`, and all six compile without a manual step. A hand-written marker is the specific failure that makes this output unusable: it is invisible in the markdown, it does not renumber when the text moves, and it survives into the finished document pointing at the wrong entry.

```bash
python3 scripts/citations.py compile full_draft.md -d research/citations.json --style apa -o final.md
```

The command appends a `## References` heading and the bibliography to the end of the output file. If a placeholder's DOI is not in the database, the command exits 1 and names every offender at once:

```
Error: Citation placeholder(s) not found in the database: {cite_10.5555/nope.1}, {cite_10.5555/nope.2}
```

That error means the database is missing an entry, which is stage 4's problem. It does not mean the placeholder should be deleted, and it does not mean a DOI should be invented to satisfy it.

The second way compile refuses is the resolution gate. Nothing renders unless its DOI came back `resolved`:

```
Error: Refusing to render citation(s) whose DOI is not resolved at Crossref or DataCite: 10.48550/arxiv.2401.01234 (unknown), 10.5555/env.2022.8.55 (unknown). Run: python3 scripts/citations.py verify -d <database>  and remove or replace any source that does not resolve.
```

Do exactly what it says. Run `verify`, then remove or replace the sources that still do not resolve. Editing the `verified` field by hand to get past the gate defeats the one claim this pipeline is entitled to make about its bibliographies.

The third way compile refuses runs before either of the other two. If the draft still carries `{cite_MISSING: <description>}` anywhere, compile checks for that first, before it even opens the database, and refuses to write any output:

```
Error: Refusing to compile 2 unsourced claim(s) marked {cite_MISSING: ...} by the drafter: line 12: the disposable soma theory predicts a trade-off between repair and reproduction; line 47. For each one: find a source with python3 scripts/sources.py find "<topic>" --json > new.json, merge it into the database with python3 scripts/citations.py build new.json -o research/citations.json, and replace the marker with {cite_<doi>} -- or cut the claim. It cannot ship marked.
```

That marker is the drafter admitting, in the draft itself, that a claim has no source yet. It is honest, and it is a hard stop. `integrity.py` enforces the same rule on an already-compiled draft: checking for `{cite_MISSING: ...}` is the first of its checks, and every occurrence it finds is one critical issue, reported with the drafter's own description. Neither script accepts the marker as a way to ship an unsourced claim wearing something that merely looks like a citation. Clear it the way stage 4 documents: find a real source and get it into the database, or cut the claim, then compile again.

## The six styles

| Style | `--style` value | In-text form | Bibliography order |
|---|---|---|---|
| APA 7th | `apa` | author-year, `(Chen et al., 2023)` | alphabetical by first author's family name |
| MLA 9th | `mla` | author only, `(Chen et al.)` | alphabetical by first author's family name |
| Chicago author-date | `chicago` | author-year, `(Chen et al., 2023)` | alphabetical by first author's family name |
| Harvard | `harvard` | author-year, `(Chen et al., 2023)` | alphabetical by first author's family name |
| IEEE | `ieee` | numeric, `[1]` | numeric, by first appearance in the text |
| Vancouver | `vancouver` | numeric, `[1]` | numeric, by first appearance in the text |

Any other value is rejected before anything is written:

```
citations.py compile: error: argument --style: invalid choice: 'acs' (choose from 'apa', 'chicago', 'harvard', 'ieee', 'mla', 'vancouver')
```

Numeric styles number each unique DOI the first time it appears in the compiled text and reuse that number everywhere else. The number comes from reading order, never from anything inside the DOI string, so a DOI of any shape numbers correctly.

## How the compiler treats a source

Uniformly. The reference formatters do not branch on a record's `type`: a journal article, a book, a report and a preprint all go through the same per-style template. What comes out is authors, title, venue when the record has one, year, and the DOI link, arranged in that style's punctuation.

The practical consequences, which are the same in all six styles:

- **Venue is printed whenever the record has one, and skipped when it does not.** A book with no `venue` renders as author, title, DOI, with no gap and no placeholder text.
- **The DOI link is printed in every style.** Nothing needs adding by hand.
- **A missing year renders as `n.d.`** in the marker and the reference entry alike. That is the honest output for a record with no year, and the fix is to get the year into the database at stage 4, not to type one into the compiled file.
- **Volume, issue and page numbers are never printed**, because the source lookup does not retrieve them. Neither is the publisher. A journal reference gives the journal name and the DOI, and stops there.
- **A preprint is not labelled as a preprint** by any style. Where a preprint carries an argument in the text, say so in the prose; the reference entry will not say it for you.
- **Journal names are printed in full**, never abbreviated. Vancouver conventionally uses NLM abbreviations; this pipeline has no abbreviation table and does not guess one.

None of that is a reason to edit the compiled output. If a target venue requires page ranges or NLM abbreviations, that is a formatting pass for whoever submits the paper, done once on the final document, and it happens after this pipeline is finished rather than inside it.

## The same four sources, rendered in each style

One fixture database, four sources: a three-author journal article, a two-author journal article, a single-author book with no venue, and a single-author preprint. Same draft text compiled six times. This is real output.

### APA 7th

```
Governance structure predicts project survival (Chen et al., 2023).
Maintainer turnover is the mechanism most often named (Okafor & Lindqvist, 2022).
The book-length treatment sets out the same argument (Nguyen, 2021),
and a recent preprint proposes a measurement protocol (Kowalski, 2024).

## References

Chen, M., Alvarez, R., & Park, J. H. (2023). Adaptive governance structures in open-source infrastructure projects. *Journal of Digital Commons*. https://doi.org/10.5555/jdc.2023.14.3.210

Kowalski, P. (2024). Measuring sustainability in open-source ecosystems. *arXiv*. https://doi.org/10.48550/arxiv.2401.01234

Nguyen, L. (2021). Open infrastructure governance. https://doi.org/10.5555/oig.2021.001

Okafor, A., & Lindqvist, S. (2022). Maintainer turnover and long-term project survival. *Environmental Informatics*. https://doi.org/10.5555/env.2022.8.55
```

Family name then initials, ampersand before the last author, venue in italics.

### MLA 9th

```
Governance structure predicts project survival (Chen et al.).
Maintainer turnover is the mechanism most often named (Okafor and Lindqvist).
The book-length treatment sets out the same argument (Nguyen),
and a recent preprint proposes a measurement protocol (Kowalski).

## References

Chen, Mei, et al. "Adaptive governance structures in open-source infrastructure projects." *Journal of Digital Commons*, 2023. https://doi.org/10.5555/jdc.2023.14.3.210.

Kowalski, Piotr. "Measuring sustainability in open-source ecosystems." *arXiv*, 2024. https://doi.org/10.48550/arxiv.2401.01234.

Nguyen, Linh. "Open infrastructure governance." 2021. https://doi.org/10.5555/oig.2021.001.

Okafor, Ada, and Sven Lindqvist. "Maintainer turnover and long-term project survival." *Environmental Informatics*, 2022. https://doi.org/10.5555/env.2022.8.55.
```

The MLA marker carries no year, which is correct for MLA and which the integrity check knows about. Given names are spelled out rather than reduced to initials.

### Chicago author-date

```
Governance structure predicts project survival (Chen et al., 2023).
Maintainer turnover is the mechanism most often named (Okafor and Lindqvist, 2022).
The book-length treatment sets out the same argument (Nguyen, 2021),
and a recent preprint proposes a measurement protocol (Kowalski, 2024).

## References

Chen, Mei, Rosa Alvarez, and Jin Ho Park. 2023. "Adaptive governance structures in open-source infrastructure projects." *Journal of Digital Commons*. https://doi.org/10.5555/jdc.2023.14.3.210.

Kowalski, Piotr. 2024. "Measuring sustainability in open-source ecosystems." *arXiv*. https://doi.org/10.48550/arxiv.2401.01234.

Nguyen, Linh. 2021. "Open infrastructure governance." https://doi.org/10.5555/oig.2021.001.

Okafor, Ada, and Sven Lindqvist. 2022. "Maintainer turnover and long-term project survival." *Environmental Informatics*. https://doi.org/10.5555/env.2022.8.55.
```

This is the author-date variant. Chicago's notes-and-bibliography variant, with footnotes, is a different system and is not one of the six; if a venue asks for footnote citations, pick the closest of the six and say which one was used, rather than hand-building footnotes.

### Harvard

```
Governance structure predicts project survival (Chen et al., 2023).
Maintainer turnover is the mechanism most often named (Okafor and Lindqvist, 2022).
The book-length treatment sets out the same argument (Nguyen, 2021),
and a recent preprint proposes a measurement protocol (Kowalski, 2024).

## References

Chen, M., Alvarez, R. and Park, J. H. (2023) 'Adaptive governance structures in open-source infrastructure projects'. *Journal of Digital Commons*. Available at: https://doi.org/10.5555/jdc.2023.14.3.210.

Kowalski, P. (2024) 'Measuring sustainability in open-source ecosystems'. *arXiv*. Available at: https://doi.org/10.48550/arxiv.2401.01234.

Nguyen, L. (2021) 'Open infrastructure governance'. Available at: https://doi.org/10.5555/oig.2021.001.

Okafor, A. and Lindqvist, S. (2022) 'Maintainer turnover and long-term project survival'. *Environmental Informatics*. Available at: https://doi.org/10.5555/env.2022.8.55.
```

Harvard is a family of house styles rather than one specification, and this is one common British-university variant: initials, single quotation marks around the title, `Available at:` before the link. If a venue names a specific guide, expect small punctuation differences from what it asks for, and treat that as a submission-time formatting pass rather than something to correct in the draft.

### IEEE

```
Governance structure predicts project survival [1].
Maintainer turnover is the mechanism most often named [2].
The book-length treatment sets out the same argument [3],
and a recent preprint proposes a measurement protocol [4].

## References

[1] Chen, M., Alvarez, R., Park, J. H., "Adaptive governance structures in open-source infrastructure projects," *Journal of Digital Commons*, 2023. https://doi.org/10.5555/jdc.2023.14.3.210

[2] Okafor, A., Lindqvist, S., "Maintainer turnover and long-term project survival," *Environmental Informatics*, 2022. https://doi.org/10.5555/env.2022.8.55

[3] Nguyen, L., "Open infrastructure governance," 2021. https://doi.org/10.5555/oig.2021.001

[4] Kowalski, P., "Measuring sustainability in open-source ecosystems," *arXiv*, 2024. https://doi.org/10.48550/arxiv.2401.01234
```

Numbered in reading order, so the bibliography order follows the text rather than the alphabet. The DOI is printed on every entry.

### Vancouver

```
Governance structure predicts project survival [1].
Maintainer turnover is the mechanism most often named [2].
The book-length treatment sets out the same argument [3],
and a recent preprint proposes a measurement protocol [4].

## References

1. Chen, M., Alvarez, R., Park, J. H. Adaptive governance structures in open-source infrastructure projects. Journal of Digital Commons. 2023. https://doi.org/10.5555/jdc.2023.14.3.210

2. Okafor, A., Lindqvist, S. Maintainer turnover and long-term project survival. Environmental Informatics. 2022. https://doi.org/10.5555/env.2022.8.55

3. Nguyen, L. Open infrastructure governance. 2021. https://doi.org/10.5555/oig.2021.001

4. Kowalski, P. Measuring sustainability in open-source ecosystems. arXiv. 2024. https://doi.org/10.48550/arxiv.2401.01234
```

Same numbering rule as IEEE. No italics, no quotation marks, journal name spelled out in full.

## Author truncation, verified per style

Compiled from a fixture with one, two, three, four and eight authors, all sharing the first author `Aalto, Kaisa`.

| Style | Marker with 1 | Marker with 2 | Marker with 3 or more | Reference entry |
|---|---|---|---|---|
| APA | `(Aalto, 2020)` | `(Aalto & Baptiste, 2020)` | `(Aalto et al., 2020)` | all authors up to 7; with 8 or more, the first 6, then `... &`, then the last |
| MLA | `(Aalto)` | `(Aalto and Baptiste)` | `(Aalto et al.)` | 1 author in full; 2 as `Family, Given, and Given Family`; 3 or more as `Family, Given, et al.` |
| Chicago | `(Aalto, 2020)` | `(Aalto and Baptiste, 2020)` | `(Aalto et al., 2020)` | every author listed, however many, with `and` before the last |
| Harvard | `(Aalto, 2020)` | `(Aalto and Baptiste, 2020)` | `(Aalto et al., 2020)` | up to 3 listed; 4 or more collapses to `Aalto, K. et al.` |
| IEEE | `[1]` | `[1]` | `[1]` | up to 3 listed; 4 or more collapses to `Aalto, K., et al.` |
| Vancouver | `[1]` | `[1]` | `[1]` | up to 3 listed; 4 or more collapses to `Aalto, K., et al.` |

Two things to notice. The author-year markers switch to `et al.` at three authors in all four author-year styles. The reference entries diverge sharply: Chicago lists eight authors in full where Harvard shows one and `et al.`, and that is the behaviour, not a bug to work around.

The eight-author APA entry, in full, since the truncation form is easy to mistype when checking one by hand:

```
Aalto, K., Baptiste, L., Contreras, I., Duarte, P., Eriksen, M., Farouk, N., ... & Haddad, Y. (2020). Study with 8 authors. *Journal of Tests*. https://doi.org/10.5555/t.8
```

## Choosing a style

If the user named a style, or the target venue names one, use that and stop reading here. Otherwise, pick by discipline and say in one line which you picked and why, so the choice is visible and easy to overrule:

| Field | Style | Why |
|---|---|---|
| Psychology, education, social sciences, much of the life sciences | `apa` | the default expectation in those literatures |
| Literature, languages, film, philosophy, most humanities | `mla` | markers carry no year, which suits close-reading prose |
| History, area studies, some social sciences | `chicago` | author-date is the variant used in article-length work |
| UK and Australian business, management, social policy | `harvard` | the common expectation, though house variants differ |
| Engineering, computer science, electronics | `ieee` | numeric markers keep dense technical prose readable |
| Medicine, clinical research, biomedical science | `vancouver` | the ICMJE convention those journals expect |

A numeric style keeps prose readable when a sentence carries four supporting sources; an author-year style lets a reader place a study without looking down the page. If neither consideration decides it, `apa` is the safest default across mixed or interdisciplinary work.

Whichever you pick, compile with that one style everywhere. Compiling one section in `ieee` and another in `apa` produces a document with two incompatible numbering systems, and it is not visible until someone reads the rendered output.

## What the verification states mean for what may be printed

Every record in `research/citations.json` carries a `verified` field, one of four values, set by `citations.py verify`. The distinction matters to this file because it governs what may appear in a bibliography at all.

- **`resolved`.** Crossref or DataCite returned the record. The work exists at that DOI, so the reference entry can be printed. That is the entire claim. It establishes nothing about whether the work supports the sentence citing it; that question belongs to stage 11 and no amount of correct formatting substitutes for it.
- **`absent`.** Both agencies returned 404. Nothing may be printed for it. Remove the entry and the placeholders that point at it, and re-source the claim at stage 1. Never substitute a similar-looking DOI.
- **`unknown`.** A network or rate-limit failure, so the DOI's status is genuinely undetermined. Retry, and if it stays unknown, the source cannot carry an inline marker. Name the work in prose and in the limitations section instead of printing a citation the pipeline could not check.
- **`invalid`.** Malformed or empty. Handled like `absent`.

Sources with no DOI at all never enter the database and never become placeholders. They are cited by name in the prose, and the limitations section says plainly that nothing checked them.

The strongest true statement about a compiled bibliography is that every printed DOI resolved at Crossref or DataCite and that every marker maps one-to-one onto an entry. Do not upgrade that into a claim about accuracy: no wording that implies the citations were checked for correctness, that the sources support the sentences citing them, or that the paper contains no errors is available to this pipeline, in the reference list or anywhere else.

## Known limits, so nobody goes looking for a bug that is not there

- Alphabetical bibliographies sort on the first author's family name only. Two entries whose first authors share a surname are not ordered relative to each other by year or title.
- No style prints volume, issue, pages or publisher, because the source lookup does not retrieve them.
- Book chapters keep their book title in the `venue` field and render like any other source; editors and page ranges have nowhere to go. The BibTeX export does distinguish them: `type: "book-chapter"` becomes `@incollection` with the book title as `booktitle`, so a chapter exported to LaTeX carries more structure than the same chapter rendered to markdown.
- A record with no year renders `n.d.` where the year would go, which in some styles leaves the sentence reading `n.d..` with the style's own trailing period. Fix the metadata rather than the compiled file.
- Everything the compiler does is a dictionary lookup over `research/citations.json`. If a reference looks wrong, the record is wrong; correct it at stage 4 and recompile. Editing `final.md` puts the document and the database out of sync, and the next compile silently discards the edit.
