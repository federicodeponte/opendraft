#!/usr/bin/env python3
"""Citation database and deterministic compile step for the opendraft skill.

No API key, standard library only. `verify` reuses the exact Crossref/DataCite
resolution in sources.py; `compile` and `bibtex` are pure, deterministic
dictionary lookups with no model involved.

`compile` refuses to render a citation whose `verified` field is not
`resolved`, which is what makes "every printed DOI resolved at Crossref or
DataCite" a fact about the output rather than a hope about the process.

    citations.py build <sources.json> -o research/citations.json
    citations.py verify -d research/citations.json
    citations.py compile <draft.md> -d research/citations.json --style apa -o out.md
    citations.py bibtex -d research/citations.json -o refs.bib

Placeholders in a draft look like {cite_<doi>}, e.g. {cite_10.1038/s41586-021-03819-2}.
Styles: apa, mla, chicago, harvard (author-year, alphabetical bibliography);
ieee, vancouver (numeric, numbered by first appearance in the text).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources  # noqa: E402  (needs the sys.path insert above)

AUTHOR_YEAR_STYLES = {"apa", "mla", "chicago", "harvard"}
NUMERIC_STYLES = {"ieee", "vancouver"}
ALL_STYLES = AUTHOR_YEAR_STYLES | NUMERIC_STYLES

DB_VERSION = 1

CITE_PATTERN = re.compile(r"\{cite_([^}]+)\}")

# `{cite_MISSING: <description>}` is not a DOI placeholder. It is the drafter
# saying, in the draft, that a claim has no source yet. CITE_PATTERN matches it
# too -- group(1) would be the literal string "MISSING: <description>" -- so
# every consumer of CITE_PATTERN filters it out and the specific error wins over
# a misleading "not found in the database".
MISSING_CITE = re.compile(r"\{cite_MISSING\s*:?\s*([^}]*)\}")


def _cite_matches(text):
    """CITE_PATTERN matches that are real DOI placeholders."""
    return [m for m in CITE_PATTERN.finditer(text)
            if not MISSING_CITE.fullmatch(m.group(0))]


def _cited_dois(text):
    return {sources._norm_doi(m.group(1)) for m in _cite_matches(text)}

# Author token used for a record with no named author, in the in-text marker and
# at the head of the bibliography entry alike. One token, both places, so the
# integrity gate can match them; the alternative was a truncated title in the
# marker that nothing could ever resolve.
ANON_AUTHOR = "Anon."


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _normalize_record(raw):
    """Normalize one scripts/sources.py find --json record into a DB entry."""
    doi = sources._norm_doi(raw.get("doi"))
    authors = []
    for a in raw.get("authors") or []:
        if isinstance(a, dict):
            family = (a.get("family") or "").strip()
            given = (a.get("given") or "").strip()
        else:
            # Backward-compatible with a plain family-name string.
            family, given = str(a).strip(), ""
        if family or given:
            authors.append({"family": family, "given": given})
    return {
        "doi": doi,
        "title": (raw.get("title") or "").strip(),
        "authors": authors,
        "year": raw.get("year"),
        "venue": (raw.get("venue") or "").strip(),
        "publisher": (raw.get("publisher") or "").strip(),
        "type": raw.get("type") or "misc",
        "url": raw.get("url") or (f"https://doi.org/{doi}" if doi else ""),
        "verified": raw.get("verified", "unknown"),
    }


class DatabaseError(Exception):
    """A citation database that cannot be read, or is not shaped like one.

    Named on purpose: a wrong-shaped database used to surface downstream as
    "placeholder not found in the database" for a DOI that is plainly sitting
    in the file, which sends a model hunting for a missing source that was
    never missing, and from there to inventing a replacement."""


_SCHEMA_HINT = ("Rebuild it with: python3 scripts/citations.py build "
                "research/sources.json -o research/citations.json")


def _validate_database(data, path):
    """Fail on a wrong-shaped database here, where the error still names the
    real problem."""
    if not isinstance(data, dict):
        raise DatabaseError(
            f"{path} is a {type(data).__name__}, not a citation database object. "
            f"Expected an object with a 'citations' member keyed by DOI. {_SCHEMA_HINT}")

    citations = data.get("citations", {})
    if not isinstance(citations, dict):
        raise DatabaseError(
            f"{path}: 'citations' is a {type(citations).__name__}, but it must be "
            f"an object keyed by DOI, not a list. {_SCHEMA_HINT}")

    for doi, record in citations.items():
        if not isinstance(record, dict):
            raise DatabaseError(
                f"{path}: citation {doi!r} is a {type(record).__name__}, "
                f"but every citation must be an object. {_SCHEMA_HINT}")
        authors = record.get("authors", [])
        if not isinstance(authors, list):
            raise DatabaseError(
                f"{path}: citation {doi!r} has a non-list 'authors' field. "
                f"Expected a list of {{\"family\", \"given\"}} objects. {_SCHEMA_HINT}")
        for author in authors:
            if not isinstance(author, dict):
                raise DatabaseError(
                    f"{path}: citation {doi!r} has author {author!r} as a bare "
                    f"{type(author).__name__}. Every author must be an object with "
                    f"\"family\" and \"given\" keys. {_SCHEMA_HINT}")
            if "family" not in author and "given" not in author:
                raise DatabaseError(
                    f"{path}: citation {doi!r} has an author object with neither "
                    f"\"family\" nor \"given\". {_SCHEMA_HINT}")
    return data


def load_database(path):
    p = Path(path)
    if not p.exists():
        return {"version": DB_VERSION, "citations": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise DatabaseError(f"{path} is not valid JSON: {e}") from e
    _validate_database(data, path)
    data.setdefault("version", DB_VERSION)
    data.setdefault("citations", {})
    return data


def save_database(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def build_database(sources_json_path, out_path):
    with open(sources_json_path, "r", encoding="utf-8") as f:
        raw_records = json.load(f)
    if not isinstance(raw_records, list):
        raise ValueError(
            f"{sources_json_path} does not look like sources.py find --json output "
            "(expected a JSON array)"
        )

    db = load_database(out_path)
    added, updated = 0, 0
    for raw in raw_records:
        record = _normalize_record(raw)
        if not record["doi"]:
            print(f"# skipping record with no DOI: {record.get('title', '')[:60]!r}",
                  file=sys.stderr)
            continue
        existing = db["citations"].get(record["doi"])
        if existing:
            # Preserve a prior verification result; refresh the bibliographic
            # fields in case the source was re-fetched with better metadata.
            record["verified"] = existing.get("verified", "unknown")
            updated += 1
        else:
            added += 1
        db["citations"][record["doi"]] = record

    save_database(out_path, db)
    return {"added": added, "updated": updated, "total": len(db["citations"])}


def verify_database(db_path):
    db = load_database(db_path)
    counts = {"resolved": 0, "absent": 0, "unknown": 0, "invalid": 0}
    failures = []
    for doi, record in sorted(db["citations"].items()):
        result = sources.verify(doi)
        record["verified"] = result["status"]
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if result["status"] in ("absent", "invalid"):
            failures.append((doi, result["status"], result.get("error", "")))
    save_database(db_path, db)
    return counts, failures


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _family_names(citation):
    return [a["family"] for a in citation["authors"] if a.get("family")]


def _full_name(a):
    return f"{a.get('given', '')} {a.get('family', '')}".strip()


def _initials(given):
    return " ".join(f"{part[0]}." for part in given.split() if part)


def _inverted_name(family, given):
    """'Family, Given', with no stranded comma when either half is missing.

    Crossref routinely records a single name part, and sources.py maps that to
    family with an empty given, so f"{family}, {given}" produced "Chen, ." on
    real data. A trailing .strip() cannot remove an interior ", "."""
    parts = [p for p in ((family or "").strip(), (given or "").strip()) if p]
    return ", ".join(parts)


def _initial_name(a):
    """Family, G. I. -- the initials-first form used by APA/IEEE/Vancouver."""
    return _inverted_name(a.get("family"), _initials(a.get("given") or ""))


def _sort_key(citation):
    families = _family_names(citation)
    # Sorted under the token the entry actually prints under, not the title.
    head = families[0].lower() if families else ANON_AUTHOR.lower()
    # A surname alone is not unique. Two entries by different Chens used to
    # land in whatever order the dict happened to iterate, so the same database
    # could compile to two different bibliographies on two runs. Year, then
    # title, then DOI makes the order total and reproducible.
    return (head,
            str(citation.get("year") or ""),
            (citation.get("title") or "").lower(),
            citation.get("doi") or "")


def _italic_md(text):
    return f"*{text}*" if text else ""


# Styles print a press for book-like sources and a venue for articles. Crossref
# reports a `publisher` for journal articles too (the imprint that owns the
# journal, for example "Springer Nature"), which no style prints in a reference
# list, so `publisher` is carried in every record but only rendered for the
# types where a press actually belongs.
_PRESS_TYPES = {"book", "book-chapter", "book-section", "book-part",
                "monograph", "edited-book", "reference-book",
                "report", "report-component", "thesis", "dissertation"}


def _publisher_of(citation):
    """The press this record should print, or "" when the style would omit it."""
    publisher = (citation.get("publisher") or "").strip()
    if not publisher:
        return ""
    if (citation.get("type") or "").strip().lower() not in _PRESS_TYPES:
        return ""
    if publisher.lower() == (citation.get("venue") or "").strip().lower():
        return ""
    return publisher


def _doi_url(citation):
    if citation.get("url"):
        return citation["url"]
    if citation.get("doi"):
        return f"https://doi.org/{citation['doi']}"
    return ""


# --- in-text markers --------------------------------------------------------

def format_in_text(style, citation, number=None):
    if style in NUMERIC_STYLES:
        return f"[{number}]"

    families = _family_names(citation)
    year = str(citation.get("year") or "n.d.")
    if not families:
        # A truncated title made an in-text marker no reader and no checker
        # could match: "(Alpha Study of Carbon Pricing, 2023)" is not a
        # surname, and the bibliography entry it points at never claimed to be
        # one. ANON_AUTHOR is used in the marker AND at the head of the
        # bibliography entry, so the two agree and the gate can join them.
        author_part = ANON_AUTHOR
    elif len(families) == 1:
        author_part = families[0]
    elif len(families) == 2:
        sep = "&" if style == "apa" else "and"
        author_part = f"{families[0]} {sep} {families[1]}"
    else:
        author_part = f"{families[0]} et al."

    if style == "mla":
        return f"({author_part})"
    return f"({author_part}, {year})"


# --- bibliography entries ---------------------------------------------------

def _end_period(s):
    """Append a period unless the string already ends with one (avoids
    'R..' when the last token is already an initial like 'R.')."""
    return s if s.endswith(".") else s + "."


def _format_authors_apa(citation):
    authors = citation["authors"]
    if not authors:
        return ANON_AUTHOR
    names = [_initial_name(a) for a in authors]
    if len(names) == 1:
        return _end_period(names[0])
    if len(names) == 2:
        return f"{names[0]}, & {_end_period(names[1])}"
    if len(names) <= 7:
        return ", ".join(names[:-1]) + f", & {_end_period(names[-1])}"
    return ", ".join(names[:6]) + f", ... & {_end_period(names[-1])}"


def _format_reference_apa(citation):
    author_str = _format_authors_apa(citation)
    year = str(citation.get("year") or "n.d.")
    title = citation.get("title") or ""
    venue = citation.get("venue") or ""
    url = _doi_url(citation)
    ref = f"{author_str} ({year}). {title}."
    if venue:
        ref += f" {_italic_md(venue)}."
    publisher = _publisher_of(citation)
    if publisher:
        ref += f" {_end_period(publisher)}"
    if url:
        ref += f" {url}"
    return ref.strip()


def _format_authors_mla(citation):
    authors = citation["authors"]
    if not authors:
        return ANON_AUTHOR
    if len(authors) == 1:
        return _end_period(_inverted_name(authors[0].get("family"),
                                          authors[0].get("given")))
    first_name = _inverted_name(authors[0].get("family"), authors[0].get("given"))
    if len(authors) == 2:
        return _end_period(f"{first_name}, and {_full_name(authors[1])}")
    return f"{first_name}, et al."


def _format_reference_mla(citation):
    author_str = _format_authors_mla(citation)
    title = citation.get("title") or ""
    venue = citation.get("venue") or ""
    year = str(citation.get("year") or "n.d.")
    url = _doi_url(citation)
    ref = f'{author_str} "{title}."'
    if venue:
        ref += f" {_italic_md(venue)},"
    publisher = _publisher_of(citation)
    if publisher:
        ref += f" {publisher},"
    # _end_period, not f"{year}.", or a record with no year renders "n.d..".
    ref += f" {_end_period(year)}"
    if url:
        ref += f" {url}."
    return ref.strip()


def _format_authors_chicago(citation):
    authors = citation["authors"]
    if not authors:
        return ANON_AUTHOR
    if len(authors) == 1:
        return _end_period(_inverted_name(authors[0].get("family"),
                                          authors[0].get("given")))
    first_name = _inverted_name(authors[0].get("family"), authors[0].get("given"))
    rest = [_full_name(a) for a in authors[1:]]
    if len(rest) == 1:
        return _end_period(f"{first_name}, and {rest[0]}")
    return _end_period(f"{first_name}, " + ", ".join(rest[:-1]) + f", and {rest[-1]}")


def _format_reference_chicago(citation):
    author_str = _format_authors_chicago(citation)
    year = str(citation.get("year") or "n.d.")
    title = citation.get("title") or ""
    venue = citation.get("venue") or ""
    url = _doi_url(citation)
    # _end_period on the year, or a record with no year renders "n.d.." here.
    ref = f'{author_str} {_end_period(year)} "{title}."'
    if venue:
        ref += f" {_italic_md(venue)}."
    publisher = _publisher_of(citation)
    if publisher:
        ref += f" {_end_period(publisher)}"
    if url:
        ref += f" {url}."
    return ref.strip()


def _format_authors_harvard(citation):
    authors = citation["authors"]
    if not authors:
        return ANON_AUTHOR
    names = [_initial_name(a) for a in authors]
    if len(names) == 1:
        return names[0]
    if len(names) <= 3:
        return ", ".join(names[:-1]) + f" and {names[-1]}"
    return f"{names[0]} et al."


def _format_reference_harvard(citation):
    author_str = _format_authors_harvard(citation)
    year = str(citation.get("year") or "n.d.")
    title = citation.get("title") or ""
    venue = citation.get("venue") or ""
    url = _doi_url(citation)
    ref = f"{author_str} ({year}) '{title}'."
    if venue:
        ref += f" {_italic_md(venue)}."
    publisher = _publisher_of(citation)
    if publisher:
        ref += f" {_end_period(publisher)}"
    if url:
        ref += f" Available at: {url}."
    return ref.strip()


def _format_authors_numeric(citation):
    authors = citation["authors"]
    if not authors:
        return ANON_AUTHOR
    names = [_initial_name(a) for a in authors]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{names[0]}, et al."


def _format_reference_ieee(citation, number):
    author_str = _format_authors_numeric(citation)
    title = citation.get("title") or ""
    venue = citation.get("venue") or ""
    year = str(citation.get("year") or "n.d.")
    url = _doi_url(citation)
    ref = f'[{number}] {author_str}, "{title},"'
    if venue:
        ref += f" {_italic_md(venue)},"
    publisher = _publisher_of(citation)
    if publisher:
        ref += f" {publisher},"
    # _end_period, not f"{year}.", or a record with no year renders "n.d..".
    ref += f" {_end_period(year)}"
    if url:
        ref += f" {url}"
    return ref.strip()


def _format_reference_vancouver(citation, number):
    author_str = _format_authors_numeric(citation)
    title = citation.get("title") or ""
    venue = citation.get("venue") or ""
    year = str(citation.get("year") or "n.d.")
    url = _doi_url(citation)
    ref = f"{number}. {_end_period(author_str)} {title}."
    if venue:
        ref += f" {venue}."
    publisher = _publisher_of(citation)
    if publisher:
        ref += f" {_end_period(publisher)}"
    # _end_period, not f"{year}.", or a record with no year renders "n.d..".
    ref += f" {_end_period(year)}"
    if url:
        ref += f" {url}"
    return ref.strip()


def format_reference(style, citation, number=None):
    if style == "apa":
        return _format_reference_apa(citation)
    if style == "mla":
        return _format_reference_mla(citation)
    if style == "chicago":
        return _format_reference_chicago(citation)
    if style == "harvard":
        return _format_reference_harvard(citation)
    if style == "ieee":
        return _format_reference_ieee(citation, number)
    if style == "vancouver":
        return _format_reference_vancouver(citation, number)
    raise ValueError(f"Unsupported style: {style}")


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

class CompileError(Exception):
    def __init__(self, missing):
        self.missing = missing
        super().__init__(
            "Citation placeholder(s) not found in the database: "
            + ", ".join(f"{{cite_{d}}}" for d in missing)
        )


class UnverifiedCitationError(Exception):
    """A cited DOI is not in state `resolved`.

    The user-facing promise is that every printed DOI resolved at Crossref or
    DataCite. `build` writes `verified: "unknown"` for every record, so without
    this gate the promise was decoration. Refusing to render is what makes it
    survive someone checking it."""

    def __init__(self, offenders):
        self.offenders = offenders
        listed = ", ".join(f"{doi} ({status})" for doi, status in offenders)
        super().__init__(
            "Refusing to render citation(s) whose DOI is not resolved at "
            f"Crossref or DataCite: {listed}. "
            "Run: python3 scripts/citations.py verify -d <database>  "
            "and remove or replace any source that does not resolve."
        )


class MissingSourceError(Exception):
    """The draft still carries `{cite_MISSING: ...}`.

    That marker is a drafter admitting a claim has no source. It is the honest
    thing to write and it is a hard stop: compiling it away would turn an
    admission into a shipped unsourced claim. Every occurrence is named at once,
    with the drafter's own description, so one pass clears them all."""

    def __init__(self, offenders):
        self.offenders = offenders          # list of (lineno, description)
        listed = "; ".join(
            f"line {lineno}: {description}" if description else f"line {lineno}"
            for lineno, description in offenders
        )
        super().__init__(
            f"Refusing to compile {len(offenders)} unsourced claim(s) marked "
            f"{{cite_MISSING: ...}} by the drafter: {listed}. "
            "For each one: find a source with "
            "python3 scripts/sources.py find \"<topic>\" --json > new.json, "
            "merge it into the database with "
            "python3 scripts/citations.py build new.json -o research/citations.json, "
            "and replace the marker with {cite_<doi>} -- or cut the claim. "
            "It cannot ship marked."
        )


def find_missing_source_markers(text):
    """Every `{cite_MISSING: ...}` as (line number, description)."""
    offenders = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in MISSING_CITE.finditer(line):
            offenders.append((lineno, (match.group(1) or "").strip()))
    return offenders


def compile_text(text, db, style):
    """Deterministic placeholder replacement. Raises MissingSourceError naming
    every claim the drafter marked unsourced, CompileError naming every
    placeholder whose DOI is not in the database, and UnverifiedCitationError
    naming every cited DOI that is not `resolved` -- never a silent drop, and
    never an unverified DOI printed as though it had been checked."""
    style = style.lower()
    if style not in ALL_STYLES:
        raise ValueError(f"Unsupported style '{style}'. Choose from: {', '.join(sorted(ALL_STYLES))}")

    # First, because {cite_MISSING: ...} also matches CITE_PATTERN and would
    # otherwise be reported as a DOI that is not in the database.
    marked = find_missing_source_markers(text)
    if marked:
        raise MissingSourceError(marked)

    citations = db["citations"]
    missing = []
    for match in _cite_matches(text):
        doi = sources._norm_doi(match.group(1))
        if doi not in citations:
            missing.append(match.group(1))
    if missing:
        # Report every offending placeholder, not just the first.
        raise CompileError(missing)

    # Only the citations this draft actually prints are gated. An unverified
    # record sitting unused in the database is not a false claim about anything.
    unverified = []
    for doi in sorted(_cited_dois(text)):
        status = citations[doi].get("verified", "unknown")
        if status != "resolved":
            unverified.append((doi, status))
    if unverified:
        raise UnverifiedCitationError(unverified)

    numeric = style in NUMERIC_STYLES
    order = []          # DOIs in first-appearance order (numeric styles)
    number_of = {}

    def replace(match):
        raw = match.group(1)
        doi = sources._norm_doi(raw)
        if numeric:
            if doi not in number_of:
                number_of[doi] = len(order) + 1
                order.append(doi)
            return format_in_text(style, citations[doi], number=number_of[doi])
        return format_in_text(style, citations[doi])

    compiled = CITE_PATTERN.sub(replace, text)

    if numeric:
        cited_dois = order
    else:
        cited_dois = sorted(
            _cited_dois(text),
            key=lambda d: _sort_key(citations[d]),
        )

    bib_lines = ["## References", ""]
    if not cited_dois:
        bib_lines.append("(No citations found)")
    elif numeric:
        for doi in cited_dois:
            bib_lines.append(format_reference(style, citations[doi], number=number_of[doi]))
            bib_lines.append("")
    else:
        for doi in cited_dois:
            bib_lines.append(format_reference(style, citations[doi]))
            bib_lines.append("")

    compiled = compiled.rstrip() + "\n\n" + "\n".join(bib_lines).rstrip() + "\n"
    return compiled


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------

_TYPE_TO_BIBTEX = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book-chapter": "incollection",
    "monograph": "book",
    "book": "book",
    "report": "techreport",
    "posted-content": "misc",
}


def _bibtex_key(citation, used_keys):
    families = _family_names(citation)
    base_author = re.sub(r"[^a-z0-9]", "", (families[0] if families else "anon").lower()) or "anon"
    year = str(citation.get("year") or "nd")
    title_words = re.findall(r"[A-Za-z0-9]+", citation.get("title") or "")
    slug = title_words[0].lower() if title_words else ""
    base = f"{base_author}{year}{slug}"
    key = base
    suffix = ord("a")
    while key in used_keys:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    used_keys.add(key)
    return key


def _bibtex_escape(text):
    return (text or "").replace("{", "\\{").replace("}", "\\}")


def to_bibtex(db):
    used_keys = set()
    entries = []
    for doi in sorted(db["citations"]):
        c = db["citations"][doi]
        entry_type = _TYPE_TO_BIBTEX.get(c.get("type"), "misc")
        key = _bibtex_key(c, used_keys)
        fields = []
        authors = c["authors"]
        if authors:
            author_field = " and ".join(
                _inverted_name(a.get("family"), a.get("given")) for a in authors
            )
            fields.append(("author", author_field))
        if c.get("title"):
            fields.append(("title", c["title"]))
        if c.get("year"):
            fields.append(("year", str(c["year"])))
        venue = c.get("venue") or ""
        if venue:
            if entry_type == "article":
                fields.append(("journal", venue))
            elif entry_type in ("inproceedings",):
                fields.append(("booktitle", venue))
            elif entry_type == "incollection":
                fields.append(("booktitle", venue))
            else:
                fields.append(("note", venue))
        if (c.get("publisher") or "").strip():
            fields.append(("publisher", c["publisher"].strip()))
        if c.get("doi"):
            fields.append(("doi", c["doi"]))
        if c.get("url"):
            fields.append(("url", c["url"]))
        body = ",\n".join(f"  {name} = {{{_bibtex_escape(value)}}}" for name, value in fields)
        entries.append(f"@{entry_type}{{{key},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser():
    parser = argparse.ArgumentParser(
        prog="citations.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    p_build = sub.add_parser("build", help="Build/merge a citation database from sources.py find --json output.")
    p_build.add_argument("sources_json", help="Path to a JSON array from `sources.py find --json`")
    p_build.add_argument("-o", "--output", required=True, help="Path to write/merge research/citations.json")

    p_verify = sub.add_parser("verify", help="Re-verify every DOI in the database via Crossref/DataCite.")
    p_verify.add_argument("-d", "--database", required=True, help="Path to citations.json")

    p_compile = sub.add_parser("compile", help="Replace {cite_<doi>} placeholders and append a bibliography.")
    p_compile.add_argument("draft", help="Path to the draft markdown file")
    p_compile.add_argument("-d", "--database", required=True, help="Path to citations.json")
    p_compile.add_argument("--style", required=True, choices=sorted(ALL_STYLES),
                            help="Citation style: apa, mla, chicago, harvard (author-year) "
                                 "or ieee, vancouver (numeric)")
    p_compile.add_argument("-o", "--output", required=True, help="Path to write the compiled markdown")

    p_bibtex = sub.add_parser("bibtex", help="Emit a BibTeX file for every citation in the database.")
    p_bibtex.add_argument("-d", "--database", required=True, help="Path to citations.json")
    p_bibtex.add_argument("-o", "--output", required=True, help="Path to write the .bib file")

    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "build":
        try:
            stats = build_database(args.sources_json, args.output)
        except (OSError, json.JSONDecodeError, ValueError, DatabaseError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Added {stats['added']}, updated {stats['updated']}, "
              f"total {stats['total']} citations in {args.output}")
        return 0

    if args.cmd == "verify":
        if not Path(args.database).exists():
            print(f"Error: database not found: {args.database}", file=sys.stderr)
            return 1
        try:
            counts, failures = verify_database(args.database)
        except (OSError, DatabaseError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"resolved={counts.get('resolved', 0)} "
              f"absent={counts.get('absent', 0)} "
              f"unknown={counts.get('unknown', 0)} "
              f"invalid={counts.get('invalid', 0)}")
        if failures:
            print("Failing DOIs:", file=sys.stderr)
            for doi, status, error in failures:
                print(f"  {doi}: {status} {error}".rstrip(), file=sys.stderr)
            return 1
        return 0

    if args.cmd == "compile":
        if not Path(args.database).exists():
            print(f"Error: database not found: {args.database}", file=sys.stderr)
            return 1
        if not Path(args.draft).exists():
            print(f"Error: draft not found: {args.draft}", file=sys.stderr)
            return 1
        try:
            db = load_database(args.database)
            text = Path(args.draft).read_text(encoding="utf-8")
            compiled = compile_text(text, db, args.style)
        except (MissingSourceError, CompileError, UnverifiedCitationError,
                DatabaseError, ValueError, OSError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(compiled, encoding="utf-8")
        print(f"Compiled {args.draft} -> {args.output} ({args.style})")
        return 0

    if args.cmd == "bibtex":
        if not Path(args.database).exists():
            print(f"Error: database not found: {args.database}", file=sys.stderr)
            return 1
        try:
            db = load_database(args.database)
        except (OSError, DatabaseError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        bib = to_bibtex(db)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(bib, encoding="utf-8")
        print(f"Wrote {len(db['citations'])} entries to {args.output}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
