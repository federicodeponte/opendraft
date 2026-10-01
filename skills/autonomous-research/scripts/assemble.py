#!/usr/bin/env python3
"""Merge the numbered section files of a draft into one document.

No API key, standard library only, no model involved: this is a file
concatenation with the ordering and completeness checks that a model doing the
same job by hand keeps getting wrong. Sections are ordered by their leading
number, not lexically, so 10 follows 9 instead of 1.

    assemble.py sections -o full_draft.md
    assemble.py sections -o full_draft.md --check
    assemble.py sections -o full_draft.md --force

A file is part of the body when its name starts with a number: 01_intro.md,
02-methods.md, 03.md. Everything else in the directory is left alone, and so is
a numbered file whose name marks it as a report rather than prose, because a
review report that lands in sections/ used to be spliced into the paper.

Refuses to run on a gap or a duplicate in the numbering rather than quietly
producing a draft with a missing section, and refuses to overwrite an existing
output without --force.
"""
import argparse
import re
import sys
from pathlib import Path

# 01_intro.md, 02-methods.md, 3.md -- the number is what orders the document.
SECTION_NAME = re.compile(r"^(\d+)(?:[-_. ]+(?P<slug>.*))?$")

# A review report is not prose. Reports belong in review/<stage>.md, but a
# stale one sitting in sections/ used to be concatenated into the paper as if
# it were a chapter, and nothing downstream could tell it apart from one.
REPORT_TOKENS = ("report", "review", "notes", "checklist", "log")


class AssembleError(Exception):
    """A problem the user can fix, reported without a traceback."""


def _classify(path):
    """(number, is_report) for a body-eligible file, or (None, False)."""
    m = SECTION_NAME.match(path.stem)
    if not m:
        return None, False
    slug = (m.group("slug") or "").lower()
    tokens = re.split(r"[^a-z0-9]+", slug)
    return int(m.group(1)), any(t in REPORT_TOKENS for t in tokens)


def plan(source_dir):
    """Decide what would be merged, in order, and what would be skipped.

    Returns (sections, skipped): `sections` is a list of (number, Path) sorted
    by number, `skipped` a sorted list of Paths left out of the body."""
    source = Path(source_dir)
    if not source.exists():
        raise AssembleError(f"section directory not found: {source}")
    if not source.is_dir():
        raise AssembleError(f"not a directory: {source}")

    sections, skipped, by_number = [], [], {}
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        number, is_report = _classify(path)
        if number is None or is_report:
            skipped.append(path)
            continue
        if number in by_number:
            first = by_number[number].name
            raise AssembleError(
                f"two files share section number {number:02d}: {first} and "
                f"{path.name}. Renumber one of them; assemble.py will not "
                f"guess which comes first.")
        by_number[number] = path
        sections.append((number, path))

    if not sections:
        raise AssembleError(
            f"no numbered section files in {source}. Section files are named "
            f"with a leading number, for example 01_introduction.md.")

    numbers = [n for n, _ in sections]
    missing = [n for n in range(min(numbers), max(numbers) + 1)
               if n not in by_number]
    if missing:
        listed = ", ".join(f"{n:02d}" for n in missing)
        raise AssembleError(
            f"gap in the section numbering: {listed} missing between "
            f"{min(numbers):02d} and {max(numbers):02d}. A missing section is "
            f"a missing part of the paper, so nothing was written.")

    return sections, sorted(skipped)


def merge(sections):
    """Concatenate section bodies, one blank line between them."""
    bodies = []
    for _, path in sections:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise AssembleError(
                f"{path.name} is empty. An empty section merged silently is a "
                f"heading with nothing under it in the finished paper.")
        bodies.append(text)
    return "\n\n".join(bodies) + "\n"


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="assemble.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source", help="Directory holding the numbered section files, e.g. sections")
    parser.add_argument(
        "-o", "--output", required=True,
        help="File to write the merged draft to, e.g. full_draft.md")
    parser.add_argument(
        "--check", action="store_true",
        help="Report what would be merged and what would be skipped, and write "
             "nothing. Still fails on a gap or a duplicate.")
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing output file.")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    out = Path(args.output)

    try:
        sections, skipped = plan(args.source)
    except AssembleError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.check:
        print(f"Would merge {len(sections)} section(s) into {out}:")
        for number, path in sections:
            print(f"  {number:02d}  {path.name}")
        if skipped:
            print("Not part of the body:")
            for path in skipped:
                print(f"      {path.name}")
        return 0

    if out.exists() and not args.force:
        # Assembly happens once, at stage 9.5. Everything after it edits
        # full_draft.md in place, so a second unforced run would throw that
        # work away, and the person running it has no other copy.
        print(
            f"Error: {out} already exists. Re-assembling replaces it with the "
            f"current contents of {args.source}/, which discards every edit "
            f"made to {out} after it was assembled: the stage 10 to 15 "
            f"revisions, the citation compile, and any hand edit since. "
            f"Pass --force if that is what you want.",
            file=sys.stderr)
        return 1

    try:
        text = merge(sections)
    except (AssembleError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Assembled {len(sections)} section(s) from {args.source} -> {out}")
    if skipped:
        print(f"Skipped (not body sections): "
              f"{', '.join(p.name for p in skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
