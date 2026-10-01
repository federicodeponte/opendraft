"""The pipeline's file contract, checked as data rather than trusted as prose.

Every agent file declares a **Reads:** and a **Writes:** line. Together those
lines are a dependency graph, and the graph was broken for a long time in a way
that no reader caught: stages 10 to 18 all read `full_draft.md`, and no stage
produced it. A model following the prompts had to invent the merge, and the
usual invention was to concatenate whatever was in `sections/`, stage reports
included. Stage 9.5 and the move of every report to `review/` closed both holes.

These tests parse the markdown and assert the three properties that keep it
closed. They are also run against a reconstruction of the pre-change contract,
so a check that cannot fail is itself a test failure.
"""
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
AGENTS_DIR = ROOT / "agents"
SKILL_MD = ROOT / "SKILL.md"

READS_RE = re.compile(r"^\*\*Reads:\*\*\s*(.+)$", re.MULTILINE)
WRITES_RE = re.compile(r"^\*\*Writes:\*\*\s*(.+)$", re.MULTILINE)
BACKTICKED = re.compile(r"`([^`]+)`(\s*\(([^)]*)\))?")
STAGE_FILE_RE = re.compile(r"^(\d+(?:\.\d+)?)-([a-z0-9-]+)\.md$")

# Directories a stage may write into. Anything else has to be justified by the
# checks below rather than by whoever typed the line.
RESEARCH_PREFIX = "research/"
REVIEW_PREFIX = "review/"
SECTIONS_GLOB = "sections/*.md"

# Top-level artifacts the pipeline legitimately produces outside those trees.
DRAFT_ARTIFACTS = {"outline.md", "outline_formatted.md", "full_draft.md",
                   "final.md"}


def _normalize(path):
    """Collapse a declared path to the identity the graph reasons about.

    `sections/<NN>_<section-name>.md` and `sections/*.md` are the same node:
    one stage writes the section files, later stages read them."""
    p = path.strip().strip("`").strip()
    if p.startswith("sections/"):
        return SECTIONS_GLOB
    return p


def _paths(line):
    """[(normalized path, annotation)] for the backticked items on a line.

    Anything not in backticks is prose: "the research topic", "any
    writing-sample files provided for this run". Those are external inputs by
    construction, and the graph does not try to source them."""
    out = []
    for m in BACKTICKED.finditer(line):
        out.append((_normalize(m.group(1)), (m.group(3) or "").lower()))
    return out


def parse_agents():
    """{stage number: {"slug", "reads", "writes"}} read off agents/*.md."""
    contract = {}
    for path in sorted(AGENTS_DIR.glob("*.md")):
        m = STAGE_FILE_RE.match(path.name)
        assert m, f"unexpected file in agents/: {path.name}"
        text = path.read_text(encoding="utf-8")
        reads = READS_RE.search(text)
        writes = WRITES_RE.search(text)
        assert reads, f"{path.name} has no **Reads:** line"
        assert writes, f"{path.name} has no **Writes:** line"
        contract[float(m.group(1))] = {
            "slug": m.group(2),
            "file": path.name,
            "reads": _paths(reads.group(1)),
            "writes": _paths(writes.group(1)),
        }
    return contract


# Stage 9.5 is a script, so it has no file in agents/. Its row lives in the
# SKILL.md stage table; the test below asserts the row is really there rather
# than letting this dict quietly paper over its removal.
ASSEMBLY_STAGE = 9.5
ASSEMBLY_ENTRY = {
    "slug": "assemble",
    "file": "SKILL.md (stage table)",
    "reads": [(SECTIONS_GLOB, "")],
    "writes": [("full_draft.md", "")],
}


def full_contract():
    contract = parse_agents()
    contract[ASSEMBLY_STAGE] = dict(ASSEMBLY_ENTRY)
    return contract


# --- the three checks, as functions so they can be run against a fake -------

def unsourced_reads(contract):
    """[(stage, path)] where a stage reads something no earlier stage wrote."""
    problems, written = [], set()
    for stage in sorted(contract):
        for path, _ in contract[stage]["reads"]:
            if path not in written:
                problems.append((stage, path))
        for path, _ in contract[stage]["writes"]:
            written.add(path)
    return problems


def creates(entry, path):
    """True when a stage produces a path rather than editing an existing one.

    A stage that reads a file and writes it back is revising it; only a stage
    that writes a path it never read brings that path into existence. This is
    firmer than trusting the "(edited in place)" annotation, which stages 16 to
    18 do not use even though prepending to `full_draft.md` is plainly an
    edit."""
    read_paths = {p for p, _ in entry["reads"]}
    return path not in read_paths


def misplaced_reports(contract):
    """[(stage, path)] where a stage's own report is not under `review/`.

    A report is identified by the stage's own name appearing in the filename,
    which is exactly how the stage reports used to be named when they lived in
    `sections/` and got merged into the paper. Research artifacts and the draft
    itself are excluded: those are pipeline inputs downstream stages consume,
    not review output, and one of them (`research/citations.json`, from the
    citation-manager stage) legitimately carries its author's name."""
    problems = []
    for stage in sorted(contract):
        entry = contract[stage]
        slug_words = [w for w in entry["slug"].split("-") if len(w) > 3]
        for path, _ in entry["writes"]:
            if path.startswith((REVIEW_PREFIX, RESEARCH_PREFIX)):
                continue
            if path in DRAFT_ARTIFACTS:
                continue
            stem = Path(path).stem.lower()
            if any(w in stem for w in slug_words):
                problems.append((stage, path))
    return problems


def stray_writes(contract):
    """[(stage, path)] for writes outside research/, review/, sections/ and the
    known draft artifacts."""
    problems = []
    for stage in sorted(contract):
        for path, _ in contract[stage]["writes"]:
            if path.startswith((RESEARCH_PREFIX, REVIEW_PREFIX)):
                continue
            if path == SECTIONS_GLOB or path in DRAFT_ARTIFACTS:
                continue
            problems.append((stage, path))
    return problems


def unexpected_section_writers(contract, author_stage=7.0):
    """[(stage, path)] for stages that create section files without being the
    one stage allowed to. Editing an existing section in place is marked as
    such on the line and is not creation."""
    problems = []
    for stage in sorted(contract):
        if stage == author_stage:
            continue
        entry = contract[stage]
        for path, _ in entry["writes"]:
            if path == SECTIONS_GLOB and creates(entry, path):
                problems.append((stage, path))
    return problems


# --- a reconstruction of the contract before the fix ------------------------

def broken_contract():
    """The shape the pipeline had before stage 9.5 and the `review/` move.

    Reconstructed, not archived: this bundle is not a git repository, so the
    pre-change files are not recoverable. It reproduces the two documented
    defects, no assembly step and reports parked in `sections/`, so that each
    check above is shown to be capable of failing."""
    contract = parse_agents()
    for stage, entry in contract.items():
        entry["writes"] = [
            (f"sections/{int(stage):02d}_{entry['slug']}-report.md", "")
            if path.startswith(REVIEW_PREFIX) else (path, annotation)
            for path, annotation in entry["writes"]
        ]
    return contract


class ContractParsingTests(unittest.TestCase):
    def test_every_agent_declares_reads_and_writes(self):
        contract = parse_agents()
        self.assertEqual(len(contract), 19)
        for stage, entry in contract.items():
            with self.subTest(stage=stage):
                self.assertTrue(entry["writes"], f"{entry['file']} writes nothing")

    def test_skill_md_still_declares_the_assembly_stage(self):
        """If stage 9.5 leaves SKILL.md, the chain reopens and this dict would
        otherwise keep the tests green while the pipeline is broken."""
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("scripts/assemble.py", text)
        self.assertRegex(text, r"\|\s*9\.5\s*\|")
        self.assertIn("assemble.py sections -o full_draft.md", text)


class ReadsAreSourcedTests(unittest.TestCase):
    def test_every_path_a_stage_reads_is_written_by_an_earlier_stage(self):
        problems = unsourced_reads(full_contract())
        self.assertEqual(problems, [], f"read with no producer: {problems}")

    def test_full_draft_has_exactly_one_producer(self):
        contract = full_contract()
        producers = [s for s in sorted(contract)
                     if any(p == "full_draft.md" and creates(contract[s], p)
                            for p, _ in contract[s]["writes"])]
        self.assertEqual(producers, [ASSEMBLY_STAGE],
                         f"full_draft.md is created by {producers}")

    def test_the_check_fails_on_the_pre_change_contract(self):
        """Without stage 9.5, every stage from 10 on reads a file nobody wrote."""
        without_assembly = parse_agents()
        problems = unsourced_reads(without_assembly)
        self.assertTrue(problems, "the reads check cannot fail, so it proves nothing")
        self.assertTrue(any(p == "full_draft.md" for _, p in problems))


class ReportsLiveInReviewTests(unittest.TestCase):
    def test_no_stage_report_is_written_outside_review(self):
        problems = misplaced_reports(full_contract())
        self.assertEqual(problems, [], f"report outside review/: {problems}")

    def test_no_stage_writes_outside_the_known_trees(self):
        problems = stray_writes(full_contract())
        self.assertEqual(problems, [], f"write outside the contract: {problems}")

    def test_the_check_fails_on_the_pre_change_contract(self):
        problems = misplaced_reports(broken_contract())
        self.assertTrue(problems, "the report-location check cannot fail")
        self.assertTrue(any(p.startswith("sections/") for _, p in problems))


class OnlyCrafterCreatesSectionsTests(unittest.TestCase):
    def test_no_stage_except_7_creates_section_files(self):
        problems = unexpected_section_writers(full_contract())
        self.assertEqual(problems, [], f"unexpected section writer: {problems}")

    def test_stages_8_and_9_declare_their_section_writes_as_in_place_edits(self):
        contract = parse_agents()
        for stage in (8.0, 9.0):
            with self.subTest(stage=stage):
                annotations = [a for p, a in contract[stage]["writes"]
                               if p == SECTIONS_GLOB]
                self.assertTrue(annotations, f"stage {stage} declares no section write")
                self.assertTrue(any("in place" in a for a in annotations),
                                f"stage {stage} looks like it creates sections")

    def test_the_check_fails_when_a_report_stage_creates_a_section(self):
        contract = full_contract()
        contract[8.0] = dict(contract[8.0])
        contract[8.0]["reads"] = []
        contract[8.0]["writes"] = [(SECTIONS_GLOB, "")]
        self.assertTrue(unexpected_section_writers(contract),
                        "the section-writer check cannot fail")


# ---------------------------------------------------------------------------
# Worked examples must not invent statistics
# ---------------------------------------------------------------------------
#
# A worked example that reads
#
#     Only 12% of studies report tissue-level effects {cite_10.1000/a}
#
# teaches the pattern it is trying to demonstrate: attach a number to a
# citation. The number is invented, the DOI is invented, and a model copying the
# shape of the example copies both. Four agent files carried this and were
# cleaned; nothing structural stopped it coming back.
#
# The check is deliberately about shape, not wording, so it survives the other
# agents rewriting these files: on any line that carries a `{cite_...}`
# placeholder, strip the placeholders (their DOIs are full of digits and dots)
# and then look for a concrete statistic in what is left.

CITE_MARKER = re.compile(r"\{cite_[^}]*\}")
# A bare DOI next to a placeholder is the same DOI written out, not a finding:
# `| ... | 10.5555/enveco.2023.45.234 | replace with {cite_10.5555/...} |`.
BARE_DOI = re.compile(r"\b10\.\d{4,9}/[^\s`)\]}|,;]+")
YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")

STATISTIC = re.compile(
    r"""(
          \d+(?:\.\d+)?\s*%              # 12%, 3.4 %
        | \d+\.\d+                       # any decimal: 0.83, 2.5
        | \d{1,3}(?:,\d{3})+             # thousands separator: 1,204
        | \b\d+\s+(?:of|out\s+of)\s+\d+\b  # 7 of 11
        | \b\d+(?:\.\d+)?\s*(?:x|-fold|\s+fold)\b   # 3x, 2.4-fold
    )""",
    re.VERBOSE | re.IGNORECASE,
)


def fabricated_statistics(text, name="<text>"):
    """[(file, line number, the statistic)] for cite-plus-number lines."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not CITE_MARKER.search(line):
            continue
        # A DOI is not a statistic, in a placeholder or written out, and
        # neither is a year.
        stripped = YEAR.sub(" ", BARE_DOI.sub(" ", CITE_MARKER.sub(" ", line)))
        for match in STATISTIC.finditer(stripped):
            hits.append((name, lineno, match.group(0).strip()))
    return hits


class WorkedExampleTests(unittest.TestCase):
    """No agent file pairs a citation placeholder with an invented number."""

    def test_no_agent_file_pairs_a_placeholder_with_a_statistic(self):
        hits = []
        for path in sorted(AGENTS_DIR.glob("*.md")):
            hits += fabricated_statistics(path.read_text(encoding="utf-8"),
                                          path.name)
        self.assertEqual(
            hits, [],
            "a worked example attaches a number to a citation placeholder; "
            "both are invented and the shape is what gets copied: "
            f"{hits}")

    def test_skill_md_does_not_pair_a_placeholder_with_a_statistic(self):
        hits = fabricated_statistics(SKILL_MD.read_text(encoding="utf-8"),
                                     SKILL_MD.name)
        self.assertEqual(hits, [], f"{hits}")

    def test_the_check_catches_the_pattern_it_is_guarding_against(self):
        for sample in (
            "Only 12% of studies report this {cite_10.1000/a}.",
            "Effect size 0.83 across cohorts {cite_10.1000/b}",
            "| Method | 1,204 samples | {cite_10.1000/c} |",
            "It performed 3x better {cite_10.1000/d}",
            "7 of 11 trials agreed {cite_10.1000/e}",
        ):
            with self.subTest(sample=sample):
                self.assertTrue(fabricated_statistics(sample),
                                "the fabrication check cannot fail")

    def test_the_check_does_not_fire_on_a_bare_placeholder_or_a_year(self):
        for sample in (
            "Cite it inline with `{cite_<doi>}` at the point of the claim.",
            "{cite_10.1038/s41598-023-41032-5} supports the mechanism.",
            "Replace (Smith & Johnson, 2023) with {cite_10.5555/enveco.2023.45.234}.",
            "Position A ({cite_<doi>}) vs. position B ({cite_<doi>}).",
            "| 10.5555/enveco.2023.45.234 | use `{cite_10.5555/enveco.2023.45.234}` |",
            "verify prints `10.5555/gone.4: absent`, so drop {cite_10.5555/gone.4}.",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(fabricated_statistics(sample), [])

    def test_a_number_without_a_placeholder_is_not_this_checks_business(self):
        """Prose about word counts and thresholds is legitimate everywhere."""
        self.assertEqual(
            fabricated_statistics("Aim for 4,000 words and a 0.4 ratio."), [])


if __name__ == "__main__":
    unittest.main()
