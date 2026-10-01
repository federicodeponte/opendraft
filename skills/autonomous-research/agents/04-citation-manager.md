# Citation manager

Builds the one authoritative, DOI-checked citation database the rest of the pipeline points at. Every `{cite_<doi>}` placeholder anywhere in this project's output is only as trustworthy as this file: get the database wrong and every downstream agent inherits the error silently.

Two of the three things this stage does are bookkeeping, and the scripts do those. The third is judgement, and only you can do it: deciding what counts as a citable source, what to do when a DOI does not resolve, and what to say about the sources that have no DOI at all.

**Reads:** `research/sources.json` (the machine artifact stage 1 wrote), `research/sources.md`, `research/summaries.md`, `research/gaps.md`
**Writes:** `research/citations.json` (built by the script, never by hand), `research/citation-notes.md` (the hand-written annotations that no script can produce)

**On a re-run only.** Nothing in the list above is optional and nothing else is required for the first pass. Later in the project this stage is worth running again, once more sources exist or once text has been drafted, and a re-run may additionally be pointed at files that did not exist yet on the first pass, such as `outline.md` from stage 5 or the drafted `sections/*.md` from stage 7. That is a second pass over new text, never a dependency of the first one: stage 4 runs to completion before stage 5 begins, and it never waits for anything downstream of itself.

## The placeholder convention

Every source referenced anywhere in this pipeline is written inline, at the exact point of the claim, as `{cite_<doi>}` where `<doi>` is the source's DOI, lowercased, in bare form with no `https://doi.org/` prefix. Nobody hand-writes a rendered marker like `[3]` or `(Smith, 2023)`; rendering into whatever citation style the Formatter chose happens deterministically later, from this database, via `scripts/citations.py compile`. If a placeholder's DOI has no matching entry in `research/citations.json`, the compile step fails and names it, and the draft does not move on until it is fixed.

A drafter who cannot source a claim writes `{cite_MISSING: <description>}` in that same inline position instead of a DOI. That is not a third shape of placeholder, it is an admission: this claim has no source yet. `compile` checks for it before it checks anything else against this database, and refuses to write any output while one remains, naming every occurrence by line number with the drafter's own description:

```
Error: Refusing to compile 2 unsourced claim(s) marked {cite_MISSING: ...} by the drafter: line 12: the disposable soma theory predicts a trade-off between repair and reproduction; line 47. For each one: find a source with python3 scripts/sources.py find "<topic>" --json > new.json, merge it into the database with python3 scripts/citations.py build new.json -o research/citations.json, and replace the marker with {cite_<doi>} -- or cut the claim. It cannot ship marked.
```

`integrity.py` runs the equivalent check on an already-compiled draft, the first check it runs, and counts every occurrence as one critical issue. Finding this marker while building or re-running the database means the work is not finished: find the source and add it via `build`, the same route as any other citation, or tell whoever owns the draft to cut the claim. It is never something to leave in place, and never a route to shipping an unsourced claim under a marker that only looks like a citation.

## Build the database with the script

`research/citations.json` is generated. You do not hand-write it, you do not hand-edit it, and you do not paste a JSON object into it. There is exactly one route:

```
python3 scripts/citations.py build research/sources.json -o research/citations.json
python3 scripts/citations.py verify -d research/citations.json
```

`build` reads the JSON array stage 1 wrote, normalizes each record, and keys the database by DOI. It prints `Added N, updated M, total T citations` and exits 0. It skips any record with no DOI and says so on stderr; that is expected and those sources are your job below, not a failure.

`verify` re-checks every DOI in the database against Crossref and then DataCite, writes the result back into each record's `verified` field, and prints a one-line count: `resolved=N absent=N unknown=N invalid=N`. It exits nonzero when anything came back `absent` or `invalid`, and lists the offending DOIs on stderr. Read the exit code, not the prose.

Both commands are idempotent. `build` merges rather than replacing, and it preserves an existing `verified` value when a record is re-added, so re-running the pair after stage 1 finds more sources is the normal way to grow the database.

**If `build` errors**, read the error rather than working around it. All three failures exit 1, and each names a different problem at stage 1, which owns `research/sources.json`:

- `does not look like sources.py find --json output (expected a JSON array)` means the file parsed as JSON but is a wrapper object rather than a bare array.
- `Expecting value: line 1 column 1 (char 0)` means the file is not JSON at all, most often because it is markdown. This is what you get if you point `build` at `research/sources.md`, which wraps its JSON in prose and fenced code. Do not do that; fix `sources.json` instead.
- `[Errno 2] No such file or directory` means stage 1 did not write the file. Go back to stage 1 rather than assembling one yourself from `sources.md`.

## The schema, for reading not for typing

Each record `build` writes looks like this. It is here so you can read the file and check it, and so downstream stages know what they are reading. It is not a template to fill in:

```json
{"version": 1,
 "citations": {
   "10.5555/jdc.2023.14.3.210": {
     "doi": "10.5555/jdc.2023.14.3.210",
     "title": "Adaptive governance structures in open-source infrastructure projects",
     "authors": [{"family": "Chen", "given": "Mei"},
                 {"family": "Alvarez", "given": "Rosa"},
                 {"family": "Park", "given": "Jin Ho"}],
     "year": 2023,
     "venue": "Journal of Digital Commons",
     "publisher": "Digital Commons Press",
     "type": "journal-article",
     "url": "https://doi.org/10.5555/jdc.2023.14.3.210",
     "verified": "resolved"}}}
```

Three things about it are worth holding onto, because they are where hand-written variants have gone wrong before:

- `citations` is an object keyed by the lowercased bare DOI, not a list. The key and the record's own `doi` field are the same string.
- `authors` is an array of `{"family", "given"}` objects. Not surname strings. `given` is an empty string when the upstream record had no given name, which is normal for a mononym or a sparse Crossref deposit. An empty `given` is a fact about the metadata; never fill one in.
- The type field is `type` and the verification field is `verified`, a bare string. Not `source_type`, not a `verification` object.
- `venue` and `publisher` are whatever the upstream metadata carried, and either can be an empty string. An empty `venue` is normal for a preprint and for many books. It is not a gap for you to fill.

`type` carries whatever Crossref or OpenAlex recorded: `journal-article`, `proceedings-article`, `book-chapter`, `monograph`, `report`, `posted-content` (a preprint). `verified` is one of `resolved`, `absent`, `unknown`, `invalid`, and starts at `unknown` until `verify` has run.

## The four verification states, and what each one obliges you to do

`verify` puts every DOI into exactly one state. `unknown` is never quietly promoted to `absent`, and `absent` is never quietly repaired.

- **`resolved`.** Crossref or DataCite returned the record. The work exists at that DOI. That is the whole of what it establishes: it says nothing about whether the work supports the sentence citing it, which is stage 11's question and the one that actually matters. Cite it.
- **`absent`.** Both agencies returned 404. The DOI points at nothing. Do not repair it, do not try a similar-looking DOI, do not swap in a different paper's DOI because the title is close. Go back to stage 1 and find a real source for the claim, or drop the claim. Remove the entry from the database and remove every `{cite_<doi>}` placeholder that pointed at it, then record it in `research/citation-notes.md` under `Removed`. A guessed replacement DOI is the single most damaging thing this stage can produce, because it resolves, looks correct, and points at a paper nobody chose.
- **`unknown`.** A network failure, a rate limit, or a non-404 HTTP error. The DOI may be perfectly good. `sources.py` already retries once internally, so re-run `citations.py verify` once more, spaced out, before concluding anything. If it is still `unknown`, the source cannot carry an inline citation: the compile gate renders only `resolved` entries, and printing a marker for a DOI you could not resolve is exactly the claim this pipeline refuses to make. Either replace the source, or keep the work in the paper by naming it in prose and in the limitations section as a source that could not be checked. Record it under `Needs review` with the exact error text `verify` printed.
- **`invalid`.** Malformed or empty. Same handling as `absent`, and note in `citation-notes.md` where the malformed string came from, since it is usually a transcription error upstream rather than a bad source.

arXiv and other preprint DOIs commonly 404 at Crossref and resolve at DataCite, which is why `verify` checks both in that order. A DOI that came back `resolved` with agency `datacite` is not weaker evidence than one from Crossref.

The compile step enforces this rather than trusting you to. Anything not `resolved` stops it, by name:

```
Error: Refusing to render citation(s) whose DOI is not resolved at Crossref or DataCite: 10.48550/arxiv.2401.01234 (unknown), 10.5555/env.2022.8.55 (unknown). Run: python3 scripts/citations.py verify -d <database>  and remove or replace any source that does not resolve.
```

So leaving an entry at `unknown` does not quietly degrade the paper later, it blocks the gate. Deal with it here. Never edit a `verified` value by hand to get past that error: the field records what an agency answered, and typing `resolved` into it makes the database assert something no agency said.

## Count what survived, and go back for more if it is short

Verification takes sources out. That is what it is for, and it is also why this stage is where a review quietly becomes too small to be one. The pool that looked ample at stage 1 is the pool before the 404s, the malformed strings and the DOIs no agency would answer for; the pool this paper can actually cite is whatever `verify` reports as `resolved`, and the gap between the two is routinely a third of the list.

So count it, and compare the count against a number rather than against a feeling:

```bash
python3 scripts/citations.py verify -d research/citations.json
```

It prints `resolved=N absent=... unknown=... invalid=...`. The floor for N is whichever is higher of the `min_references` recorded in `research/brief.json` and the per-type floor in `references/paper-types.md` under "Scale: matching pipeline depth and source count to what was asked". If N is below that floor, this stage is not finished and stage 7 does not start.

What to do instead is go back to stage 1 and search again, with different queries rather than the same ones run harder. The pool came up short because the query set ran out of angles, so take the angles from the material itself: the sub-questions the topic decomposes into, the outcome measures by their own names, the populations and settings the brief names, the adjacent literature that would cite this work, the review articles and their reference lists, the contrarian position. Merge the new records into `research/sources.json` exactly as stage 1 specifies, re-run `build`, re-run `verify`, and count again. Repeat until N clears the floor or until a round of genuinely new queries returns nothing new.

Two ways out, and only two. Meet the floor, or tell the user: say how many sources verified, what the searching covered, and why the literature would not yield more, in the run report and in the paper's own limitations section. What is never a way out is quietly shipping the short list. A reference list that fell from fifty found to eighteen verified and says nothing about it does not read as a careful paper, it reads as a thin one, and the care that produced it is invisible to everyone but the person who did it.

Nor is padding. Do not add sources the paper never cites to make the count, do not enter one work twice under a preprint DOI and a published DOI, and do not relax the `resolved` requirement for the last few entries. Each of those meets the number by making the list untrue, which is worse than missing the number.

## The judgement work: what goes in `research/citation-notes.md`

This is the file you write by hand. It exists as a separate file precisely so that a hand-written annotation can never corrupt a generated database: nothing here is ever pasted into `research/citations.json`.

Scan every input file end to end before writing it. Not just the summaries: table footnotes (`*Source: ...`), figure captions ("adapted from..."), reference lists, and inline parentheticals in the notes all carry citations that never became placeholders.

Write it with these four headings, in this order, every time, even when a section is empty (write `None.` under an empty heading rather than dropping it, so a reader can tell the difference between "nothing to report" and "not checked"):

```markdown
# Citation notes

Companion to `research/citations.json`. Nothing in this file is a citation
database entry, and nothing in it may be copied into that file.

## No DOI

| Source | Author or organisation | Year | Title as given | Where it appears |
|---|---|---|---|---|
| eurostat-2023 | Eurostat | 2023 | Statistical database | research/summaries.md, table 2 footnote |

These are printed unchecked. They carry no DOI, so nothing verified that they
exist. Cite them by name in the prose, never as a `{cite_...}` placeholder, and
name the class of them in the paper's limitations section.

## Unconverted mentions

| Mention as written | Location | Resolved DOI | Action |
|---|---|---|---|
| (Smith & Johnson, 2023) | research/summaries.md, source 3 | 10.5555/enveco.2023.45.234 | replace with `{cite_10.5555/enveco.2023.45.234}` |
| (Weber, 2019) | research/gaps.md, paragraph 4 | none found | see Needs review |

## Needs review

| Item | Problem | What was done |
|---|---|---|
| 10.5555/example.1 | verify returned unknown twice, HTTP 503 from crossref | not cited inline, named in limitations |
| (Weber, 2019) | no matching source in research/sources.json, no DOI to verify | claim needs a source from stage 1, or it goes |

## Removed

| DOI | State | Where the placeholder was | Replacement |
|---|---|---|---|
| 10.5555/gone.4 | absent | sections/03-methods.md, para 2 | none yet, back to stage 1 |
```

Keep the tables. A prose paragraph describing four unconverted mentions is a paragraph the next stage skims; a table row per mention is a row the next stage can act on.

## What counts as a citable source

A citable source is one a reader could go and read: a journal article, a conference paper, a book or chapter, a technical report, a dataset with a DOI, a preprint clearly labelled as one. It is not a blog post used as evidence for an empirical claim, a press release standing in for a study, or a secondary summary of a paper you never located.

Two judgement calls come up every run:

- **A source named only in prose, with no DOI.** A government statistics portal, a standards document, an organisational report. It goes under `No DOI`, cited by name in the text, never given an invented DOI to make it fit the placeholder scheme. Never invent a DOI. There is no situation in this pipeline where inventing one is the right call.
- **A source you remember rather than retrieved.** It does not go in. If it is not in `research/sources.json`, `verify` cannot help, because `verify` checks a DOI you already have. Send the claim back to stage 1.

## What counts as incomplete, and what to do about it

If a field (year, title, venue) is missing from the built database because the upstream record did not carry it, leave it missing and add a `Needs review` row. Do not reconstruct a title from context, do not approximate a year from a nearby paper, do not guess a publisher, and do not open the JSON file to type one in. A database that fills gaps with plausible-sounding values is worse than one that leaves them visibly blank, because the blank gets checked and the plausible guess does not.

A missing `year` is not cosmetic: every author-year style renders it as `n.d.` in both the marker and the reference entry, which is visible to a reader and honest. `2023` typed in by hand because the neighbouring papers are from 2023 is neither.

## Deduplication

`build` keys by DOI, so a source cited five times in the text is automatically one entry. DOIs are case-insensitive and `build` lowercases them, so `10.1234/ABC` and `10.1234/abc` collapse correctly on their own.

What it cannot catch is the same work deposited twice under two DOIs, typically a preprint and its published version. Stage 1 removes those pairs from the pool, but check the built database for near-identical titles anyway, and if a pair survived, keep the published version, drop the preprint's entry, and repoint any placeholder that used the preprint DOI. Record the swap under `Removed`.

For no-DOI sources, matching author plus year plus a close title match is the same source; list it once.

## Language

Handle citations regardless of the language they appear in. Keep non-English titles exactly as written, with original diacritics: `CO2-Bepreisung in Deutschland` stays as it is, and is not translated, transliterated, or stripped of umlauts. The same holds for author names.

## Worked examples

**A bare mention in the notes.** `research/summaries.md` says: `Recent studies show carbon pricing reduces emissions (Smith & Johnson, 2023).` Look for Smith, Johnson and 2023 in `research/sources.json`. If they are there, the DOI is already a database entry, because `build` took the whole array; add a row under `Unconverted mentions` with that DOI and the action, so whoever owns that text replaces the parenthetical with `{cite_<doi>}`. If they are not there, there is no DOI to verify and nothing to build from: the row goes under `Needs review` with "no matching source in `research/sources.json`", and the claim goes back to stage 1. It never becomes a fabricated DOI.

**A German table footnote.** `*Quelle: Eigene Darstellung basierend auf Eurostat (2023) und IEA (2023).*` Neither is a DOI-bearing academic source. Both go under `No DOI`, as two separate rows, titles recorded as best described from context, and both are cited by name in the prose. This is not fabrication, because the file states plainly that nothing verified them.

**A DOI that comes back absent.** `verify` exits 1 and prints `10.5555/gone.4: absent`. The temptation is to search for the title and attach whichever DOI turns up. Do not. Delete the entry, grep the draft for `{cite_10.5555/gone.4}`, remove those placeholders, log the row under `Removed`, and either re-source the claim at stage 1 or cut it. The compile step would otherwise print a marker and a reference entry for a work that is not there.

**A preprint that resolves at DataCite only.** `verify` reports `resolved`, agency `datacite`. Nothing further to do here; stage 1 already flagged its preprint status in `research/sources.md`, and the paper should describe it as a preprint where it is discussed.

## Common mistakes

Hand-writing or hand-editing `research/citations.json` instead of building it; pointing `build` at `research/sources.md`; typing the schema out as a list instead of letting the script key it by DOI; flattening author objects to surname strings; writing `source_type` or a `verification` object, neither of which any script reads; skipping table footnotes and figure captions when scanning for unconverted mentions; treating a `verify` failure as noise instead of reading the exit code; inventing a DOI, a title, or a year that was not in the source data or the verify response; and mixing annotations into the database file where the next `build` will either drop them or trip over them.

## Done when

- `research/citations.json` exists, was produced by `citations.py build`, and parses: `python3 -c "import json;d=json.load(open('research/citations.json'));print(len(d['citations']))"` prints the entry count.
- `citations.py verify -d research/citations.json` has been run, and its exit code was read. Every remaining entry is `resolved`; every `absent` or `invalid` entry has been removed and logged, and every `unknown` was retried and then either replaced or excluded from inline citation.
- `research/citation-notes.md` exists with all four headings present, and every no-DOI source, unconverted mention, review item and removal is a row in it.
- Nothing in either file was reconstructed, approximated, or invented. No DOI in the database was typed by a model rather than returned by a tool.
- Every claim that lost its source is either re-sourced or gone from the draft, not left pointing at a placeholder that no longer resolves.
- The `resolved` count has been compared against the floor, not estimated. It meets the floor, or a further round of new queries returned nothing new and the shortfall is written down for the limitations section with the number in it.
