# Scout

Finds and ranks the candidate source pool for a research topic. Every later stage (summarizing, gap analysis, outlining) only ever reasons about the sources Scout surfaced; a narrow or unverified pool here quietly caps the quality of the whole paper.

**Reads:** the research topic, scope, and any seed references supplied by the user
**Writes:** `research/sources.md` (the readable narrative), `research/sources.json` (the machine artifact stage 4 builds the citation database from)

## What you have

The skill ships one keyless lookup tool, backed by Crossref and OpenAlex:

```
python3 scripts/sources.py find "<query>" --n 15            # readable list
python3 scripts/sources.py find "<query>" --n 15 --json     # the raw record array
```

## Read the exit code before the result

`find` exits 1, not 0, on exactly one condition: every API it tried, Crossref then OpenAlex, failed to answer at all, and it says so on stderr rather than stdout: `# no source API could be reached (crossref, openalex); this is a failed search, not an empty topic`. That is a different fact from a query that reached both APIs cleanly and came back with nothing worth keeping, and reading only the printed list erases the difference. A stage that treats exit 1 as an empty topic goes on to draft a paper with no literature under it, on the strength of a network failure it never checked for; the person reviewing the paper later has no way to tell that failure apart from a topic nobody has written about.

Check the exit code of every `find` call, not just its output. On exit 1, run the same query again once; a single dead attempt is often a timeout or a rate limit, not a permanent outage. If it exits 1 a second time, stop the stage here rather than continuing on to the remaining planned queries or reaching for a title recalled from training to fill the gap. Tell the user the search infrastructure failed, in those words, and wait; do not write `research/sources.md` against a pool this thin, and do not proceed to stage 2.

Below three sources actually retrieved by `find`, whatever the cause, the stage stops for a second and separate reason: a review needs enough independent sources to triangulate a claim, notice where the field disagrees with itself, and tell a repeated finding from a single paper's framing, and three is the minimum that supports any of that. Below it there is no literature to review, only one or two citations waiting to be dressed up as one, and the honest move is to stop and report rather than summarize, outline, and draft against a pool too thin to carry the paper. This is not the "very narrow topic" case in Special cases below, which is for a topic that ran cleanly and came back genuinely small, ten sources or fewer, and stays open to broadening the query set; this floor sits beneath that, for when even broadening would leave next to nothing.

Each result carries `doi`, `title`, `authors`, `year`, `venue`, `publisher`, `type`, and `source` (crossref or openalex).

`authors` is an array of objects, one per author, each `{"family": "Chen", "given": "Mei"}`. It is not a list of surname strings, and nothing downstream will accept it as one. `given` is present but empty when the upstream record has no given name: Crossref sometimes deposits a family name alone, and OpenAlex exposes only a single display name per author, which `sources.py` splits on the last space, so a mononym yields `{"family": "Pi", "given": ""}`. Carry the objects through exactly as returned. Do not flatten them to surnames, do not merge `given` into `family`, and never invent an initial for an empty `given`.

A real two-record slice of `find --json`, for shape:

```json
[
  {
    "doi": "10.2139/ssrn.5316632",
    "title": "A Comparative Study of Retrieval-Augmented Generation, Graph Retrieval-Augmented Generation, and Fine-Tuned Large Language Models for Fire Engineering Knowledge Retrieval",
    "authors": [
      {"family": "Xue", "given": "Xingzhuo"},
      {"family": "Zhang", "given": "Guowei"},
      {"family": "Jiang", "given": "Liming"},
      {"family": "Liu", "given": "Chunyuan"}
    ],
    "year": 2025,
    "venue": "",
    "publisher": "Elsevier BV",
    "type": "posted-content",
    "source": "crossref"
  },
  {
    "doi": "10.1007/979-8-8688-1808-0_1",
    "title": "Introduction to Retrieval-Augmented Generation (RAG)",
    "authors": [{"family": "Bose", "given": "Ranajoy"}],
    "year": 2025,
    "venue": "Mastering Retrieval-Augmented Generation",
    "publisher": "Apress",
    "type": "book-chapter",
    "source": "crossref"
  }
]
```

`type` is whatever Crossref or OpenAlex recorded, most often `journal-article`, `proceedings-article`, `book-chapter`, `monograph`, `report`, or `posted-content`. `venue` is an empty string when no container title was deposited, which is common for preprints. `find` does not return an abstract or a citation count; Crossref's bibliographic search is plain keyword matching, it does not support field syntax like `author:` or `title:`, so put author surnames and key terms directly in the query string as ordinary words.

If you have a web fetch or search tool available, use it to open `https://doi.org/<doi>` for promising results and read the abstract or full text directly. If you do not, work from title, venue, and year alone, and say so explicitly in the `research/sources.md` entry (`"abstract": null, "note": "metadata only, not fetched"`). Never write an abstract or a relevance justification you could not actually read.

## Search strategy

1. **Decompose the topic** into distinct queries rather than one broad string: the core concept, 1 to 2 adjacent/interdisciplinary angles, any named regulatory or standards bodies relevant to the domain, and recent-development phrasing (add the current year or "2024" style terms for fast-moving fields). How many queries depends on how many sources the piece needs, following `SKILL.md`'s scale:
   - **Short piece** (10 to 15 sources): 4 to 8 queries.
   - **Full paper, the default** (25 to 50 sources): 12 to 20 queries.
   - **Thesis chapter or long review** (fifty sources or more): 30 to 50 queries.

   A query's yield is not uniform, so plan against it rather than against query count alone. A query built around one author's surname or an exact title phrase tends to return only 1 to 2 sources; an ordinary 2 to 3 word topic query returns roughly 2 to 5; a broader query of 4 or more words, or one combining several concepts, returns roughly 5 to 10. Before running the searches, add the expected yields across your planned queries. If the total sits under 70 percent of the tier's source count, add more queries rather than hoping the shortfall resolves itself during filtering; a thesis chapter targeting fifty sources needs a planned yield of at least 35 before the first query runs.
2. **Expand from seed references**, if any were given: query the seed's own title keywords, its authors' surnames alongside the topic, and one query per co-author combination. This tends to surface the citation neighborhood a single topic query misses.
3. **Run each query** through `find`, requesting 10 to 15 results per call, and merge, deduplicating by DOI.
4. **Balance temporally**: aim for roughly 60 percent sources from the last 5 years, 30 percent from the 5 years before that, and a handful of older foundational works if the field has them. Note in the output if a field is too young to have a temporal spread.
5. **Balance by type**: prefer `journal-article`, `proceedings-article`, and `report`; include `posted-content` (preprints) only when they are recent (under 12 months) or clearly still the best available source, and mark them as preprints. If a preprint is older than 24 months with no journal version found, flag it as likely superseded rather than dropping it silently.

## Searching is a loop, and this stage runs more than once

The tier counts above are what a first pass aims at. They are not what the paper needs, because a source found here is not yet a source the paper can cite: stage 4 verifies every DOI at Crossref and DataCite, and the ones that come back `absent`, `invalid` or `unknown` leave the pool. Whatever that removal costs has to be found, not absorbed.

So expect to come back here. Stage 4 counts what verified, compares it against the floor (the `min_references` in `research/brief.json`, or the per-type floor in `references/paper-types.md`, whichever is higher), and returns to this stage when the count is short. A second visit is the normal shape of this pipeline on a review, not a sign that the first pass was done badly.

When you come back, bring different queries. Re-running the same query set returns the same records and the count does not move, which is the failure this note exists to prevent. New angles come from four places, in roughly this order of yield:

1. **The brief's own vocabulary.** Briefs name the sub-questions they want covered, and each one is a query: an outcome ("emergency response times", "boundary road traffic volumes"), a population ("older adults", "e-scooter riders"), a setting, an intervention's other name.
2. **The vocabulary of the sources you already have.** Titles and abstracts in the pool name the measures, cohorts, instruments and study designs the field actually uses, and those terms are usually not the ones the topic line used.
3. **The citation neighbourhood.** Query the surnames of authors already in the pool alongside the topic, and query the review articles a field this size will have; a review's own subject terms are a ready-made query list.
4. **The other side.** A query built to find the contrarian position, the null result, or the critique. A pool assembled only from queries phrased like the claim will be a pool that agrees with the claim.

Merge each new round into `research/sources.json` by the same deduplicating merge below, so the file stays raw tool output throughout. Stop when a round of genuinely new queries returns nothing new; that is a fact about the literature and belongs in `gaps_noticed` and in the paper's limitations, phrased as what was searched and what was not there.

## Quality filtering

Keep a source only if `find` (or `verify`) actually returned it: never add a paper you recall from training but could not retrieve through the tool or a live fetch. Remove exact duplicates (same DOI) and near-duplicates (same title, different DOI, e.g. preprint plus published version, keep the published one). Drop non-English sources unless the user asked for them.

Because the tool does not return citation counts, do not rank by "impact" unless you fetched that number yourself from a live source and can say where it came from. Rank instead by: how directly the title and venue match the topic, recency, and venue plausibility (a named journal or established conference outranks an unfamiliar venue, all else equal).

**Preprint handling.** When a result's `type` is `posted-content`, check whether the same title and authors also turn up as a `journal-article` or `proceedings-article` in your results; if so, keep the published version and drop the preprint. If no published version turns up:
- under 12 months old: keep it, it is simply recent work.
- 12 to 24 months old: keep it, but mark `"status": "awaiting peer review"`.
- over 24 months old: mark `"status": "possibly superseded, no journal version found"` rather than silently including or excluding it.

Rank the final list by, in order: topical match (does the title/venue directly address the question, or only touch it in passing), recency (prefer the last 2 to 3 years unless the paper is foundational), and venue plausibility. If you fetched full text or an abstract for a source, note anything it cites that also shows up elsewhere in your list; a paper cited by several others in the pool is worth flagging as a likely hub even without a citation count.

**Diversity, not just relevance.** A source list that is 30 near-identical empirical papers from the same year is worse than one with range. Where the field supports it, include at least one review or survey paper (for background), a few recent empirical studies (current state), one or two foundational or seminal works even if old (context), and, if they exist, a paper taking a critical or contrarian position (alternative view). Note in `gaps_noticed` if one of these categories is simply absent from what you found.

## Output format

You write two files. They are not alternatives and neither replaces the other.

### `research/sources.json`, the machine artifact

The raw `find --json` records for the sources you kept, concatenated into one JSON array, deduplicated by DOI, in your final ranked order. Nothing else: no wrapper object, no `rank`, no `why_relevant`, no prose. This is the file stage 4 runs `citations.py build` against, and `build` requires a top-level JSON array of `find --json` records. It errors on anything else, including a wrapper object and including markdown around it.

Never hand-edit `research/sources.json`, and never hand-type a record into it. Every record in it is a value `find` returned, copied through unchanged, fields and author objects intact. A record you typed yourself is a source nobody retrieved.

Save each query's output, then merge:

```bash
mkdir -p research/_raw
python3 scripts/sources.py find "query one" --n 15 --json > research/_raw/q1.json
python3 scripts/sources.py find "query two" --n 15 --json > research/_raw/q2.json
# ...one file per query

python3 - <<'PY'
import json, pathlib
merged, seen = [], set()
for p in sorted(pathlib.Path("research/_raw").glob("*.json")):
    for rec in json.loads(p.read_text(encoding="utf-8")):
        doi = (rec.get("doi") or "").strip().lower()
        if doi and doi not in seen:
            seen.add(doi)
            merged.append(rec)
pathlib.Path("research/sources.json").write_text(
    json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(merged), "unique records")
PY
```

That merge keeps everything the queries returned. Then drop from the array the records you rejected in quality filtering (near-duplicate preprint/journal pairs, non-English titles where the user did not ask for them, weak matches you decided against), so the array and the ranked list in `sources.md` describe the same pool. A DOI in `sources.json` that you argued against in `sources.md` becomes a database entry nobody meant to cite.

### `research/sources.md`, the readable narrative

A short intro paragraph (the topic, the queries run, and any gaps you noticed) followed by a JSON block. This is where the ranking, the relevance judgements, the preprint status flags, the gaps and the refinement suggestions live, because none of them survive `build` and none of them belong in the database:

```json
{
  "search_query": "the original topic",
  "queries_run": ["query 1", "query 2", "..."],
  "total_unique_sources": 32,
  "sources": [
    {
      "rank": 1,
      "doi": "10.1234/example",
      "title": "Full paper title",
      "authors": [
        {"family": "Smith", "given": "Alice"},
        {"family": "Johnson", "given": "Paul"}
      ],
      "year": 2023,
      "venue": "Nature Medicine",
      "type": "journal-article",
      "preprint": false,
      "abstract": "First 2-3 sentences, only if fetched",
      "note": null,
      "why_relevant": "One sentence tied to the title/venue or to fetched content",
      "relevance": "high | medium | low"
    }
  ],
  "gaps_noticed": ["e.g. very few sources after 2023, field may be emerging"],
  "suggested_refinements": ["alternative phrasing or adjacent terms worth a follow-up query"]
}
```

Keep the author objects here in the same `{"family", "given"}` shape `find` returned, so the two files can be read side by side without a mental translation step.

Every entry carries both `abstract` and `note`, and together they record whether
anyone actually read the source. When you fetched it, `abstract` holds the first
two or three sentences you read and `note` stays `null`. When you did not,
`abstract` is `null` and `note` is the string `"metadata only, not fetched"`.
Both keys are present either way. A missing key reads as an oversight; `null`
against a stated alternative reads as an answer, and this is the field a later
stage checks before treating an entry as evidence of anything the title does not
already say. The same rule governs `why_relevant`: on a metadata-only entry it
can rest on title, venue and year and nothing else, and it may not describe
findings, methods or results, because none of those were read.

Every entry must be valid JSON: no repeated-token garbage in author names (`{"family": "Smith Smith Smith"}` is a bug, not a name), authors as a real array of 1 to 20 author objects, `year` between 1900 and the current year, and no empty `title`. If a field genuinely cannot be determined, use `null`, do not omit the key and do not guess a plausible-looking value.

The two files must agree. Same DOIs, same count, same titles and years. If they disagree, `sources.json` is wrong by construction, because it is supposed to be untouched tool output; rebuild it from `research/_raw/` rather than editing it into agreement.

## Worked example

Topic: "transformers for climate modeling." Queries run: `"transformers climate modeling"`, `"attention mechanism weather forecasting"`, `"deep learning climate prediction 2024"`, `"neural network downscaling climate"`. Four calls to `find --n 15 --json`, each saved to its own file under `research/_raw/`, return 58 raw hits; the merge deduplicates by DOI and leaves 41 unique records. Filtering out three non-English titles and two near-duplicate preprint/journal pairs leaves 36, and those five rejected records come back out of the array. Two of the 36 are `posted-content` from 2024 with no journal version, marked as recent preprints in `sources.md` rather than dropped. `research/sources.json` ends up as an array of 36 raw records; `research/sources.md` ends up with the same 36, ranked, with the preprint flags and the note in `gaps_noticed`: "field is young, almost nothing before 2021, no clearly seminal paper to anchor the review on."

## Special cases

- **Very narrow topic (under 10 sources found across all queries):** broaden terms, try adjacent fields, and say plainly that the area is niche rather than padding the list with weak matches.
- **Very broad topic (over 150 unique sources):** stop expanding, group what you have into 3 to 5 sub-topics, and recommend the user narrow scope before Scribe processes all of them.
- **Interdisciplinary topic:** run at least one query per discipline and note the cross-field connections you see; a source that would be missed by a single-domain query is often the most valuable one.

## Done when

- `research/sources.md` exists, contains valid JSON, and every source in it came from an actual `find`/fetch call, not memory.
- `research/sources.json` exists and parses as a top-level JSON array of raw `find --json` records, with author objects intact. Check it, do not assume it: `python3 -c "import json;d=json.load(open('research/sources.json'));print(type(d).__name__, len(d))"` must print `list` and the source count.
- The two files list the same DOIs in the same number.
- The number of unique, deduplicated sources kept matches the tier the piece was scaled to: roughly 10 to 15 for a short piece, 25 to 50 for a full paper, fifty or more for a thesis chapter (fewer only if the topic is genuinely narrow, and that is stated).
- Every entry has doi, title, authors, year, venue, type; `abstract` and `why_relevant` (in `sources.md` only) are either grounded in fetched content or explicitly marked as metadata-only.
- Every entry in `sources.md` carries both `abstract` and `note`, neither key omitted: a fetched source has the sentences and a `null` note, an unfetched one has a `null` abstract and `"metadata only, not fetched"`. No `why_relevant` on a metadata-only entry describes a finding, method or result, since none were read.
- Preprints are flagged as such, and any preprint older than 24 months with no journal version is flagged as possibly superseded.
- Gaps and refinement suggestions are included, even if short.
- The pool is large enough to survive verification. Stage 4 removes every DOI that does not resolve, so a pool that only just reaches the floor here will fall below it there; aim above the floor rather than at it, and expect to be sent back for another round of new queries if it still comes up short.
