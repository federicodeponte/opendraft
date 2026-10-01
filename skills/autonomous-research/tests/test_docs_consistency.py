"""Cross-file consistency of the prompt bundle, checked rather than read.

Every defect this file guards against was found by hand in a bundle whose
individual files each read as correct. That is the shape of the problem: a
prompt bundle has no compiler, so two files can state different numbers for the
same thing indefinitely and every reviewer who reads either one in isolation
comes away satisfied. The stage that runs second silently edits over the stage
that ran first, and neither is wrong on its own terms.

Eight defects of exactly that shape were found and fixed by hand:

  * `references/paper-types.md` listed the short-piece tier as "1-7, then 10,
    11, 15", omitting stage 9.5. Stages 10, 11 and 15 all read `full_draft.md`,
    which `scripts/assemble.py` produces at 9.5, so that tier did not describe a
    shorter pipeline, it described one that reaches stage 10 with nothing to
    read.
  * The length-target share column read 29 percent for the two largest
    sections, against a base the rows do not sum to, and the column totalled 102
    under a Total row asserting 100.
  * The sentence-length distribution summed to 103.
  * Two files pointed at `agents/01-scout.md` under "Balance temporally", which
    is a bullet inside "Quality filtering" and not a heading, breaking the
    file-and-heading convention `references/paper-types.md` states in its own
    opening.
  * `agents/15-polish.md` quoted a mean sentence length to a decimal place and
    called it the average of stage 14's band midpoints, when two of those bands
    are open-ended and have no midpoint to average.
  * `SKILL.md` forbids "any accuracy guarantee" about the output in its closing
    section, and 250 lines earlier called a hand-edited citation database a
    defeat of "the only citation guarantee this skill makes", asserting in one
    passage the promise the other bans. Both passages read as careful on their
    own; only reading them together shows one making the claim.
  * `SKILL.md`'s pipeline table listed stage 4 as writing only
    `research/citations.json`, while `agents/04-citation-manager.md` declares
    `research/citation-notes.md` as its second output and its own "Done when"
    requires that file to exist with all four headings. The table is what a
    reader follows stage by stage, so the omitted file was one nobody created.
  * `agents/06-formatter.md` sets a floor of fifty or more references for a
    literature review, while the full-paper tier row allows twenty-five to
    fifty sources. The default request, a narrative review at default scale,
    therefore met two numbers that cannot both be satisfied, with nothing
    saying which governs.

Each check below is run against a mutation that reintroduces its defect, so a
check that cannot fail fails the suite instead of passing quietly.
"""
import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
FORMATTER = ROOT / "agents" / "06-formatter.md"
ENTROPY = ROOT / "agents" / "14-entropy.md"
POLISH = ROOT / "agents" / "15-polish.md"
PAPER_TYPES = ROOT / "references" / "paper-types.md"
SKILL_MD = ROOT / "SKILL.md"


def doc_files():
    return (sorted((ROOT / "agents").glob("*.md"))
            + sorted((ROOT / "references").glob("*.md"))
            + [SKILL_MD])


# --- referenced paths -------------------------------------------------------

# Top-level files are named without a directory, so they need an allowlist
# rather than a prefix. It stays narrow on purpose: `full_draft.md`,
# `outline.md` and everything under `research/` are outputs the pipeline
# writes at runtime, and a guard that demanded those exist in the bundle
# would fail on a clean checkout.
ROOT_FILES = r"SKILL\.md|DERIVATION\.json|THIRD_PARTY_NOTICES\.md|LICENSE"

BUNDLE_PATH = re.compile(
    r"`((?:agents|references|scripts|tests)/[\w./-]+|" + ROOT_FILES + r")`")


def missing_paths(text, root=ROOT):
    """[path] for backticked bundle paths that do not exist."""
    return [p for p in BUNDLE_PATH.findall(text) if not (root / p).exists()]


def path_referencing_files():
    """Files whose backticked bundle paths have to resolve.

    Wider than doc_files(), which feeds the prose checks: THIRD_PARTY_NOTICES.md
    is the one file that points at DERIVATION.json, and a provenance pointer
    nobody checks is precisely the one that goes stale after a rename."""
    return doc_files() + [ROOT / "THIRD_PARTY_NOTICES.md"]


def shipped_text_files():
    """Every file a reader of this bundle can open.

    doc_files() feeds the checks that only make sense for pipeline prose. Two
    checks below apply to anything shipped at all: no asserted accuracy
    guarantee, and no em dash. Restricting those to the pipeline files leaves
    the provenance map and the notices unchecked, and those are the two nobody
    re-reads after writing them once."""
    return (doc_files() + sorted((ROOT / "scripts").glob("*.py"))
            + [ROOT / "THIRD_PARTY_NOTICES.md", ROOT / "DERIVATION.json"])


# --- `file.md` ... under "Heading" pointers ---------------------------------

POINTER = re.compile(
    r'`((?:agents|references)/[\w.-]+\.md)`[^.\n]{0,140}?under\s+"([^"]+)"')


def headings_of(path):
    return [h.strip().strip('"').lower()
            for h in re.findall(r"^#{1,6}\s+(.+?)\s*$",
                                path.read_text(encoding="utf-8"), re.M)]


def unresolved_pointers(text, root=ROOT):
    """[(target file, heading)] for pointers naming a heading that is not one.

    A pointer that names a bullet rather than a heading is the failure this
    catches: it reads as precise, and it sends a model to a heading that does
    not exist."""
    problems = []
    for target, heading in POINTER.findall(text):
        path = root / target
        if not path.exists():
            problems.append((target, heading))
            continue
        head = heading.strip().lower()
        if not any(head == h or head in h or h in head for h in headings_of(path)):
            problems.append((target, heading))
    return problems


# --- the length-target table ------------------------------------------------

TABLE_ROW = re.compile(
    r"^\|\s*([A-Za-z][A-Za-z /]*?)\s*\|\s*([\d,]+)\s*\|\s*(\d+)%\s*\|\s*$", re.M)


def length_table(text):
    """[(section, words, share)] for the words/share table in `text`."""
    return [(name, int(words.replace(",", "")), int(share))
            for name, words, share in TABLE_ROW.findall(text)]


def table_problems(rows):
    """[str] for a share column that does not reconcile against its own rows.

    The shares are checked against the subtotal the rows actually sum to, not
    against the round number in the Total row. Those differ here by 250 words,
    and computing a share against the round number is what produced a column
    totalling 102 under a Total row claiming 100."""
    body = [r for r in rows if r[0].lower() != "total"]
    totals = [r for r in rows if r[0].lower() == "total"]
    if not body or not totals:
        return ["table is missing body rows or a Total row"]
    subtotal = sum(w for _, w, _ in body)
    problems = []
    if sum(s for _, _, s in body) != 100:
        problems.append(
            f"share column sums to {sum(s for _, _, s in body)}, not 100")
    for name, words, share in body:
        expected = round(words / subtotal * 100)
        if share != expected:
            problems.append(
                f"{name}: {share}% stated, {expected}% is {words}/{subtotal}")
    for name, words, share in totals:
        if share != 100:
            problems.append(f"Total row states {share}%, not 100%")
    return problems


# --- the sentence-length distribution and the mean derived from it ----------

DISTRIBUTION = re.compile(
    r"roughly (\d+) percent short \(under 15 words\), (\d+) percent medium "
    r"\(15 to 25\) and (\d+) percent long \(over 25\)")
STATED_MEAN = re.compile(r"mean sentence length near (\d+) words")
MIDPOINTS = re.compile(r"band midpoints of roughly (\d+), (\d+) and (\d+) words")


def distribution_problems(entropy_text, polish_text):
    """[str] where the length mix is not a distribution, or the mean stage 15
    states is not the mean stage 14's mix produces.

    Two stages measuring one axis against different numbers is worse than one
    measuring it: whichever runs first is edited over by the second, and no
    reader of either file alone can see it."""
    dist = DISTRIBUTION.search(entropy_text)
    if not dist:
        return ["stage 14 no longer states its three length percentages"]
    shares = [int(g) for g in dist.groups()]
    problems = []
    if sum(shares) != 100:
        problems.append(f"length mix sums to {sum(shares)}, not 100")

    mean, mids = STATED_MEAN.search(polish_text), MIDPOINTS.search(polish_text)
    if not mean or not mids:
        return problems + ["stage 15 no longer states its mean and midpoints"]
    midpoints = [int(g) for g in mids.groups()]
    derived = sum(s * m for s, m in zip(shares, midpoints)) / 100
    if round(derived) != int(mean.group(1)):
        problems.append(
            f"stage 15 states a mean of {mean.group(1)}; stage 14's mix over "
            f"midpoints {midpoints} gives {derived:.1f}")
    return problems


# --- the scale tiers --------------------------------------------------------

SKILL_TIER = re.compile(r"^- \*\*A [^*]+\*\*(.*?)(?=^- \*\*|^\s*$)", re.M | re.S)
TIER_HEADER = re.compile(r"^\|\s*Tier\s*\|", re.M)


def tier_rows(text):
    """[[tier, word count, stages, sources]] read off the scale table.

    Anchored on the table's own header rather than on the tier names, so
    renaming a tier does not silently drop it from the check and leave the
    suite green over a table nobody is looking at any more."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if TIER_HEADER.match(line):
            rows = []
            for row in lines[i + 2:]:          # +2 skips the |---| separator
                if not row.startswith("|"):
                    break
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                if len(cells) == 4:
                    rows.append(cells)
            return rows
    return []


def stage_tokens(cell):
    """The stage numbers named in a stage-list cell, parentheticals dropped."""
    return set(re.findall(r"\d+(?:\.\d+)?", cell.split("(")[0]))


def tier_problems(skill_text, paper_types_text):
    """[str] where the two files' scale tiers disagree, or a tier drops 9.5."""
    problems = []
    skill_tiers = SKILL_TIER.findall(skill_text)
    if len(skill_tiers) != 3:
        return [f"SKILL.md lists {len(skill_tiers)} scale tiers, expected 3"]
    rows = tier_rows(paper_types_text)
    if len(rows) != 3:
        return [f"paper-types.md lists {len(rows)} tier rows, expected 3"]

    for body in skill_tiers:
        if "9.5" not in body:
            problems.append(f"a SKILL.md tier omits stage 9.5: {body.strip()[:60]}")
    for name, _words, stages, _sources in rows:
        if "9.5" not in stages:
            problems.append(f"paper-types tier '{name.strip()}' omits stage 9.5")

    # The short-piece tier is the one that names individual stages in both
    # files, so it is the one where a disagreement is checkable.
    skill_short = stage_tokens(skill_tiers[0].split("**")[-1])
    pt_short = stage_tokens(rows[0][2])
    if skill_short != pt_short:
        problems.append(
            f"short-piece stage list differs: SKILL.md {sorted(skill_short)} "
            f"vs paper-types.md {sorted(pt_short)}")
    return problems


class ReferencedPathsTests(unittest.TestCase):
    def test_every_referenced_bundle_path_exists(self):
        for path in path_referencing_files():
            with self.subTest(file=path.name):
                missing = missing_paths(path.read_text(encoding="utf-8"))
                self.assertEqual(missing, [], f"{path.name}: {missing}")

    def test_the_check_fails_on_a_path_that_does_not_exist(self):
        self.assertTrue(missing_paths("see `agents/99-nonexistent.md` for this"),
                        "the referenced-path check cannot fail")

    def test_the_check_covers_top_level_files_too(self):
        # Resolved against agents/, where no top-level file lives, so a working
        # check has to report all four. Before ROOT_FILES existed the regex
        # matched none of them and this passed by seeing nothing at all.
        text = "`DERIVATION.json` `THIRD_PARTY_NOTICES.md` `LICENSE` `SKILL.md`"
        self.assertEqual(len(missing_paths(text, root=ROOT / "agents")), 4,
                         "top-level references are invisible to the path check")

    def test_the_notices_file_is_actually_scanned(self):
        # Non-vacuity: if the notices file stopped naming any bundle path, the
        # subtest above would still pass while checking nothing.
        notices = ROOT / "THIRD_PARTY_NOTICES.md"
        self.assertIn(notices, path_referencing_files())
        self.assertTrue(
            BUNDLE_PATH.findall(notices.read_text(encoding="utf-8")),
            "THIRD_PARTY_NOTICES.md names no bundle path; this check is vacuous")


class HeadingPointerTests(unittest.TestCase):
    def test_every_heading_pointer_resolves(self):
        for path in doc_files():
            with self.subTest(file=path.name):
                bad = unresolved_pointers(path.read_text(encoding="utf-8"))
                self.assertEqual(bad, [], f"{path.name}: {bad}")

    def test_the_check_fails_on_a_pointer_naming_a_bullet(self):
        """The defect verbatim: "Balance temporally" is a bullet inside
        "Quality filtering", not a heading of its own."""
        bad = unresolved_pointers(
            '`agents/01-scout.md` fixes it under "Balance temporally", so.')
        self.assertEqual(bad, [("agents/01-scout.md", "Balance temporally")])

    def test_the_check_passes_the_corrected_pointer(self):
        self.assertEqual(
            unresolved_pointers('`agents/01-scout.md` under "Quality filtering,"'),
            [])


class LengthTableTests(unittest.TestCase):
    def test_the_formatter_share_column_reconciles(self):
        rows = length_table(FORMATTER.read_text(encoding="utf-8"))
        self.assertTrue(rows, "no length-target table found in the formatter")
        self.assertEqual(table_problems(rows), [])

    def test_paper_types_carries_the_same_table(self):
        """The same table in two files is the collision waiting to happen."""
        a = length_table(FORMATTER.read_text(encoding="utf-8"))
        b = length_table(PAPER_TYPES.read_text(encoding="utf-8"))
        self.assertTrue(b, "no length-target table found in paper-types.md")
        self.assertEqual(a, b, "the two copies of the length table disagree")

    def test_paper_types_reconciles_too(self):
        self.assertEqual(
            table_problems(length_table(PAPER_TYPES.read_text(encoding="utf-8"))),
            [])

    def test_both_files_explain_the_subtotal_gap(self):
        """The rows sum to 21,250 against a stated total of 21,000. That gap is
        fine and documented; an undocumented one would read as an error."""
        for path in (FORMATTER, PAPER_TYPES):
            with self.subTest(file=path.name):
                self.assertIn("21,250", path.read_text(encoding="utf-8"))

    def test_the_check_fails_on_the_share_column_it_was_written_for(self):
        broken = [("Abstract", 250, 1), ("Introduction", 2500, 12),
                  ("Literature review", 6000, 29), ("Methodology", 2500, 12),
                  ("Results", 6000, 29), ("Discussion", 3000, 14),
                  ("Conclusion", 1000, 5), ("Total", 21000, 100)]
        problems = table_problems(broken)
        self.assertTrue(problems, "the share-column check cannot fail")
        self.assertTrue(any("102" in p for p in problems), problems)


class DistributionTests(unittest.TestCase):
    def test_the_length_mix_is_a_distribution_and_the_mean_follows_from_it(self):
        self.assertEqual(
            distribution_problems(ENTROPY.read_text(encoding="utf-8"),
                                  POLISH.read_text(encoding="utf-8")), [])

    def test_the_check_fails_on_a_mix_that_does_not_sum_to_100(self):
        entropy = ("roughly 30 percent short (under 15 words), 50 percent "
                   "medium (15 to 25) and 23 percent long (over 25)")
        polish = ("mean sentence length near 19 words ... band midpoints of "
                  "roughly 10, 20 and 30 words")
        problems = distribution_problems(entropy, polish)
        self.assertTrue(any("103" in p for p in problems), problems)

    def test_the_check_fails_when_the_two_stages_disagree_on_the_mean(self):
        entropy = ("roughly 30 percent short (under 15 words), 50 percent "
                   "medium (15 to 25) and 20 percent long (over 25)")
        polish = ("mean sentence length near 24 words ... band midpoints of "
                  "roughly 10, 20 and 30 words")
        problems = distribution_problems(entropy, polish)
        self.assertTrue(any("gives 19.0" in p for p in problems), problems)


class ScaleTierTests(unittest.TestCase):
    def test_the_two_files_agree_on_the_tiers(self):
        self.assertEqual(
            tier_problems(SKILL_MD.read_text(encoding="utf-8"),
                          PAPER_TYPES.read_text(encoding="utf-8")), [])

    def test_the_check_fails_when_a_tier_drops_the_assembly_stage(self):
        """Verbatim the defect: a short-piece tier without 9.5 reaches stage 10
        with no `full_draft.md` to read."""
        pt = PAPER_TYPES.read_text(encoding="utf-8").replace(
            "1-7, then 9.5, 10, 11, 15", "1-7, then 10, 11, 15")
        problems = tier_problems(SKILL_MD.read_text(encoding="utf-8"), pt)
        self.assertTrue(problems, "the tier check cannot fail")
        self.assertTrue(any("9.5" in p for p in problems), problems)


# --- citation styles, documented against the code ---------------------------

STYLES_DOC = ROOT / "references" / "citation-styles.md"


def _citations_module():
    spec = importlib.util.spec_from_file_location(
        "opendraft_citations_for_docs", ROOT / "scripts" / "citations.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def documented_styles(text):
    """{`--style` value} as the reference's own tables give them."""
    return set(re.findall(r"^\|[^|]+\|\s*`([a-z]+)`\s*\|", text, re.M))


def rendered_style_blocks(text):
    """{heading: [reference entries]} for each rendered sample.

    Reads only inside the fenced sample, because the prose sentence after the
    fence and the closing fence itself both look like content to a naive line
    filter and inflate the count."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("### ")]
    blocks = {}
    for n, i in enumerate(starts):
        block = lines[i:starts[n + 1] if n + 1 < len(starts) else len(lines)]
        fences = [j for j, x in enumerate(block) if x.strip().startswith("```")]
        if len(fences) < 2:
            continue
        fenced = block[fences[0] + 1:fences[1]]
        heads = [j for j, x in enumerate(fenced) if x.strip() == "## References"]
        if heads:
            blocks[block[0][4:].strip()] = [x for x in fenced[heads[0] + 1:]
                                            if x.strip()]
    return blocks


class CitationStyleTests(unittest.TestCase):
    """The styles reference counts its own samples correctly, and matches code."""

    def test_the_documented_styles_are_the_code_s_styles(self):
        documented = documented_styles(STYLES_DOC.read_text(encoding="utf-8"))
        self.assertEqual(documented, set(_citations_module().ALL_STYLES))

    def test_the_stated_count_matches_what_is_shown(self):
        text = STYLES_DOC.read_text(encoding="utf-8")
        self.assertIn("## The six styles", text)
        self.assertEqual(len(documented_styles(text)), 6)
        self.assertEqual(len(rendered_style_blocks(text)), 6)

    def test_every_sample_renders_the_four_fixture_sources(self):
        text = STYLES_DOC.read_text(encoding="utf-8")
        self.assertIn("The same four sources", text)
        blocks = rendered_style_blocks(text)
        self.assertTrue(blocks, "no rendered samples found")
        for style, entries in blocks.items():
            with self.subTest(style=style):
                self.assertEqual(len(entries), 4, entries)

    def test_the_check_would_catch_a_dropped_entry(self):
        mutated = STYLES_DOC.read_text(encoding="utf-8").replace(
            "\nNguyen, L. (2021). Open infrastructure governance. "
            "https://doi.org/10.5555/oig.2021.001\n", "\n")
        self.assertEqual(len(rendered_style_blocks(mutated)["APA 7th"]), 3)


# --- source floors against the scale tiers ----------------------------------

FLOOR_LINE = re.compile(r"Minimum reference count:([^\n]*)")
FLOOR_ITEM = re.compile(r"(\d+)\+?\s+for an?\s+([a-z ]+?)\s*(?:,|\.|$)")
PRECEDENCE = re.compile(r"floor governs", re.I)


def per_type_floors(formatter_text):
    """{paper type: minimum references} as the formatter states them."""
    line = FLOOR_LINE.search(formatter_text)
    return ({kind: int(n) for n, kind in FLOOR_ITEM.findall(line.group(1))}
            if line else {})


def _band(cell):
    """(low, high) for a tier's source cell; high is None when open-ended."""
    ranged = re.match(r"\s*(\d[\d,]*)\s*-\s*(\d[\d,]*)", cell)
    if ranged:
        return (int(ranged.group(1).replace(",", "")),
                int(ranged.group(2).replace(",", "")))
    open_ended = re.match(r"\s*(\d[\d,]*)\s*\+", cell)
    return (int(open_ended.group(1).replace(",", "")), None) if open_ended else None


def source_floor_problems(formatter_text, paper_types_text):
    """[problem] where a per-type floor outruns a tier band with no rule stated.

    A literature review is the default paper type and a full paper is the
    default scale, so these two numbers meet in the commonest request this
    pipeline gets, not in an edge case. Either the bands accommodate every
    floor, or the reconciling file says which one wins."""
    floors = per_type_floors(formatter_text)
    if not floors:
        return ["no per-type reference floor found in the formatter; this "
                "check would otherwise pass vacuously"]
    rows = tier_rows(paper_types_text)
    if not rows:
        return ["no scale tiers found; this check would otherwise pass vacuously"]
    clashes = [f"{kind} floor {n} exceeds the '{row[0]}' band {row[3]}"
               for row in rows if _band(row[3]) and _band(row[3])[1] is not None
               for kind, n in floors.items() if n > _band(row[3])[1]]
    if clashes and not PRECEDENCE.search(paper_types_text):
        return clashes + ["and no precedence between them is stated"]
    return []


class SourceFloorTests(unittest.TestCase):
    """The per-type floor and the per-scale band cannot both be silent."""

    def test_the_floors_and_the_tiers_are_reconciled(self):
        problems = source_floor_problems(
            FORMATTER.read_text(encoding="utf-8"),
            PAPER_TYPES.read_text(encoding="utf-8"))
        self.assertEqual(problems, [], problems)

    def test_the_floors_are_actually_found(self):
        floors = per_type_floors(FORMATTER.read_text(encoding="utf-8"))
        self.assertEqual(floors.get("literature review"), 50, floors)
        self.assertEqual(floors.get("empirical paper"), 20, floors)

    def test_the_check_fails_when_the_precedence_sentence_goes_away(self):
        stripped = PRECEDENCE.sub(
            "floor is mentioned", PAPER_TYPES.read_text(encoding="utf-8"))
        problems = source_floor_problems(
            FORMATTER.read_text(encoding="utf-8"), stripped)
        self.assertTrue(any("literature review floor" in p for p in problems),
                        problems)

    def test_the_check_refuses_to_pass_vacuously(self):
        self.assertTrue(source_floor_problems(
            "no floors here", PAPER_TYPES.read_text(encoding="utf-8")))
        self.assertTrue(source_floor_problems(
            FORMATTER.read_text(encoding="utf-8"), "no tiers here"))


# --- pipeline table against the agents' own declarations --------------------

PIPELINE_ROW = re.compile(
    r"^\|\s*(\d+(?:\.\d+)?)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", re.M)
BACKTICKED = re.compile(r"`([^`]+)`")


def _normalise_write(path):
    """Stage 7 names the file it creates; every other stage names the glob."""
    return "sections/*.md" if path.startswith("sections/") else path


def _declared_writes(agent_path):
    line = re.search(r"^\*\*Writes:\*\*(.*)$",
                     agent_path.read_text(encoding="utf-8"), re.M)
    return ({_normalise_write(p) for p in BACKTICKED.findall(line.group(1))}
            if line else set())


def writes_problems(skill_text, root=ROOT):
    """[problem] where the pipeline table and an agent disagree on its outputs.

    The table is the only place a reader meets every stage at once, so a file
    missing from a row is a file nobody creates, however carefully the agent's
    own header declares it. Rows reading "fixes" stand in prose for the in-place
    edit the agent declares, so `full_draft.md` and the section glob are allowed
    to be absent from exactly those rows and nowhere else."""
    problems = []
    for num, _stage, agent_cell, writes_cell in PIPELINE_ROW.findall(skill_text):
        named = re.search(r"(agents/[^`]+\.md)", agent_cell)
        if not named:
            continue
        path = root / named.group(1)
        if not path.exists():
            problems.append(f"stage {num}: {named.group(1)} does not exist")
            continue
        declared = _declared_writes(path)
        listed = {_normalise_write(p) for p in BACKTICKED.findall(writes_cell)}
        missing = declared - listed
        if "fixes" in writes_cell:
            missing -= {"full_draft.md", "sections/*.md"}
        problems += [f"stage {num}: {path.name} writes {p}, table omits it"
                     for p in sorted(missing)]
        problems += [f"stage {num}: table lists {p}, {path.name} does not"
                     for p in sorted(listed - declared)]
    return problems


class PipelineTableTests(unittest.TestCase):
    """Every row lists what that stage's own file says it writes."""

    def test_the_table_matches_every_agent(self):
        problems = writes_problems(SKILL_MD.read_text(encoding="utf-8"))
        self.assertEqual(problems, [], problems)

    def test_the_table_covers_every_stage_and_assembly(self):
        rows = PIPELINE_ROW.findall(SKILL_MD.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 20, [r[0] for r in rows])

    def test_the_check_fails_on_the_omission_it_was_written_for(self):
        mutated = SKILL_MD.read_text(encoding="utf-8").replace(
            "`research/citations.json`, `research/citation-notes.md`",
            "`research/citations.json`")
        problems = writes_problems(mutated)
        self.assertTrue(any("citation-notes.md" in p for p in problems),
                        problems)

    def test_the_check_fails_on_a_row_listing_a_file_the_agent_never_writes(self):
        mutated = SKILL_MD.read_text(encoding="utf-8").replace(
            "`agents/02-scribe.md` | `research/summaries.md` |",
            "`agents/02-scribe.md` | `research/summaries.md`, "
            "`review/scribe.md` |")
        problems = writes_problems(mutated)
        self.assertTrue(any("review/scribe.md" in p for p in problems),
                        problems)


# --- accuracy guarantees ----------------------------------------------------

GUARANTEE = re.compile(r"\bguarantees?\b", re.I)
GUARANTEE_PROHIBITION = re.compile(
    r"\b(?:any|any other|any similar)\s+accuracy guarantees?\b", re.I)


def guarantee_claims(text):
    """[snippet] for uses of "guarantee" that assert one instead of banning one.

    Naming the banned phrase ("any accuracy guarantee") is the single legitimate
    use of the word in this bundle. Saying the skill makes such a promise is the
    defect, and it survives review because the sentence asserting it and the
    sentence forbidding it are hundreds of lines apart in the same file."""
    allowed = [m.span() for m in GUARANTEE_PROHIBITION.finditer(text)]
    return [text[max(0, m.start() - 60):m.end() + 20].replace("\n", " ")
            for m in GUARANTEE.finditer(text)
            if not any(s <= m.start() and m.end() <= e for s, e in allowed)]


class AccuracyGuaranteeTests(unittest.TestCase):
    """The word may name a claim the bundle bans; it may never make one."""

    def test_no_bundle_file_asserts_a_guarantee(self):
        for path in shipped_text_files():
            with self.subTest(file=path.name):
                claims = guarantee_claims(path.read_text(encoding="utf-8"))
                self.assertEqual(claims, [], f"{path.name}: {claims}")

    def test_the_provenance_and_notices_files_are_covered(self):
        # They are user-visible, they quote the upstream project's own success
        # rate, and they sit outside doc_files(). A claim added to either would
        # have been invisible to this check before they were listed here.
        names = {p.name for p in shipped_text_files()}
        self.assertIn("DERIVATION.json", names)
        self.assertIn("THIRD_PARTY_NOTICES.md", names)

    def test_the_check_fails_on_the_sentence_it_was_written_for(self):
        bad = guarantee_claims(
            "gate, which defeats the only citation guarantee this skill makes.")
        self.assertEqual(len(bad), 1, bad)

    def test_the_check_allows_naming_the_banned_phrase(self):
        for permitted in ('zero errors, exhaustive research, any accuracy '
                          'guarantee.',
                          'or any similar accuracy guarantee, anywhere in the '
                          'draft',
                          'or any other accuracy guarantee. State the actual '
                          'counts.'):
            with self.subTest(text=permitted[:40]):
                self.assertEqual(guarantee_claims(permitted), [])

    def test_the_check_ignores_the_other_word_sense(self):
        self.assertEqual(guarantee_claims("it is guaranteed to fail"), [])


class EmDashTests(unittest.TestCase):
    """No em dash anywhere in the bundle, prose or code."""

    def test_no_em_dash_in_any_bundle_file(self):
        for path in shipped_text_files():
            with self.subTest(file=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("—", text, f"em dash in {path.name}")

    def test_the_check_would_catch_one(self):
        self.assertIn("—", "a sentence — with one")


if __name__ == "__main__":
    unittest.main()
