# Citation verification

How OpenDraft checks citations, and what those checks do and do not establish. Moved from the README.

Citations are checked in two independent ways. They answer different questions
and neither substitutes for the other.

## 1. Does the work exist? (multi-source confirmation)

Discovery may find a candidate through any source. Confirmation then looks the
candidate's **DOI** up directly in each scholarly database and counts how many
hold a record for it.

**By default a citation is kept only if at least 2 of {CrossRef, OpenAlex,
Semantic Scholar} hold its DOI.** A single-source result is dropped and the drop
is logged. Accepting single-source results is an explicit opt-out
(`require_multi_source=False`), not the default.

To be exact about what "2 databases hold it" means: one of the two may be the
database that returned the candidate in the first place, which is taken at its
word rather than re-queried. The others are looked up directly by DOI. The
engine tracks this distinction internally (`confirming_sources` versus
`independently_confirmed_by`) and `verification_notes` on each citation spells
out which database found it and which ones confirmed it.

| Setting | Default | Effect |
|:---|:---|:---|
| `require_multi_source` | `True` | Drop citations fewer than `min_confirming_sources` databases hold |
| `min_confirming_sources` | `2` | How many of the three must hold the DOI |
| `allow_unconfirmed_web_sources` | `False` | Keep DOI-less web-search results (kept tagged if enabled) |
| `enable_llm_fallback` | `False` | Let the LLM assert a citation when every lookup fails |

Every citation in `bibliography.json` carries its provenance:

| `verification_status` | Meaning |
|:---|:---|
| `multi_source_confirmed` | The DOI is held by `min_confirming_sources` or more databases, listed in `verification_sources` |
| `single_source` | Exactly one database holds the DOI. Dropped under the default settings |
| `unconfirmed` | The DOI carries no record in **any** scholarly database. Dropped under the default settings |
| `web_search_unconfirmed` | No DOI, so no scholarly database could be queried. Zero databases confirmed it |
| `llm_unverified` | Asserted by the LLM with no external lookup of any kind. Nothing checked that it exists |
| `not_checked` | Confirmation was disabled for this run |

`verification_sources` is written out even when it is empty, precisely so an
unconfirmed citation can never serialize to look like a confirmed one.

**What this establishes, and what it does not.** A confirmation means the DOI is
registered and indexed in that many databases. It does not mean the work
supports the sentence it is attached to, and it is not three separately sourced
attestations of the same facts: OpenAlex and Semantic Scholar both ingest
Crossref metadata, so the three are not fully independent of one another.

arXiv is not queried as a citation database. `arxiv.org` can appear as a
web-search result and Semantic Scholar exposes arXiv IDs, but there is no arXiv
API client in this engine.

## 2. Does the source support the claim? (claim-level verification)

A real, correctly cited, multi-source-confirmed paper can still be attached to a
claim it says nothing about. Existence checking cannot detect that, so
`CitationClaimVerifier` judges each source against the claim it is cited for and
returns `RELEVANT`, `IRRELEVANT` or `UNCERTAIN`.

In the citation phase this runs against the **paper topic**, because that phase
executes before any draft text exists and the topic is the only claim available
at that point. Sentence-level checking needs a draft and is available through
`run_citation_claim_verification()`.

Reports are written to the research folder as
`citation_claim_verification.md` and `.json`. A citation judged `IRRELEVANT` is
removed only above a confidence floor (`CLAIM_VERIFICATION_MIN_CONFIDENCE`,
default `0.7`), and the engine refuses to empty the bibliography outright.

| Env var | Default | Effect |
|:---|:---|:---|
| `ENABLE_CLAIM_VERIFICATION` | `true` | Run claim-level verification at all |
| `CLAIM_VERIFICATION_DROP_IRRELEVANT` | `true` | Remove irrelevant citations rather than only reporting them |
| `CLAIM_VERIFICATION_MIN_CONFIDENCE` | `0.7` | Confidence needed before a removal happens |

**These verdicts are language-model judgements, not proofs.** The judge reads a
citation's title and abstract, not the paper's full text. `UNCERTAIN` means
unchecked, not passing. Treat the output as evidence for a human reviewer.

## Effect on how many citations you get

Requiring two independent confirmations necessarily lets fewer candidates
through than accepting the first responder did. That is the intended trade:
fewer citations, each one confirmed by more than one database.

**A run can now fail where it previously produced a weak draft.** Strict
confirmation, the strict quality filter and claim-level removal all shrink the
bibliography, and the pipeline raises `PipelineValidationError` if no citations
survive the citation phase. If you hit that, widen the search or relax the
settings deliberately rather than by accident.

Citation counts quoted in older versions of the README and in `EVALUATION.md` were
measured before multi-source confirmation became the default and have **not**
been re-measured since. Treat them as historical. If you need the old
behaviour, set `require_multi_source=False` — and note that citations then
carry `verification_status: not_checked` rather than being labelled confirmed.
