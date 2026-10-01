#!/usr/bin/env python3
"""Automated integrity gate for a compiled research draft.

Standard library only. Runs the five-point manual checklist an editor would
otherwise do by eye, plus a word-count and leftover-template-text check.
Prints nothing and exits 0 on a clean pass (loop-usable); prints every
failure with a line number and exits nonzero otherwise.

    integrity.py <draft.md> -d research/citations.json [--target N --tolerance 0.1]

Checks:
  0. No {cite_MISSING: ...} markers. That marker is a drafter declaring a claim
     they could not source; it is honest, and it is fatal. Each one is reported
     with the drafter's own description of the claim.
  1. No surviving {cite_...} placeholders (compile should have replaced all).
  2. Every bibliography entry is pointed to by at least one in-text marker.
  3. Every in-text marker resolves to a bibliography entry; an author-year
     marker must match on surname AND year, and a numeric [n] marker must land
     on bibliography entry n.
  4. No stranded punctuation where a marker was removed (" .", " ,", " ;", or a
     double space left between two words). Markdown tables, list items and
     fenced code blocks are exempt: aligned columns and indented code are not
     deleted markers, and a gate that fires on them damages a correct paper.
  5. A numeric bibliography (IEEE/Vancouver) carries its reference numbers.
  6. Word count within --tolerance of --target, if given. Prose words only:
     a counted token has to contain at least one letter or digit, so pipes,
     rules, bullets and hashes do not inflate the count.
  7. No leftover template/placeholder text (TODO, FIXME, TK, XXX, Lorem ipsum,
     "[insert", "your name here", ...).
  8. No surviving bracketed authoring slot, e.g. "[figure from summaries.md]".
     agents/07-crafter.md, agents/17-abstract.md and agents/05-architect.md
     all teach drafting with these; a slot left unfilled is a number nobody
     found, and a slot silently replaced with a plausible-looking one is a
     fabrication that every other check in this file is blind to.
  9. (only with -d/--database) every DOI printed in the compiled bibliography
     is present in the database with verified == "resolved". Skipped, and
     said so in the failure report, when -d is not given.

The brief's own numbers (only with -b/--brief, or the equivalent flags). Each
of these is a requirement the person asking for the paper stated in words, not
a house preference of this pipeline, which is why none of them has a default:
absent a stated number nothing is checked.
 11. Main text inside the word range they asked for. Main text means the body:
     the compiled reference list and the abstract are both excluded, because a
     brief that caps "the main text at 6,000 words and the abstract at 200"
     is counting them separately and so is this.
 12. The reference list carries at least the number of entries they asked for.
 13. An abstract (or the summary a document type calls instead) is present and
     inside its stated cap.
 14. Every section they named by name exists as a heading.

Advisory, reported but never fatal:
 15. (only with -c/--corpus) every number in the draft that appears nowhere in
     research/summaries.md. This is the half of check 8 that check 8 cannot
     reach: a bracketed slot left unfilled is caught there, a slot quietly
     replaced with an invented number is caught by nothing. It does not exit
     nonzero, because a number legitimately derived from the corpus also
     appears nowhere in it, and this script cannot tell the two apart.

--stats prints the four numbers checks 11 to 14 measure and exits 0 without
checking anything, so a draft can be counted while it is still being written.
An estimate of a word count is not a word count; this is the command that
turns "about the right length" into a number before delivery, not after.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import citations  # noqa: E402  (needs the sys.path insert above)
import sources  # noqa: E402

CITE_PLACEHOLDER = re.compile(r"\{cite_[^}]*\}")

# {cite_MISSING: Kirkwood's disposable soma theory} is a drafter saying "this
# claim is real and I could not source it". It is a deliberate, honest marker,
# not a typo, and it is not a route to shipping the claim: it is guaranteed to
# stop this gate. It gets its own message because "unresolved placeholder
# '{cite_MISSING: ...}'" sends the reader looking for a DOI in a database that
# was never supposed to hold one, and the fix is different -- find a source, or
# cut the claim.
MISSING_CITE = re.compile(r"\{cite_MISSING\s*:?\s*([^}]*)\}")

# One name token: unicode-aware, so "Muller" with an umlaut is a surname and not
# a single letter "M" followed by an unmatchable remainder.
_NAME = r"[^\W\d_][\w'’\-]*"  # U+2019 added: typographic apostrophe, e.g. "Dall’Ora"
# ... constrained to start with something that is not lower case, which is what
# keeps ordinary prose parentheticals like "(approximately 2020)" from being
# read as citation markers.
_NAME_UPPER = r"(?![a-zà-öø-ÿ])" + _NAME

# Nobiliary/prepositional surname particles: German ("von", "van der"), Dutch
# ("van", "van den"), Spanish/Portuguese ("de", "del", "dos", "da"), Italian
# ("della", "di", "da"), French ("de", "du", "la", "le"), and Arabic ("al-").
# Listed as single words -- "van der" / "van den" / "von der" are just two of
# these back to back, which the one-or-more repetition below covers without
# hardcoding every two-word combination. Matched case-insensitively: APA
# capitalises the leading particle only when it opens a sentence or a
# reference-list entry (bibliography "Von Haaren, B. (2015)."), and leaves it
# lower case everywhere else, including in-text "(von Haaren, 2015)".
_PARTICLE = r"(?:al|bin|da|de|del|della|den|der|di|dos|du|la|le|ten|ter|van|von|zu)"
# One or more particles, each glued to what follows by whitespace, or by a
# hyphen for the Arabic "al-" form ("al-Rashid"), then the surname itself.
# The surname still has to pass _NAME_UPPER, so a bare lower-case word that
# happens to be a particle ("(de facto standard, 2020)") still fails to
# match: "facto" is lower case and the whole thing is rejected, same as
# before this addition existed.
_SURNAME = r"(?:(?i:" + _PARTICLE + r")[-\s]+)*" + _NAME_UPPER
# Same, but for the second author in "(Smith & von Neumann, 2024)": the
# original code let that slot be any case (bare _NAME, not _NAME_UPPER)
# because it is never mistaken for prose the way the marker's opening word
# is, and this keeps that looseness while adding particle support.
_SURNAME_LOOSE = r"(?:(?i:" + _PARTICLE + r")[-\s]+)*" + _NAME + r"(?:\s" + _NAME_UPPER + r")*"  # multi-word surnames, e.g. "von Thiele Schwarz"

# Author-year marker: (Family, 2024) / (Family & Family, 2024) / (Family et al., 2024)
# The year is OPTIONAL because MLA in-text markers carry no year at all: they
# are just "(Family)". A marker whose year group is None is matched on surname
# alone, and only against a surname that is actually in the bibliography (see
# check_markers_and_bibliography), so "(RAG)" in prose stays prose.
AUTHOR_YEAR_MARKER = re.compile(
    r"\((" + _SURNAME + r"(?:\s(?:&|and|et al\.)(?:\s" + _SURNAME_LOOSE + r")?)?)"
    r"\.?(?:(?:,\s*|\s+)(\d{4}|n\.d\.))?\)"
)
# Numeric marker: [12] or [1, 2] or [1-3] -- capture the raw bracket contents.
NUMERIC_MARKER = re.compile(r"\[(\d+(?:\s*[,\-]\s*\d+)*)\]")

# A numeric bibliography line starts with "N." or "[N]".
NUMERIC_BIB_LINE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\.)\s+\S")

# The leading name of a bibliography entry, particle included (see _SURNAME
# above), unicode-aware to match _NAME.
BIB_SURNAME = re.compile(r"^\s*(" + _SURNAME + r")")

# A four-digit year in a bibliography entry, restricted to 19xx/20xx and to
# positions not inside a longer digit run, so DOI fragments are not read as
# publication years.
BIB_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

# URLs are stripped before year extraction: a DOI such as 10.2019/foo would
# otherwise donate a spurious year to the entry it belongs to.
URL_RE = re.compile(r"(?:https?://|doi:)\S+")

# Markdown structure that the stranded-punctuation check must not read as prose.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
TABLE_ROW_RE = re.compile(r"^\s*\|")
TABLE_RULE_RE = re.compile(r"^\s*:?-{3,}:?(?:\s*\|\s*:?-+:?)+\s*$")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
INDENTED_CODE_RE = re.compile(r"^(?: {4}|\t)")
# A line like {figure:evidence-map} is where the journal export places a figure,
# table or the index equations drawn by scripts/evidence.py. It is layout, not
# prose, so it counts toward no word total.
EVIDENCE_PLACEHOLDER_RE = re.compile(r"^\s*\{(?:figure|table|equations):[a-z0-9-]+\}\s*$")

# " ." / " ," / " ;" / " :" left where a marker used to sit. Two things look
# like this and are not that, and both are text a paper is required to contain:
#   - a decimal written without its leading zero ("P < .001", "r = .42"), which
#     AMA, Vancouver and APA-7 all mandate for a statistic bounded by one;
#   - a spaced ellipsis marking an elision inside a quotation.
# Neither can be produced by deleting an in-text marker, which is the only thing
# this check exists to find. Flagging them was worse than a nuisance: the
# message named a cause that did not exist, so every repair an agent reached for
# was wrong, and the only route to exit 0 was to make the paper break its own
# field's notation. A gate that can only be satisfied by corrupting correct
# writing is not a gate.
SPACE_BEFORE_PUNCT = re.compile(r"(?<= )(?<!\. )(?:\.(?![\d.])(?!\s\.)|[,;:])")
# A double space between two words, which is what deleting an in-text marker
# actually leaves behind. Deliberately narrow: two spaces after a sentence-final
# period, or column alignment, are not defects.
MID_SENTENCE_DOUBLE_SPACE = re.compile(r"(?<=[a-zà-öø-ÿ,;:])\s{2,}(?=[a-zà-öø-ÿ])")

# A bracketed run with no nested brackets and no newline, so a slot never
# reaches across a line break the way NUMERIC_MARKER above never does either.
_BRACKET_RE = re.compile(r"\[([^\[\]\n]*)\]")

# A pure numeric citation marker's contents: "1", "12", "1, 4", "2-5", or
# "2-5" with an en dash, the exact shapes NUMERIC_MARKER above matches.
_NUMERIC_BRACKET = re.compile(r"^\d+(?:\s*[,\-–]\s*\d+)*$")

# Vocabulary drawn directly from the bracketed slots actually written in
# agents/07-crafter.md, agents/17-abstract.md and agents/05-architect.md: the
# nouns a slot asks for (a figure, a value, a range...) and the verbs that
# introduce an instruction to go find one (name, states, reports...). This is
# deliberately not a generic "suspicious bracket" heuristic; every word here
# was pulled from a real slot in one of those three files, which is what
# keeps it from firing on an editorial bracket in a direct quotation, since
# "[sic]", "[the authors]" and "[emphasis added]" use none of this
# vocabulary.
_SLOT_VOCAB = re.compile(
    r"\b(?:"
    r"figure|value|range|effect|dataset|cohorts?|populations?|period|"
    r"finding|indicators?|metrics?|statistics?|contribution|implication|"
    r"approach|techniques?|outcome|methods?|mechanism|directions?|audience|"
    r"decisions?|problem|gap|actual(?:ly)?|verbatim|unsourced|terms?|"
    r"summaries\.md|gaps\.md|citations\.json|"
    r"named?|states?|reports?|draws?|frames?|demonstrat\w*|records?"
    r")\b", re.IGNORECASE)

# "the introduction/methodology/results/discussion/conclusion/body ... names
# / states / reports / draws / frames / uses / demonstrates / needs..." -- the
# shape most of the stage-17 abstract slots are built from, even the handful
# whose individual words (e.g. "the second contribution as the conclusion
# states it") are too generic on their own to vocabulary-match reliably.
_SECTION_VERB = re.compile(
    r"\bthe\s+(?:introduction|methodology(?:\s+section)?|results?(?:\s+section)?|"
    r"discussion|conclusion|body(?:'s)?)\b.{0,60}?\b(?:states?|names?|draws?|"
    r"frames?|uses?|reports?|records?|demonstrat\w*|needs?)\b",
    re.IGNORECASE | re.DOTALL)

TEMPLATE_MARKERS = [
    r"\bTODO\b", r"\bFIXME\b", r"\bTK\b", r"\bXXX\b",
    r"Lorem ipsum", r"\[insert\b", r"your name here",
    r"\[TBD\]", r"\bplaceholder text\b",
    # The attribution line belongs in conversation with the user, never inside
    # the paper. Catching it here makes that a rule the gate enforces rather
    # than an instruction a model can forget.
    r"Built with opendraft",
]
TEMPLATE_RE = re.compile("|".join(TEMPLATE_MARKERS), re.IGNORECASE)


def _lines_with_matches(text, pattern):
    for i, line in enumerate(text.splitlines(), start=1):
        for m in pattern.finditer(line):
            yield i, line, m


def find_bibliography_start(lines):
    for i, line in enumerate(lines):
        if re.match(r"^#{1,3}\s*References\b", line, re.IGNORECASE) or \
           re.match(r"^#{1,3}\s*Bibliography\b", line, re.IGNORECASE):
            return i
    return None


def check_missing_sources(text):
    """Every {cite_MISSING: ...} in the draft, one critical issue each.

    The marker exists so a drafter who cannot source a real claim can say so
    instead of dropping the evidence or inventing a DOI. Saying so is where its
    usefulness ends: an unsourced claim never ships, so each occurrence fails
    the gate, by name, with the description the drafter wrote."""
    failures = []
    for lineno, _line, m in _lines_with_matches(text, MISSING_CITE):
        described = (m.group(1) or "").strip()
        what = f": {described}" if described else ""
        failures.append(
            f"line {lineno}: unsourced claim marked by the drafter{what}. "
            f"Find a source with scripts/sources.py find, add it to the "
            f"database, and cite it, or cut the claim. It cannot ship marked.")
    return failures


def check_placeholders(text):
    failures = []
    for lineno, line, m in _lines_with_matches(text, CITE_PLACEHOLDER):
        # {cite_MISSING: ...} is reported by check_missing_sources, which knows
        # what it is and what to do about it.
        if MISSING_CITE.fullmatch(m.group(0)):
            continue
        failures.append(f"line {lineno}: unresolved placeholder {m.group(0)!r}")
    return failures


def _extract_body_and_bib(text):
    lines = text.splitlines()
    bib_start = find_bibliography_start(lines)
    if bib_start is None:
        return text, [], None
    body = "\n".join(lines[:bib_start])
    bib_lines = lines[bib_start + 1:]
    return body, bib_lines, bib_start + 1  # 1-indexed line of first bib line


def check_markers_and_bibliography(text):
    """Checks 2, 3 and 5 together since they all need the body/bibliography split."""
    failures = []
    body, bib_lines, bib_first_lineno = _extract_body_and_bib(text)

    if bib_first_lineno is None:
        # Only a marker that carries a year is unambiguous enough to demand a
        # bibliography on its own. A bare "(RAG)" in a document with no
        # References section is an abbreviation, not a dangling citation.
        dated_marker = any(m.group(2) for m in AUTHOR_YEAR_MARKER.finditer(body))
        if dated_marker or NUMERIC_MARKER.search(body):
            failures.append("no References/Bibliography section found, but in-text markers are present")
        return failures

    non_empty_bib = [(idx, line) for idx, line in enumerate(bib_lines) if line.strip()]
    is_numeric_bib = bool(non_empty_bib) and all(
        NUMERIC_BIB_LINE.match(line) for _, line in non_empty_bib
    )

    if is_numeric_bib:
        bib_numbers = set()
        for idx, line in non_empty_bib:
            m = NUMERIC_BIB_LINE.match(line)
            num = int(m.group(1) or m.group(2))
            if num in bib_numbers:
                failures.append(f"line {bib_first_lineno + idx}: duplicate bibliography number [{num}]")
            bib_numbers.add(num)

        cited_numbers = set()
        for lineno, line, m in _lines_with_matches(body, NUMERIC_MARKER):
            for piece in re.split(r"\s*,\s*", m.group(1)):
                if "-" in piece:
                    lo, hi = piece.split("-")
                    nums = range(int(lo), int(hi) + 1)
                else:
                    nums = [int(piece)]
                for num in nums:
                    cited_numbers.add(num)
                    if num not in bib_numbers:
                        failures.append(
                            f"line {lineno}: in-text marker [{num}] has no matching "
                            f"bibliography entry {num}"
                        )
        for num in sorted(bib_numbers - cited_numbers):
            failures.append(f"bibliography entry {num} is never cited in the text")
    else:
        # Author-year bibliography: match on surname AND year, so two different
        # Smiths in the same reference list no longer satisfy each other's
        # markers. Each entry keeps every year it names; a marker matches an
        # entry when the surnames agree and the marker's year is one of them.
        entries = []
        for idx, line in non_empty_bib:
            m = BIB_SURNAME.match(line)
            entries.append({
                "lineno": bib_first_lineno + idx,
                "surname": m.group(1).lower() if m else None,
                "years": set(BIB_YEAR.findall(URL_RE.sub(" ", line))),
                "line": line,
            })

        cited = set()
        for lineno, line, m in _lines_with_matches(body, AUTHOR_YEAR_MARKER):
            family = re.split(r"\s(?:&|and|et al\.)", m.group(1))[0].strip().rstrip(".")
            year = m.group(2)
            surname_hits = [i for i, e in enumerate(entries)
                            if e["surname"] == family.lower()]
            if year is None:
                # MLA: the marker carries no year, so surname is all there is.
                # A parenthetical matching no bibliography surname is ordinary
                # prose, not a broken citation, and is left alone.
                cited.update(surname_hits)
                continue
            hits = [i for i in surname_hits if _year_matches(year, entries[i]["years"])]
            if not hits:
                failures.append(
                    f"line {lineno}: in-text marker citing {family!r} ({year}) has no "
                    f"matching bibliography entry"
                )
            cited.update(hits)

        for i, e in enumerate(entries):
            if e["surname"] and i not in cited:
                failures.append(
                    f"line {e['lineno']}: bibliography entry "
                    f"{e['line'].strip()[:60]!r} is never cited in the text")

    return failures


def _year_matches(marker_year, entry_years):
    """True when a marker's year is consistent with a bibliography entry.

    An entry that names no year at all cannot contradict anything, so it
    matches: the alternative is failing a correct paper over metadata the
    formatter never had."""
    if not entry_years:
        return True
    if marker_year == "n.d.":
        return False
    return marker_year in entry_years


def _prose_lines(body):
    """Yield (lineno, line) for lines that are running prose.

    Fenced code blocks, markdown table rows and rules, list markers and indented
    code are structure, not sentences. Column alignment inside a table and the
    two-space indent of a nested bullet are the exact shapes the old
    double-space rule mistook for a deleted citation marker, and the skill's own
    stage 5 requires a synthesis table, so this is the common case."""
    in_fence = False
    for lineno, line in enumerate(body.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if TABLE_ROW_RE.match(line) or TABLE_RULE_RE.match(line):
            continue
        if INDENTED_CODE_RE.match(line):
            continue
        if LIST_ITEM_RE.match(line):
            continue
        yield lineno, line


def check_stranded_punctuation(text):
    failures = []
    body, _, _ = _extract_body_and_bib(text)
    for lineno, line in _prose_lines(body):
        for pattern in (SPACE_BEFORE_PUNCT, MID_SENTENCE_DOUBLE_SPACE):
            for m in pattern.finditer(line):
                snippet = line[max(0, m.start() - 15):m.end() + 15].strip()
                failures.append(
                    f"line {lineno}: stranded punctuation/spacing near {snippet!r}")
    return failures


def count_prose_words(text):
    """Words a reader would count, not whitespace-separated tokens.

    A token counts only if it contains a letter or a digit, which drops table
    pipes, horizontal rules, heading hashes and bullet dashes. Fenced code
    blocks are dropped whole: source is not prose, and counting it inflates the
    body against --target by enough to pass a short draft and fail a correct
    one."""
    words = 0
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if EVIDENCE_PLACEHOLDER_RE.match(line):
            continue
        for token in line.split():
            if any(ch.isalnum() for ch in token):
                words += 1
    return words


def check_word_count(text, target, tolerance):
    if target is None:
        return []
    body, _, _ = _extract_body_and_bib(text)
    words = count_prose_words(body)
    lo, hi = target * (1 - tolerance), target * (1 + tolerance)
    if not (lo <= words <= hi):
        return [f"word count {words} is outside target {target} +/-{tolerance:.0%} "
                f"(allowed range {int(lo)}-{int(hi)})"]
    return []


# --- the brief's own numbers ------------------------------------------------
#
# Everything below this line checks the draft against what the person asked
# for, rather than against anything this pipeline decided on its own. A word
# range, a reference minimum, an abstract cap and a list of sections are all
# things a brief states in ordinary words ("about 3,000 words", "a couple of
# dozen sources at least", "the abstract at 200"). Nothing here has a default,
# and a number that was never stated is never checked: the point is to hold the
# draft to the request, not to invent a house style and enforce that instead.

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

# The heading that carries the paper's own summary. Which word a document uses
# for it is a matter of type and language, not of substance: a journal article
# has an abstract, a committee paper has a summary, a German draft has a
# Zusammenfassung. All three are the same section and the same cap applies.
ABSTRACT_TITLE = re.compile(
    r"^(?:abstract|summary|executive\s+summary|key\s+findings|"
    r"zusammenfassung|kurzfassung|r[ée]sum[ée])\b", re.IGNORECASE)


def sections(text):
    """[(level, title, start, end)] for every markdown heading, 0-indexed.

    `start` is the heading's own line; `end` is one past the last line of what
    the heading governs, which runs to the next heading of the same level or
    shallower. Fenced code is skipped, so a `#` comment inside a shell block is
    not a section.
    """
    lines = text.splitlines()
    heads = []
    in_fence = False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        if m:
            heads.append((len(m.group(1)), m.group(2).strip(), i))

    out = []
    for idx, (level, title, start) in enumerate(heads):
        end = len(lines)
        for next_level, _t, next_start in heads[idx + 1:]:
            if next_level <= level:
                end = next_start
                break
        out.append((level, title, start, end))
    return out


def find_abstract(text):
    """(title, lineno, body) for the draft's abstract, or None.

    lineno is 1-indexed, for the failure messages; body is the prose under the
    heading, heading line excluded.
    """
    lines = text.splitlines()
    for _level, title, start, end in sections(text):
        if ABSTRACT_TITLE.match(title):
            return title, start + 1, "\n".join(lines[start + 1:end])
    return None


def count_main_text_words(text):
    """Prose words of the main text: bibliography and abstract both dropped.

    A brief that caps the main text and the abstract separately is counting
    them separately, and folding a 200-word abstract into a 1,200-word cap
    fails a correct draft by a sixth of its length.
    """
    body, _, _ = _extract_body_and_bib(text)
    lines = body.splitlines()
    for _level, title, start, end in sections(body):
        if ABSTRACT_TITLE.match(title):
            lines = lines[:start] + lines[end:]
            break
    return count_prose_words("\n".join(lines))


def count_reference_entries(text):
    """Entries in the compiled reference list.

    `citations.py compile` writes one entry per line, blank-line separated, so
    an entry is a non-empty bibliography line that opens the way an entry opens:
    with its number, in a numeric style, or with a surname in an author-year
    one. A line opening with neither is a continuation or a note, and is not
    counted as a second reference.
    """
    _body, bib_lines, bib_first_lineno = _extract_body_and_bib(text)
    if bib_first_lineno is None:
        return 0
    return sum(1 for line in bib_lines
               if line.strip()
               and (NUMERIC_BIB_LINE.match(line) or BIB_SURNAME.match(line)))


def check_word_range(text, low, high):
    """Main text inside the range the brief asked for."""
    if low is None and high is None:
        return []
    words = count_main_text_words(text)
    asked = (f"{low} to {high}" if low is not None and high is not None
             else f"at least {low}" if low is not None else f"at most {high}")
    if low is not None and words < low:
        return [f"main text is {words} words, under the {asked} words the brief "
                f"asks for. Expand it against the sources, do not pad it."]
    if high is not None and words > high:
        return [f"main text is {words} words, over the {asked} words the brief "
                f"asks for. Cut {words - high} words."]
    return []


def check_reference_count(text, minimum):
    """The reference list meets the minimum the brief stated."""
    if minimum is None:
        return []
    found = count_reference_entries(text)
    if found < minimum:
        return [f"the reference list has {found} entries; the brief asks for at "
                f"least {minimum}. Go back to stage 1, search further, verify "
                f"what comes back, and cite it. Do not lower the number."]
    return []


def check_abstract(text, max_words):
    """An abstract is present, is not empty, and is inside its stated cap."""
    if max_words is None:
        return []
    found = find_abstract(text)
    if found is None:
        return [f"no abstract found. The brief asks for one of at most "
                f"{max_words} words, and no Abstract or Summary heading is in "
                f"the draft."]
    title, lineno, body = found
    words = count_prose_words(body)
    if words == 0:
        return [f"line {lineno}: the {title!r} heading is present but empty"]
    if words > max_words:
        return [f"line {lineno}: the {title!r} section runs {words} words, over "
                f"the {max_words}-word cap the brief states. Cut "
                f"{words - max_words} words."]
    return []


def check_required_sections(text, names):
    """Every section the brief named by name exists as a heading."""
    if not names:
        return []
    titles = [title.lower() for _level, title, _s, _e in sections(text)]
    failures = []
    for name in names:
        wanted = name.strip().lower()
        if not any(wanted in title for title in titles):
            failures.append(
                f"the brief asks for a {name!r} section and no heading in the "
                f"draft matches it")
    return failures


BRIEF_KEYS = ("words_min", "words_max", "word_range", "min_references",
              "abstract_max_words", "required_sections")


class BriefError(Exception):
    pass


def normalise_brief(data):
    """A brief file's contents as {words_min, words_max, min_references, ...}.

    Unknown keys are an error rather than an omission: a brief is written by
    hand from what the user said, and a misspelt key that is silently ignored
    turns a stated requirement into an unchecked one, which is the exact
    failure this file exists to stop.
    """
    if not isinstance(data, dict):
        raise BriefError("a brief file has to be a JSON object with keys from: "
                         + ", ".join(BRIEF_KEYS))
    unknown = sorted(set(data) - set(BRIEF_KEYS))
    if unknown:
        raise BriefError(f"unknown key(s) in the brief file: {', '.join(unknown)}. "
                         f"Accepted keys: {', '.join(BRIEF_KEYS)}")

    brief = {"words_min": data.get("words_min"), "words_max": data.get("words_max")}
    if "word_range" in data:
        pair = data["word_range"]
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            raise BriefError('"word_range" has to be a two-element array, '
                             'for example [2700, 3300]')
        brief["words_min"], brief["words_max"] = pair

    for key in ("words_min", "words_max", "min_references", "abstract_max_words"):
        value = brief.get(key, data.get(key))
        if value is not None and not isinstance(value, int):
            raise BriefError(f'"{key}" has to be a whole number, not {value!r}')
        brief[key] = value

    sections_asked = data.get("required_sections") or []
    if not isinstance(sections_asked, list) or any(
            not isinstance(s, str) for s in sections_asked):
        raise BriefError('"required_sections" has to be an array of strings')
    brief["required_sections"] = sections_asked
    return brief


def load_brief(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BriefError(f"{path} is not valid JSON: {e}") from e
    return normalise_brief(data)


def check_template_text(text):
    failures = []
    for lineno, line, m in _lines_with_matches(text, TEMPLATE_RE):
        failures.append(f"line {lineno}: leftover template text {m.group(0)!r}")
    return failures


def check_bracket_slots(text):
    """A `[bracketed authoring slot]` that survived compile into the draft.

    agents/07-crafter.md, agents/17-abstract.md and agents/05-architect.md all
    teach drafting with placeholders like `[figure from summaries.md]`: a
    value the drafter is supposed to look up in research/summaries.md and
    substitute, never a value to invent. Every one of those files' own "Done
    when" checklists says a surviving slot is a fatal defect, but nothing
    before this check enforced it in code. That gap matters because the real
    failure is silent: {cite_...} placeholders are matched by
    check_placeholders, but nothing stopped a drafter under word-count
    pressure from replacing `[figure from summaries.md]` with a plausible
    invented number instead of leaving the honest slot in place. The DOI
    still resolves, the marker still maps to a bibliography entry, and every
    other check in this file passes; only the number is a fabrication, and
    it looks identical to a real one from the outside. This check makes the
    honest failure (the slot, left in) the only failure shape available, by
    catching it before the dishonest one (a slot quietly filled with
    something invented) ever has a chance to look like it passed.

    The pattern is built from the actual slot vocabulary in those three
    files, not a generic "any bracket" rule: a broad rule would also fire on
    numeric citation markers ("[12]", "[2-5]"), markdown links and images
    ("[text](url)", "![alt](path)"), reference-style links and footnotes
    ("[label][ref]", "[^1]"), and the editorial brackets a direct quotation
    legitimately uses ("the model [sic] performed", "they [the authors]
    argue"). Those five shapes are excluded structurally -- position in the
    line, or a single bare word with no instruction-shaped vocabulary --
    rather than by trying to enumerate every legitimate bracket phrase, which
    is what keeps the exclusion correct for a quotation bracket this file has
    never seen.

    Left uncaught on purpose, rather than shipped imprecise: a single bare
    word in brackets ("[study]", "[topic]", "[terms]", "[Field]", all of
    which appear as real slots in the three files above). A one-word bracket
    is indistinguishable by shape alone from a legitimate editorial
    insertion like "[sic]" or "[Ed.]", so reaching for a bespoke word list to
    catch just those four risks flagging a real one the moment a quoted
    passage includes it. Also left uncaught: "[2-3 sentences]" in
    17-abstract.md, which is a length hint on the template itself (how many
    sentences to write), not a value to look up and substitute the way every
    other bracket in that file is.
    """
    failures = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _BRACKET_RE.finditer(line):
            content = m.group(1).strip()
            if not content:
                continue  # task-list "[ ]"
            if content.startswith("^"):
                continue  # footnote reference: [^1]
            tail = line[m.end():m.end() + 1]
            if tail and tail in "([":
                continue  # markdown link/image/reference-style link
            if len(content.split()) < 2:
                continue  # bare word: numeric marker, "[sic]", "[Ed.]", ...
            if _NUMERIC_BRACKET.match(content):
                continue  # "[1, 4]" etc: the comma still leaves 2 tokens
            if _SLOT_VOCAB.search(content) or _SECTION_VERB.search(content):
                failures.append(
                    f"line {lineno}: bracketed authoring slot survived into "
                    f"the draft: {m.group(0)!r}. It reads as an instruction "
                    f"to the writer, not text meant to ship. Resolve it from "
                    f"the source it names, or rewrite the sentence so the "
                    f"claim it was carrying no longer needs it.")
    return failures


# A number as it appears in a claim: 34, 1,200, 0.83, 34.2, 15. Bounded on both
# sides so a version string, an identifier or a decimal does not decompose into
# several smaller numbers.
#
# The right-hand guard rejects a following digit, with or without a dot between
# ("3.4.5" is a version, not the number 3.4), and a following word character.
# It deliberately allows a bare trailing period, because that is a sentence
# ending. An earlier version wrote this as `(?![\w.])`, which looks equivalent
# and is not: it rejected every number that ends a sentence, so "effect size
# 0.42." in the corpus was extracted as no number at all, and the draft's
# perfectly well-sourced 0.42 was then reported as appearing nowhere. A
# provenance check whose corpus reader silently drops values does not report
# fabrication, it manufactures it.
#
# The left-hand guard also rejects a digit hyphenated onto a word, because
# "COVID-19", "GPT-4" and "T-1000" are names whose tail happens to be a
# numeral. Left in, they would be reported as unsourced numbers in every paper
# whose subject is one of them, which is a large share of the papers this
# skill will ever write.
_CLAIM_NUMBER = re.compile(
    r"(?<![\w.,])(?<![A-Za-z]-)(\d[\d,]*(?:\.\d+)?)(?!\.?\d)(?!\w)")

# A whole numeric citation marker, removed from a line before it is scanned:
# "[12]" and "[2-5]" are pointers to the bibliography, not measurements.
_NUMERIC_MARKER_SPAN = re.compile(r"\[\s*\d+(?:\s*[,\-–]\s*\d+)*\s*\]")

# A fence carrying an info string ("```python") is a code listing, and the
# numbers in it are code. A bare fence in a draft is the ASCII figure stage 16
# adds: agents/16-enhancer.md has the enhancer draw diagrams in bare fences,
# and while every fence was skipped alike, a fabricated figure written into
# one was invisible to this check.
_FENCE_INFO = re.compile(r"^\s*(?:```|~~~)\s*\S")

# Thresholds and interval widths are conventions of the method, chosen by the
# author, not values read out of a source. A paper reporting "p < 0.05" is not
# quoting a finding, so requiring 0.05 to appear in the corpus would flag the
# convention itself.
#
# Exempt only where a threshold is what is actually being stated, for the same
# reason _CI_LEVELS is context-gated below. An unconditional set is a smuggling
# route, and the widest one on this list: 0.1 is a plausible effect size, a
# plausible proportion and a plausible rate, so "the observed effect size was
# 0.1 standard deviations" inherited an exemption written for "p < 0.05" and
# was never looked at.
_CONVENTIONAL = {"0.05", "0.01", "0.001", "0.1"}
_THRESHOLD_BEFORE = re.compile(
    r"(?:\b(?:p|alpha)\s*[<>=]\s*|"
    r"\b(?:significance level|alpha level|threshold|significance)\s*"
    r"(?:of\s*|at\s*|[<>=]\s*)?)$", re.IGNORECASE)
_THRESHOLD_AFTER = re.compile(
    r"^\s*(?:level\b|threshold\b|significance\b)", re.IGNORECASE)
_CI_LEVELS = {"90", "95", "99"}

# An interval level is exempt only where it is actually naming an interval:
# immediately before "CI"/"confidence interval", or immediately after a phrase
# introducing one. Scanning the whole line for the word "CI" was the first
# version and it is a smuggling route: in "Retention was 95% by week four (95%
# CI 0.81 to 0.94)" the parenthesised interval exempts the reported 95% too,
# which is the fabricated one.
_CI_AFTER = re.compile(r"^\s*%?\s*(?:CI\b|confidence interval)", re.IGNORECASE)
_CI_BEFORE = re.compile(
    r"\b(?:confidence (?:level|interval)|significance level|alpha)\s*"
    r"(?:of\s*)?$", re.IGNORECASE)

# A four-digit number is a publication year often enough to exempt, and a
# cohort size often enough that a blanket exemption is a hole: "n = 2000" and
# "a sample of 1,847 participants" both sit in the year band, and both are
# exactly the kind of number this check exists to question. So the exemption
# is withdrawn wherever the number is doing a counting job.
_COUNT_NOUN = re.compile(
    r"^\s*(?:participants?|patients?|subjects?|respondents?|samples?|records?|"
    r"cases|observations?|documents?|articles?|studies|trials?|images?|"
    r"tokens?|words?|users?|items?|rows?)\b", re.IGNORECASE)
_COUNT_PREFIX = re.compile(
    r"(?:\bn\s*=\s*|\b(?:sample|cohort|total|set|corpus|population)\s+of\s+)$")

# The same hole, one word to the right. Withdrawing the year exemption for
# counting words left every other kind of measurement inside the band exempt,
# so "the intervention cost 1,950 euros per patient", "each dose contained
# 1975 mg" and "training required 2050 hours" all read as publication dates. A
# number carrying a unit is a measurement whatever its magnitude.
_UNIT_AFTER = re.compile(
    r"^\s*(?:%|percent|percentage points?|"
    r"eur|usd|gbp|chf|euros?|dollars?|pounds?|cents?|"
    r"mg|kg|g|lbs?|ml|l|km|cm|mm|m|nm|s|ms|hz|khz|mhz|gb|mb|kb|tb|"
    r"hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|weeks?|months?)\b",
    re.IGNORECASE)
_CURRENCY_BEFORE = re.compile(r"[$€£¥]\s*$")

# "Figure 2", "Table 1", "Section 3.2", "stage 11": a label pointing at a part
# of the document, not a quantity taken from a source. None of these words
# precedes a number in ordinary prose except as a label.
_LABELLED_NUMBER = re.compile(
    r"\b(?:figure|fig\.?|table|section|chapter|equation|eq\.?|appendix|stage|"
    r"step|volume|vol\.?)\s*$", re.IGNORECASE)

# "no", "part", "issue" and "page" are ordinary English words that happen also
# to be label words, and matching them case-insensitively exempted whatever
# number followed: "there were no 38 percent gains" and "the issue 47 percent
# of respondents raised" both went unread. Used as labels they are either
# abbreviated with a period or capitalised, so that is what is required of
# them here.
_LABELLED_ABBREV = re.compile(r"\b(?:no|pp?)\.\s*$", re.IGNORECASE)
_LABELLED_CAPPED = re.compile(r"\b(?:Part|Issue|Page|No)\s*$")

# "ISO 8601", "RFC 2119", "EN 1993": a standard's number is its name. Kept as a
# short closed list of standards bodies, and deliberately case-sensitive,
# rather than a general "an acronym precedes it" rule. That broader rule was
# considered and rejected: it would also swallow "the RCT reported 34", and a
# fabricated number hiding behind an acronym is exactly what this check is for.
# A false negative here costs more than the false positive it would prevent.
_STANDARD_PREFIX = re.compile(
    r"\b(?:ISO|IEC|RFC|IEEE|ANSI|ASTM|DIN|EN|BS|NIST|ITU|ETSI)\s*$")

# Spelled-out numbers, read only where a percent word follows them.
#
# The digits-only boundary was real and "thirty-four percent" walked straight
# through it. Reading every spelled number would be worse than the gap: prose
# is full of "one of the studies" and "two approaches", none of which is a
# measurement, and an advisory list mostly made of those is one nobody reads.
# The percent word is what separates the two. A spelled number immediately in
# front of it is doing the job a digit would do in the same sentence, and a
# spelled number anywhere else is usually discourse.
#
# Still invisible, and stated rather than papered over: a spelled count with no
# percent word ("thirty-four participants"). Closing that means flagging
# ordinary prose numbers, which trades a narrow blind spot for a wide one.
_WORD_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_WORD_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
              "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_WORD_SCALES = {"hundred": 100, "thousand": 1000,
                "million": 1000000, "billion": 1000000000}
_NUMBER_WORDS = sorted(
    set(_WORD_UNITS) | set(_WORD_TENS) | set(_WORD_SCALES),
    key=len, reverse=True)
_SPELLED_PERCENT = re.compile(
    r"(?<![\w-])((?:" + "|".join(_NUMBER_WORDS) + r")"
    r"(?:[\s-]+(?:and[\s-]+)?(?:" + "|".join(_NUMBER_WORDS) + r")){0,4})"
    r"[\s-]+(?:percent|per\s+cent|percentage\s+points?)\b",
    re.IGNORECASE)


def _spelled_value(phrase):
    """'thirty-four' -> 34. None if the run is not a number after all."""
    total = current = 0
    for tok in re.split(r"[\s-]+", phrase.lower()):
        if not tok or tok == "and":
            continue
        if tok in _WORD_UNITS:
            current += _WORD_UNITS[tok]
        elif tok in _WORD_TENS:
            current += _WORD_TENS[tok]
        elif tok in _WORD_SCALES:
            scale = _WORD_SCALES[tok]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
        else:
            return None
    return total + current


def _spelled_numbers(text):
    """Every percent-context spelled number in the text, as numeral strings."""
    found = set()
    for m in _SPELLED_PERCENT.finditer(text):
        value = _spelled_value(m.group(1))
        if value is not None:
            found |= _normalise_number(str(value))
    return found


def _normalise_number(raw):
    """'1,200' and '1200' are the same number; so are '0.830' and '0.83'."""
    plain = raw.replace(",", "")
    forms = {plain}
    try:
        forms.add(repr(float(plain)))
    except ValueError:
        pass
    return forms


def corpus_numbers(corpus_text):
    """Every number that actually appears in the research corpus.

    Spelled-out percentages are read here as well as in the draft, and the
    symmetry is the point: a corpus recording "twelve percent" has to make a
    draft's "12%" known, or a correctly sourced figure gets reported as
    fabricated purely because the two spelled it differently.
    """
    found = set()
    for m in _CLAIM_NUMBER.finditer(corpus_text):
        found |= _normalise_number(m.group(1))
    found |= _spelled_numbers(corpus_text)
    return found


def check_number_provenance(text, corpus_text):
    """Advisory: numbers in the draft that appear nowhere in the research corpus.

    This is the other half of the bracketed-slot problem, and the half
    check_bracket_slots cannot reach. That check catches the honest failure: a
    slot like `[figure from summaries.md]` left unfilled. It is structurally
    blind to the dishonest one, where the same slot is replaced by a
    plausible invented number. When that happens the DOI still resolves, the
    marker still maps to a bibliography entry, the word count still lands,
    and every other check in this file passes. Only the number is a
    fabrication, and from the outside it is indistinguishable from a real one.

    The rule this enforces is not new. agents/06-formatter.md already states
    it: "every number and every finding attributed to a source must appear in
    that source's entry in research/summaries.md". Until now that rule lived
    only in prose, which means it was enforced only by a model remembering
    it, at exactly the point in a long run where models stop remembering
    things.

    Deliberately advisory rather than fatal, and the distinction is the whole
    design. A paper legitimately computes numbers that appear in no source:
    the two cohorts summed, a percentage derived from a count, a difference
    between two reported figures. This script cannot tell a derived number
    from an invented one, because the arithmetic that would distinguish them
    was never written down. A gate that failed on both would break correct
    papers, and the file's own precedent is that a check which damages a
    correct paper is worse than no check. So this reports and does not fail:
    it converts an invisible fabrication into a short list a human reads,
    which is the strongest honest claim the mechanism supports.

    It also does not overlap agents/11-verifier.md's stage-11 sweep. That
    sweep asks whether a statistic carries a citation marker at all. This
    asks, of a number that may well carry a perfectly valid marker, whether
    its value was ever in the corpus. A fabricated number inserted next to a
    real citation passes that sweep by design.

    Known limit, stated rather than papered over: this reads digits, plus one
    class of spelled-out number. "thirty-four percent" is read, because the
    percent word marks it as doing a measurement's job; "thirty-four
    participants" is not, because reading every spelled number means flagging
    "one of the studies" and "two approaches" in ordinary prose, and an
    advisory list made mostly of those is one nobody reads. The exclusions
    below are each narrowed to the context that justifies them, so that a
    fabricated value cannot be parked inside one on purpose, but the boundary
    is structural. Treat a clean advisory list as evidence about the numbers
    this check can read, not as a fabrication clearance for the draft.
    """
    if not corpus_text:
        return []
    known = corpus_numbers(corpus_text)
    notes = []
    body, _, _ = _extract_body_and_bib(text)
    in_fence = False
    fenced_code = False
    for lineno, line in enumerate(body.splitlines(), start=1):
        if FENCE_RE.match(line):
            if in_fence:
                in_fence = False
                fenced_code = False
            else:
                in_fence = True
                fenced_code = bool(_FENCE_INFO.match(line))
            continue
        if (in_fence and fenced_code) or INDENTED_CODE_RE.match(line):
            continue
        scanned = _NUMERIC_MARKER_SPAN.sub(" ", line)
        for m in _CLAIM_NUMBER.finditer(scanned):
            raw = m.group(1)
            plain = raw.replace(",", "")
            prefix = scanned[:m.start()]
            suffix = scanned[m.end():]
            if (_LABELLED_NUMBER.search(prefix)
                    or _LABELLED_ABBREV.search(prefix)
                    or _LABELLED_CAPPED.search(prefix)
                    or _STANDARD_PREFIX.search(prefix)):
                continue
            if plain in _CONVENTIONAL and (
                    _THRESHOLD_BEFORE.search(prefix)
                    or _THRESHOLD_AFTER.match(suffix)):
                continue
            if plain in _CI_LEVELS and (
                    _CI_AFTER.match(suffix) or _CI_BEFORE.search(prefix)):
                continue
            if (plain.isdigit() and 1900 <= int(plain) <= 2100
                    and not _COUNT_NOUN.match(suffix)
                    and not _COUNT_PREFIX.search(prefix)
                    and not _UNIT_AFTER.match(suffix)
                    and not _CURRENCY_BEFORE.search(prefix)):
                continue  # a year: a publication date, not a measurement
            if _normalise_number(raw) & known:
                continue
            notes.append(
                f"line {lineno}: {raw!r} appears nowhere in the research "
                f"corpus. If it was derived from figures that are in the "
                f"corpus, say so in the sentence or the methodology. If it "
                f"came from a source, that source's entry in "
                f"research/summaries.md is missing it. If it came from "
                f"neither, it is invented and the claim has to go.")
        for m in _SPELLED_PERCENT.finditer(scanned):
            value = _spelled_value(m.group(1))
            if value is None or _normalise_number(str(value)) & known:
                continue
            notes.append(
                f"line {lineno}: {m.group(1)!r} ({value}) appears nowhere in "
                f"the research corpus. If it was derived from figures that "
                f"are in the corpus, say so in the sentence or the "
                f"methodology. If it came from a source, that source's entry "
                f"in research/summaries.md is missing it. If it came from "
                f"neither, it is invented and the claim has to go.")
    return notes


def run_reviews(text, corpus_text=None):
    """Advisory findings. Never affects the exit code."""
    if corpus_text is None:
        return []
    return check_number_provenance(text, corpus_text)


# Only appears inside a compiled reference list, so this is scoped to the
# bibliography by the caller rather than run over the whole document: a body
# sentence that happens to mention a doi.org URL in prose is not a printed
# reference entry.
_BIB_DOI_URL = re.compile(r"https?://doi\.org/(\S+)", re.IGNORECASE)


def _doi_url_candidates(raw):
    """The DOI as printed, then with one trailing period removed.

    Every style citations.py can compile to prints the bare DOI URL except
    MLA, Chicago and Harvard, which each append exactly one "." immediately
    after it with no separating space (see citations.py's
    _format_reference_mla and neighbors). Only one trailing period is ever
    added by any formatter, so only one is ever stripped here: a DOI whose
    own suffix legitimately ends in "." would need a second literal period
    printed after it to be mistaken for one of these, which no style does.
    """
    yield raw
    if raw.endswith("."):
        yield raw[:-1]


def check_database_cross_check(text, database):
    """Every DOI printed in the compiled bibliography, checked against `database`.

    citations.py compile already refuses to render a DOI whose database
    record is not verified == "resolved"; that is the first line of defence,
    enforced at compile time against whatever research/citations.json looked
    like at that moment. This is the second line, enforced here, against
    whatever research/citations.json looks like now. research/citations.json
    is a plain JSON file: a hand edit can mark a record "resolved" without
    ever asking Crossref or DataCite, and a compile can also simply have run
    against a copy of the database from before verification finished. Either
    way, the bibliography a reader sees is the only place that gap becomes
    visible after the fact, which is why this re-derives every DOI actually
    printed there and asks the database, again, whether it was really
    resolved -- rather than trusting that compile's gate already settled it.
    """
    failures = []
    citation_records = database.get("citations", {})
    _, bib_lines, bib_first_lineno = _extract_body_and_bib(text)
    if bib_first_lineno is None:
        return failures
    for idx, line in enumerate(bib_lines):
        for m in _BIB_DOI_URL.finditer(line):
            lineno = bib_first_lineno + idx
            candidates = [sources._norm_doi(c) for c in _doi_url_candidates(m.group(1))]
            printed = candidates[0]
            record = None
            for cand in candidates:
                rec = citation_records.get(cand)
                if rec is not None:
                    record = rec
                    if record.get("verified") == "resolved":
                        break
            if record is None:
                failures.append(
                    f"line {lineno}: DOI {printed!r} printed in the bibliography "
                    f"is not in the citation database at all. Rebuild it with "
                    f"scripts/citations.py build, or check that -d points at "
                    f"the right file.")
            elif record.get("verified") != "resolved":
                failures.append(
                    f"line {lineno}: DOI {printed!r} printed in the bibliography "
                    f"is in the database but not resolved (database status: "
                    f"{record.get('verified', 'unknown')!r}).")
    return failures


def run_checks(text, target=None, tolerance=0.1, database=None, brief=None):
    failures = []
    failures += check_missing_sources(text)
    failures += check_placeholders(text)
    failures += check_markers_and_bibliography(text)
    failures += check_stranded_punctuation(text)
    failures += check_word_count(text, target, tolerance)
    failures += check_template_text(text)
    failures += check_bracket_slots(text)
    if database is not None:
        failures += check_database_cross_check(text, database)
    if brief:
        failures += check_word_range(text, brief.get("words_min"),
                                     brief.get("words_max"))
        failures += check_reference_count(text, brief.get("min_references"))
        failures += check_abstract(text, brief.get("abstract_max_words"))
        failures += check_required_sections(text, brief.get("required_sections"))
    return failures


def stats(text):
    """The four numbers the brief checks measure, whether or not one was given."""
    abstract = find_abstract(text)
    return {
        "main_text_words": count_main_text_words(text),
        "abstract_words": count_prose_words(abstract[2]) if abstract else None,
        "reference_entries": count_reference_entries(text),
        "sections": [title for _l, title, _s, _e in sections(text)],
    }


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="integrity.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("draft", help="Path to the compiled draft markdown file")
    parser.add_argument("-d", "--database", default=None,
                         help="Path to citations.json. When given, cross-checks every DOI "
                              "printed in the draft's bibliography against the database: each "
                              'must be present with verified == "resolved", or it is reported '
                              "as a critical issue. Omit to skip this cross-check (the draft is "
                              "still checked for everything else, and the report says the "
                              "cross-check did not run).")
    parser.add_argument("-c", "--corpus", default=None,
                         help="Path to research/summaries.md. When given, every number in the "
                              "draft that appears nowhere in that file is reported as an "
                              "advisory note. Advisory, never fatal: a number derived from the "
                              "corpus rather than quoted from it is legitimate and appears "
                              "there too, and this script cannot tell a derived number from an "
                              "invented one. Omit to skip the report entirely.")
    parser.add_argument("--target", type=int, default=None, help="Target word count")
    parser.add_argument("--tolerance", type=float, default=0.1,
                         help="Allowed fractional deviation from --target (default 0.1 = 10%%)")
    parser.add_argument("-b", "--brief", default=None,
                         help="Path to research/brief.json, the requirements the user actually "
                              "stated: word range, reference minimum, abstract cap and named "
                              "sections. Each one is checked only if it is there; nothing in it "
                              "has a default, because every value in it came from the brief "
                              "rather than from this pipeline. The flags below override it.")
    parser.add_argument("--word-range", default=None, metavar="LO-HI",
                         help="Main-text word range the brief asked for, e.g. 1200-1500. The "
                              "reference list and the abstract are counted separately and are "
                              "not included in this number.")
    parser.add_argument("--min-references", type=int, default=None,
                         help="Fewest reference entries the brief asks for")
    parser.add_argument("--abstract-max", type=int, default=None, metavar="N",
                         help="Word cap on the abstract the brief asks for. Passing it also "
                              "requires that an abstract is there at all.")
    parser.add_argument("--require-section", action="append", default=None,
                         metavar="NAME",
                         help="A section the brief names, matched against the draft's headings. "
                              "Repeat the flag once per section.")
    parser.add_argument("--stats", action="store_true",
                         help="Print the main-text word count, the abstract word count, the "
                              "reference count and the section headings, then exit 0 without "
                              "checking anything. For counting a draft while it is still being "
                              "written, so a trim or an expansion runs against a number rather "
                              "than an impression.")
    return parser


_WORD_RANGE = re.compile(r"^\s*(\d+)\s*(?:-|to|\.\.)\s*(\d+)\s*$")


def brief_from_args(args):
    """The brief file, if any, with the command-line flags layered over it."""
    brief = load_brief(args.brief) if args.brief else normalise_brief({})
    if args.word_range:
        m = _WORD_RANGE.match(args.word_range)
        if not m:
            raise BriefError(f"--word-range {args.word_range!r} is not a range; "
                             f"write it as LO-HI, for example 1200-1500")
        brief["words_min"], brief["words_max"] = int(m.group(1)), int(m.group(2))
        if brief["words_min"] > brief["words_max"]:
            raise BriefError(f"--word-range {args.word_range!r} runs backwards")
    if args.min_references is not None:
        brief["min_references"] = args.min_references
    if args.abstract_max is not None:
        brief["abstract_max_words"] = args.abstract_max
    if args.require_section:
        brief["required_sections"] = (brief.get("required_sections") or []) + list(args.require_section)
    return brief


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Error: draft not found: {args.draft}", file=sys.stderr)
        return 1

    database = None
    if args.database:
        if not Path(args.database).exists():
            print(f"Error: database not found: {args.database}", file=sys.stderr)
            return 1
        try:
            database = citations.load_database(args.database)
        except citations.DatabaseError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    if args.brief and not Path(args.brief).exists():
        print(f"Error: brief not found: {args.brief}", file=sys.stderr)
        return 1
    try:
        brief = brief_from_args(args)
    except BriefError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    corpus_text = None
    if args.corpus:
        corpus_path = Path(args.corpus)
        if not corpus_path.exists():
            print(f"Error: corpus not found: {args.corpus}", file=sys.stderr)
            return 1
        corpus_text = corpus_path.read_text(encoding="utf-8")

    text = draft_path.read_text(encoding="utf-8")

    if args.stats:
        counted = stats(text)
        abstract = counted["abstract_words"]
        print(f"main text words:   {counted['main_text_words']}")
        print(f"abstract words:    {abstract if abstract is not None else 'no abstract section'}")
        print(f"reference entries: {counted['reference_entries']}")
        print(f"sections:          {', '.join(counted['sections']) or 'none'}")
        return 0

    failures = run_checks(text, target=args.target, tolerance=args.tolerance,
                          database=database, brief=brief)

    # Printed whether or not the gate passes, and never changes the exit code.
    # Silent without --corpus, so the default invocation keeps its contract of
    # printing nothing on a clean pass.
    reviews = run_reviews(text, corpus_text=corpus_text)
    if reviews:
        print(f"Advisory: {len(reviews)} number(s) in {args.draft} appear nowhere in "
              f"{args.corpus}. These are not gate failures; each one is either derived, "
              f"missing from the corpus, or invented, and only a reader can tell which:",
              file=sys.stderr)
        for r in reviews:
            print(f"  - {r}", file=sys.stderr)

    if failures:
        cross_check_note = (
            f"database cross-check: ran against {args.database}" if database is not None
            else "database cross-check: not run (pass -d/--database to enable)"
        )
        print(f"Integrity check FAILED for {args.draft} "
              f"({len(failures)} issue(s); {cross_check_note}):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
