#!/usr/bin/env python3
"""Keyless source lookup and DOI verification for the opendraft skill.

No API key. Crossref, OpenAlex and DataCite are open endpoints. Every printed
DOI is checked against Crossref, then DataCite, and a source whose DOI does not
resolve is never returned as verified.

    sources.py find "topic" [--n 12] [--json] [--no-preprints]
    sources.py verify 10.1038/s41598-023-41032-5 [more DOIs...]

find prints a human-readable list by default; pass --json to get the raw
array that scripts/citations.py build consumes.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Crossref runs a "polite pool" with better rate limits for requests that carry a
# contact address. That address should be the person actually making the requests,
# so it is opt-in through the environment and never a baked-in default: shipping
# one address would pool every installer into a single identity and route their
# rate-limit problems to a stranger's inbox.
_CONTACT = (os.environ.get("OPENDRAFT_CONTACT_EMAIL") or "").strip()
UA = "opendraft-skill/1.0"
if _CONTACT:
    UA += " (mailto:%s)" % _CONTACT


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _norm_doi(doi):
    """Lower-case and strip a DOI down to its bare form (no scheme/host)."""
    d = (doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d


# 10.<registrant>/<suffix> is the whole of DOI grammar that can be checked
# without asking a registry: a numeric registrant code (optionally with
# dot-separated sub-codes, an older but still-valid form) followed by a slash
# and a non-empty, non-whitespace suffix. The suffix itself is opaque by
# design: DOI syntax (ANSI/NISO Z39.84) allows almost any character in it,
# including the slashes, dots, parentheses, angle brackets, colons and
# semicolons that show up in real DOIs like
# 10.1002/(SICI)1099-1050(199806)7:3<233::AID-HEC343>3.0.CO;2-Y, so this only
# rejects what genuinely cannot be a DOI at all: no "10." prefix, no
# registrant digits, or nothing after the slash.
_DOI_SHAPE = re.compile(r"^10\.\d{2,9}(?:\.\d+)*/\S+$")


def _shape_invalid_reason(d):
    """None when `d` could plausibly be a DOI, else why it cannot be one."""
    if not d.startswith("10."):
        return "does not start with the DOI prefix '10.'"
    if not _DOI_SHAPE.match(d):
        if "/" not in d:
            return "has no '/' separating the registrant code from the suffix"
        return "does not match DOI grammar 10.<registrant>/<suffix>"
    return None


# Crossref indexes peer-review reports, decision letters, corrections and
# component parts as first-class works. A bibliographic query returns them
# ranked alongside the papers, so an unfiltered `find` can hand back a citation
# list made entirely of review artifacts. Only these types are citable.
# journal-article / proceedings-article / book-chapter / monograph / report are
# always in scope; posted-content (arXiv, SSRN, bioRxiv preprints) is gated by
# --include-preprints / --no-preprints because it is also the type Crossref
# uses for non-scholarly "posted" content such as blog notes (see
# _BLOG_PUBLISHERS below).
PUBLISHED_TYPES = {"journal-article", "proceedings-article", "book-chapter",
                    "monograph", "report"}
PREPRINT_TYPES = {"posted-content"}


def citable_types(include_preprints=True):
    return PUBLISHED_TYPES | (PREPRINT_TYPES if include_preprints else set())


# Titles Crossref gives review/decision/correction records, matched case-folded.
_JUNK_PREFIXES = ("review for ", "decision letter for ", "author response",
                  "reviewer report", "peer review of ", "correction to",
                  "corrigendum", "erratum", "retraction")


def _citable(title, doi):
    t = (title or "").strip().lower()
    if not t or t.startswith(_JUNK_PREFIXES):
        return False
    # Review artifacts hang off the parent DOI as /vN/reviewN or /vN/decisionN.
    tail = doi.rsplit("/", 2)[-2:] if doi.count("/") >= 2 else []
    return not any(s.startswith(("review", "decision", "sup")) for s in tail)


# DOI-minting services that register works for blog posts and research notes,
# not peer-reviewed or preprint-server output. Rogue Scholar mints DOIs for
# science blog posts under Crossref publisher "Front Matter" (prefix
# 10.59350) and files them as type "posted-content", which is otherwise
# indistinguishable from a real arXiv/SSRN preprint by type alone. Checked
# case-insensitively.
_BLOG_PUBLISHERS = {"front matter"}


def _is_low_quality(authors, venue, publisher=""):
    """Strong signal that a hit is blog/note content, not a citable work.

    Two independent triggers, both conditioned on an empty venue (no
    container-title / no journal / no conference proceedings recorded):
      1. Published through a known blog-DOI-minting service (Rogue Scholar's
         "Front Matter"), regardless of author count.
      2. A single author with no recorded given name -- a bare mononym like
         "Pi" with nothing else to distinguish it, which is what an author
         list looks like when Crossref/OpenAlex return sparse metadata for
         low-effort posts. A multi-author work, or one where a given name is
         on record, is not touched by this rule.

    A non-empty venue always clears a source: whatever the author situation,
    a work that names its journal/conference/book series is not the pattern
    this filter targets.
    """
    if (venue or "").strip():
        return False
    if (publisher or "").strip().lower() in _BLOG_PUBLISHERS:
        return True
    if len(authors) == 1 and not (authors[0].get("given") or "").strip():
        return True
    return False


def _crossref_authors(item):
    out = []
    for a in item.get("author") or []:
        family = (a.get("family") or "").strip()
        given = (a.get("given") or "").strip()
        if family or given:
            out.append({"family": family or given, "given": given if family else ""})
    return out


def _openalex_authors(w):
    """OpenAlex only exposes a single display_name per author, so split it
    into a best-effort given/family pair the same way a human would read it:
    last token is the family name, everything before it is the given name.
    A single-token name (a mononym) yields an empty given name."""
    out = []
    for a in w.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if not name:
            continue
        parts = name.split()
        if len(parts) >= 2:
            out.append({"family": parts[-1], "given": " ".join(parts[:-1])})
        else:
            out.append({"family": parts[0], "given": ""})
    return out


def _display_name(author):
    given, family = author.get("given", ""), author.get("family", "")
    return f"{given} {family}".strip() if given else family


_PREFERRED_TYPES = ("journal-article", "proceedings-article", "book-chapter")


def _title_key(title):
    """Collapse a title to a comparison key: letters and digits only, lowercased.

    Catches the common case of one paper deposited twice, for example an SSRN
    preprint and the journal version, which carry different DOIs and so survive
    DOI-based deduplication."""
    return "".join(c for c in (title or "").lower() if c.isalnum())


def _preferable(new, old):
    """True when `new` is the better record of the same work.

    A published version beats a preprint, and a record naming its venue beats one
    that does not. Anything else is a tie and the incumbent stays."""
    new_pub = new.get("type") in _PREFERRED_TYPES
    old_pub = old.get("type") in _PREFERRED_TYPES
    if new_pub != old_pub:
        return new_pub
    return bool(new.get("venue")) and not old.get("venue")


def _absorb(out, by_title, rec):
    """Add `rec` unless the same work is already present, keeping the better copy.

    Returns True when the caller's result count changed."""
    key = _title_key(rec.get("title"))
    if key and key in by_title:
        i = by_title[key]
        if _preferable(rec, out[i]):
            out[i] = rec
        return False
    if key:
        by_title[key] = len(out)
    out.append(rec)
    return True


def find(topic, n=12, include_preprints=True, status=None):
    """Search Crossref then OpenAlex for citable sources on `topic`.

    `status`, when given, is filled in with two lists: `attempted` names every
    API this call actually reached for, and `failed` names those that raised.
    An empty result means two different things -- "the APIs answered and had
    nothing" and "nothing answered at all" -- and only the caller holding this
    dict can tell them apart. `main` uses it to exit non-zero on the second,
    because an exit code of 0 with zero sources reads to an orchestrating model
    as a successful search of a topic with no literature, and the next stage
    then writes a paper without any."""
    if status is None:
        status = {}
    status.setdefault("attempted", [])
    status.setdefault("failed", [])
    out, seen, by_title = [], set(), {}
    types = citable_types(include_preprints)
    status["attempted"].append("crossref")
    try:
        # Over-fetch: the type and quality filters remove a large share of
        # Crossref hits.
        q = urllib.parse.urlencode({
            "query.bibliographic": topic, "rows": max(n * 6, 60),
            "filter": ",".join(f"type:{t}" for t in sorted(types)),
            "select": "DOI,title,author,issued,container-title,type,publisher"})
        for it in _get(f"https://api.crossref.org/works?{q}")["message"]["items"]:
            if len(out) >= n: break
            doi = _norm_doi(it.get("DOI"))
            title = (it.get("title") or [""])[0]
            if not doi or doi in seen: continue
            if it.get("type") not in types: continue
            if not _citable(title, doi): continue
            au = _crossref_authors(it)
            if not au: continue          # a paper with no named author is not citable
            venue = (it.get("container-title") or [""])[0]
            publisher = it.get("publisher") or ""
            if _is_low_quality(au, venue, publisher): continue
            seen.add(doi)
            _absorb(out, by_title, {
                "doi": doi, "title": title, "authors": au[:6],
                "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
                "venue": venue, "publisher": publisher,
                "type": it.get("type"), "source": "crossref"})
    except Exception as e:
        status["failed"].append("crossref")
        print(f"# crossref failed: {e}", file=sys.stderr)
    if len(out) < n:
        status["attempted"].append("openalex")
        try:
            q = urllib.parse.urlencode({"search": topic, "per-page": (n - len(out)) * 3,
                                        "filter": "type:article"})
            for w in _get(f"https://api.openalex.org/works?{q}").get("results", []):
                if len(out) >= n: break
                doi = _norm_doi(w.get("doi"))
                title = w.get("title") or ""
                if not doi or doi in seen or not _citable(title, doi): continue
                au = _openalex_authors(w)
                if not au: continue
                source = ((w.get("primary_location") or {}).get("source") or {})
                venue = source.get("display_name", "")
                publisher = source.get("host_organization_name", "") or ""
                if _is_low_quality(au, venue, publisher): continue
                # OpenAlex indexes DOIs that neither Crossref nor DataCite
                # resolves. Dropping one silently made a rate-limited verify
                # look identical to a genuinely absent record, so say which
                # DOI went and why: "unknown" is a network problem to retry,
                # "absent" is a bad DOI to leave out.
                verification = verify(doi)
                if verification["status"] != "resolved":
                    print(f"# dropped openalex hit {doi}: verification "
                          f"{verification['status']}"
                          + (f" ({verification['error']})" if verification.get("error") else ""),
                          file=sys.stderr)
                    continue
                seen.add(doi)
                _absorb(out, by_title, {
                    "doi": doi, "title": title, "authors": au[:6],
                    "year": w.get("publication_year"),
                    "venue": venue, "publisher": publisher,
                    "type": w.get("type"), "source": "openalex"})
        except Exception as e:
            status["failed"].append("openalex")
            print(f"# openalex failed: {e}", file=sys.stderr)
    return out


VERIFY_ATTEMPTS = 3
VERIFY_BASE_DELAY = 0.3


def verify(doi):
    """resolved | absent | unknown | invalid. Unknown never becomes absent.

    Crossref is asked first, then DataCite. A non-404 answer from Crossref, a
    429 or a 5xx or a dropped connection, is not evidence about the record: it
    is evidence about Crossref. Returning "unknown" there used to end the
    function, so a DataCite-only DOI (every arXiv and Zenodo deposit) came back
    unverifiable whenever Crossref was rate-limiting, and the caller had no way
    to tell that from a real failure. Both agencies are now always tried, and
    only if neither could answer is the last "unknown" returned.
    """
    d = _norm_doi(doi)
    if not d:
        return {"doi": d, "status": "invalid", "agency": None,
                "error": "DOI is empty"}
    shape_problem = _shape_invalid_reason(d)
    if shape_problem:
        return {"doi": d, "status": "invalid", "agency": None,
                "error": f"{d!r} is not a well-formed DOI: {shape_problem}"}
    last_unknown = None
    for name, url in (("crossref", f"https://api.crossref.org/works/{urllib.parse.quote(d)}"),
                      ("datacite", f"https://api.datacite.org/dois/{urllib.parse.quote(d)}")):
        for attempt in range(1, VERIFY_ATTEMPTS + 1):
            try:
                j = _get(url)
                t = (j.get("message", {}).get("title") or [""])[0] if name == "crossref" \
                    else (j.get("data", {}).get("attributes", {}).get("titles") or [{}])[0].get("title", "")
                return {"doi": d, "status": "resolved", "agency": name, "title": t}
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # Definitive "no such record" at this agency. No retry, and
                    # it does not clear an earlier agency's unknown: one 404 plus
                    # one unreachable agency is still unknown, never absent.
                    break
                error = f"HTTP {e.code}"
            except Exception as e:  # transport error, timeout, malformed JSON
                error = str(e)
            if attempt < VERIFY_ATTEMPTS:
                # Exponential backoff: a flat 0.3s retry against a 429 is a
                # second 429, which is how a rate limit turned into a verdict.
                time.sleep(VERIFY_BASE_DELAY * (2 ** (attempt - 1)))
                continue
            last_unknown = {"doi": d, "status": "unknown", "agency": name,
                            "error": error}
            break
        time.sleep(0.1)
    if last_unknown:
        return last_unknown
    return {"doi": d, "status": "absent", "agency": None}


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="sources.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    p_find = sub.add_parser(
        "find", help="Search Crossref/OpenAlex for citable sources on a topic.")
    p_find.add_argument("topic", help="Topic to search for, e.g. 'retrieval augmented generation'")
    p_find.add_argument("--n", type=int, default=12, help="Maximum results to return (default: 12)")
    p_find.add_argument("--json", action="store_true",
                         help="Print the raw JSON array instead of a human-readable list. "
                              "This is the format scripts/citations.py build expects.")
    preprint_group = p_find.add_mutually_exclusive_group()
    preprint_group.add_argument(
        "--include-preprints", dest="include_preprints", action="store_true", default=True,
        help="Include Crossref posted-content such as arXiv/SSRN preprints (default).")
    preprint_group.add_argument(
        "--no-preprints", dest="include_preprints", action="store_false",
        help="Exclude posted-content entirely (journal articles, proceedings, "
             "chapters, reports, monographs only).")

    p_verify = sub.add_parser(
        "verify", help="Verify one or more DOIs resolve via Crossref then DataCite.")
    p_verify.add_argument("dois", nargs="+", help="One or more DOIs to verify")

    return parser


def _print_human(results):
    if not results:
        print("No citable sources found.")
        return
    for r in results:
        names = ", ".join(_display_name(a) for a in r["authors"][:3])
        if len(r["authors"]) > 3:
            names += " et al."
        venue = r.get("venue") or "(no venue)"
        print(f"{r['doi']}  [{r.get('type')}]")
        print(f"    {r['title']}")
        print(f"    {names} ({r.get('year')}) - {venue}")


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "find":
        status = {}
        results = find(args.topic, n=args.n,
                       include_preprints=args.include_preprints, status=status)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            _print_human(results)
        # "No sources exist for this topic" and "no search reached an API" are
        # different facts and must not share an exit code. If every API this
        # call tried raised, the search never happened.
        attempted, failed = status.get("attempted", []), status.get("failed", [])
        if attempted and len(failed) == len(attempted):
            print(f"# no source API could be reached ({', '.join(failed)}); "
                  "this is a failed search, not an empty topic", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "verify":
        res = [verify(d) for d in args.dois]
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] != "resolved" for r in res) else 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
