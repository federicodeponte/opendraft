"""Every command this bundle tells a reader to run has to exist.

A prompt is documentation the model executes. When a file says
`python3 scripts/citations.py add`, an agent runs it, argparse exits 2, and the
pipeline stops on a command that was never real. That happened: compile's
`MissingSourceError` told the user to add the source with a subcommand
`citations.py` does not have, and the wrong instruction was then quoted verbatim
into `references/citation-styles.md` and `agents/04-citation-manager.md`. Nothing
caught it, because prose is not executed by the test suite and argparse is not
consulted by the prose.

So this module consults argparse. It reads the real parsers, scans every
markdown and Python file in the bundle for anything shaped like an invocation,
and asserts that each subcommand and each flag it finds is one the script
actually accepts. It checks the error messages too, since those are instructions
a user follows at exactly the moment things are already going wrong.
"""
import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS_DIR = ROOT / "scripts"

# `scripts/foo.py bar` with an optional `python3 ` in front. The tail is
# captured loosely and split later, because an invocation runs to the end of a
# sentence, a code fence line, or a shell pipe, and prose does all three.
# Quotes must stay inside the tail: the first version of this stopped at one,
# which made every flag after a quoted argument invisible, and the flag check
# silently passed everything. A backtick still ends it, since that closes a
# markdown code span. So does the start of the next invocation: a sentence that
# names two commands is common, and a tail that runs through the second one
# hides it from `finditer` entirely, which is how the original bug survived a
# first draft of this very check.
INVOCATION = re.compile(
    r"scripts/(?P<script>[a-z_]+)\.py(?P<tail>(?:(?!scripts/)[^\n`])*)")

# A quoted argument is one token whatever is inside it.
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")

# Tokens that are arguments rather than flags or subcommands.
PLACEHOLDER = re.compile(r"^[<\"']|[/.]|^\$")

# argparse gives these to every parser whether or not anyone declared them.
ALWAYS_ACCEPTED = {"-h", "--help"}


def _load(path):
    spec = importlib.util.spec_from_file_location(f"opendraft_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _subparser_action(parser):
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action
    return None


def script_surface():
    """{script stem: {subcommand: {accepted flags}}}, read from argparse itself.

    A script with no subparsers maps to `{None: {flags}}`, so the same walk
    covers both shapes.
    """
    surface = {}
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        parser = _load(path)._build_parser()
        action = _subparser_action(parser)
        top_level = {opt for a in parser._actions for opt in a.option_strings}
        if action is None:
            surface[path.stem] = {None: top_level | ALWAYS_ACCEPTED}
            continue
        surface[path.stem] = {
            name: {opt for a in sub._actions for opt in a.option_strings}
            | top_level | ALWAYS_ACCEPTED
            for name, sub in action.choices.items()
        }
    return surface


def _tokens(tail):
    """The words of an invocation, stopping where the command plausibly ends.

    Prose continues past a command; a shell line does not. Cutting at the first
    redirect, pipe or sentence boundary keeps the next clause's words from being
    read as arguments.
    """
    tail = QUOTED.sub(" ARG ", tail)
    for stop in (">", "|", "&&", ";", ", ", ". ", " -- "):
        tail = tail.split(stop)[0]
    return tail.split()


def undocumented_invocations(text, name, surface):
    """[(file, line, what, why)] for every command the scripts do not accept."""
    problems = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in INVOCATION.finditer(line):
            script = match.group("script")
            if script not in surface:
                problems.append((name, lineno, f"scripts/{script}.py",
                                 "no such script"))
                continue
            commands = surface[script]
            tokens = _tokens(match.group("tail"))
            if None in commands:
                subcommand, rest = None, tokens
            elif not tokens or tokens[0].startswith("-"):
                # A bare mention like "scripts/citations.py takes a database"
                # is prose about the script, not an invocation of it.
                continue
            else:
                subcommand, rest = tokens[0], tokens[1:]
                if PLACEHOLDER.search(subcommand):
                    continue
                if subcommand not in commands:
                    problems.append(
                        (name, lineno, f"{script}.py {subcommand}",
                         f"not a subcommand; have {sorted(commands)}"))
                    continue
            accepted = commands[subcommand]
            for token in rest:
                if not token.startswith("-") or PLACEHOLDER.search(token):
                    continue
                flag = token.split("=")[0]
                if flag not in accepted:
                    problems.append(
                        (name, lineno,
                         f"{script}.py {subcommand or ''} {flag}".strip(),
                         "not an accepted flag"))
    return problems


def bundle_files():
    for path in sorted(ROOT.rglob("*.md")):
        if "__pycache__" not in path.parts:
            yield path
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        yield path


class DocumentedCommandsExistTests(unittest.TestCase):
    """Nothing in the bundle names a command the scripts will not run."""

    @classmethod
    def setUpClass(cls):
        cls.surface = script_surface()

    def test_every_script_exposes_the_commands_the_suite_assumes(self):
        """Guards the guard: an empty surface would make everything pass."""
        self.assertEqual(
            sorted(self.surface["citations"]),
            ["bibtex", "build", "compile", "verify"])
        self.assertIn("find", self.surface["sources"])

    def test_no_file_in_the_bundle_names_a_command_that_does_not_exist(self):
        problems = []
        for path in bundle_files():
            problems += undocumented_invocations(
                path.read_text(encoding="utf-8"),
                str(path.relative_to(ROOT)), self.surface)
        self.assertEqual(
            problems, [],
            "a file tells the reader to run something argparse will reject; "
            "an agent following it stops the pipeline on exit 2: "
            f"{problems}")

    def test_the_check_catches_the_bug_it_was_written_for(self):
        """The real regression: compile's own error named `citations.py add`."""
        sample = ("find a source with python3 scripts/sources.py find "
                  "\"<topic>\", add it with python3 scripts/citations.py add, "
                  "and replace the marker")
        problems = undocumented_invocations(sample, "<sample>", self.surface)
        self.assertTrue(problems, "the check cannot fail")
        self.assertIn("citations.py add", problems[0][2])

    def test_the_check_catches_an_invented_flag(self):
        sample = "python3 scripts/sources.py find \"aging\" --n 12 --deep"
        problems = undocumented_invocations(sample, "<sample>", self.surface)
        self.assertTrue(problems, "the flag check cannot fail")
        self.assertIn("--deep", problems[0][2])

    def test_the_check_catches_a_script_that_is_not_there(self):
        problems = undocumented_invocations(
            "run python3 scripts/summarize.py draft.md", "<sample>",
            self.surface)
        self.assertEqual([p[3] for p in problems], ["no such script"])

    def test_the_check_stays_quiet_on_real_invocations_and_on_prose(self):
        for sample in (
            "python3 scripts/citations.py build new.json -o research/citations.json",
            "python3 scripts/citations.py compile full_draft.md "
            "-d research/citations.json --style apa -o final.md",
            "python3 scripts/sources.py find \"<topic>\" --json > new.json",
            "python3 scripts/integrity.py final.md",
            "`scripts/citations.py` is the only route into the database.",
            "See scripts/export.py for the DOCX path.",
            "python3 scripts/citations.py verify -d research/citations.json",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(
                    undocumented_invocations(sample, "<sample>", self.surface),
                    [])


if __name__ == "__main__":
    unittest.main()
