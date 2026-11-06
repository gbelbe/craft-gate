#!/usr/bin/env python3
"""Run only the test files a change can affect, from what the last full run saw each test execute.

    python scripts/test_impact.py record --coverage .coverage --out .test-impact.json
    python scripts/test_impact.py select --map .test-impact.json

``record`` reads a coverage data file made with per-test contexts
(``pytest --cov --cov-context=test``) and writes a small map: for each source file, which test
files executed which lines, and the commit the run was made at. The run on the main branch makes
it, a full run every project already does.

``select`` compares the working tree with that commit and prints what to run, one test file a line:

* a changed source line selects the test files that executed it. A line no test recorded
  (module-level code runs at import, outside any test) selects every test file that touched the
  file at all;
* a changed test file selects itself; a changed ``conftest.py`` or helper beside the tests, and a
  file the map cannot place (a lock file, a workflow, a data file, a feature file), selects
  everything;
* a documentation file selects nothing.

The output is ``ALL`` when it cannot narrow: no map, a map that cannot be read or is older than
``--max-age-days``, or a commit that is not in this checkout. It never selects fewer files than a
change can affect, only more. The map's line numbers are those of its own commit, so the diff is
read against that commit and its old side is used: a main branch that has moved on since shifts
nothing.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
from gitdiff import git  # noqa: E402

MAP_VERSION = 1
VERSION, COMMIT, CREATED, SOURCES = "version", "commit", "created", "sources"  # the map's keys
ALL = "ALL"
DEFAULT_MAP = ".test-impact.json"
DEFAULT_MAX_AGE_DAYS = 14
DOCUMENTATION = ("*.md", "*.rst", "*.txt", "docs/*", "LICENSE*", "README*")
_OLD_SIDE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.MULTILINE)
_TEST_FILE = re.compile(r"(^|/)(test_[^/]*|[^/]*_test)\.py$")
_TEST_DIRECTORIES = frozenset({"tests", "test"})


def file_of_context(context: str) -> str | None:
    """'tests/a/test_x.py::test_y|run' -> 'tests/a/test_x.py'; outside any test (empty) -> None."""
    path = context.split("::", 1)[0].split("|", 1)[0]
    return path or None


def to_ranges(lines: list[int]) -> list[list[int]]:
    """[1, 2, 3, 7, 9, 10] -> [[1, 3], [7, 7], [9, 10]]: the runs of consecutive lines."""
    runs: list[list[int]] = []
    for line in sorted(lines):
        if runs and line == runs[-1][1] + 1:
            runs[-1][1] = line
        else:
            runs.append([line, line])
    return runs


def covers(ranges: list[list[int]], lines: set[int]) -> bool:
    """Whether any of *lines* lies in one of the inclusive *ranges*."""
    return any(start <= line <= end for start, end in ranges for line in lines)


def build_map(executed: dict[str, dict[int, list[str]]], commit: str, when: datetime) -> dict:
    """The map of a run: *executed* is {source file: {line: [contexts]}}."""
    sources: dict[str, dict[str, list[list[int]]]] = {}
    for source, by_line in executed.items():
        per_test: dict[str, list[int]] = defaultdict(list)
        for line, contexts in by_line.items():
            for context in contexts:
                if test := file_of_context(context):
                    per_test[test].append(line)
        sources[source] = {test: to_ranges(lines) for test, lines in sorted(per_test.items())}
    return {
        VERSION: MAP_VERSION,
        COMMIT: commit,
        CREATED: when.isoformat(),
        SOURCES: sources,
    }


def read_coverage(path: Path) -> dict[str, dict[int, list[str]]]:
    """{source file: {line: [contexts]}} from a coverage data file."""
    from coverage import CoverageData  # noqa: PLC0415  # only `record` needs coverage

    data = CoverageData(basename=str(path))
    data.read()
    return {file: data.contexts_by_lineno(file) for file in data.measured_files()}


def repo_relative(file: str, root: Path) -> str:
    """*file* as coverage names it (absolute, or relative if the project asks) -> root-relative."""
    path = Path(file)
    return path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()


def record(coverage: Path, out: Path, root: Path) -> None:
    commit = git(["rev-parse", "HEAD"], cwd=root).strip()
    executed = {repo_relative(f, root): v for f, v in read_coverage(coverage).items()}
    out.write_text(json.dumps(build_map(executed, commit, datetime.now(UTC))) + "\n")


def load_map(path: Path, max_age_days: int, now: datetime) -> dict | None:
    """The map at *path*, or None when it is missing, unreadable, of another version or too old."""
    try:
        data = json.loads(path.read_text())
        created = datetime.fromisoformat(data[CREATED])
        usable = data[VERSION] == MAP_VERSION and now - created <= timedelta(days=max_age_days)
    except (OSError, KeyError, TypeError, ValueError):
        return None
    return data if usable else None


def is_documentation(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in DOCUMENTATION)


def is_test_path(path: str) -> bool:
    return any(part in _TEST_DIRECTORIES for part in PurePosixPath(path).parts[:-1])


def old_side_lines(diff: str) -> set[int]:
    """The lines of the old file a ``-U0`` diff touches; an insertion touches its two neighbours."""
    lines: set[int] = set()
    for start, count in _OLD_SIDE.findall(diff):
        first, size = int(start), 1 if count == "" else int(count)
        if size == 0:
            lines.update((first, first + 1))
        else:
            lines.update(range(first, first + size))
    return lines


def tests_for_source(entry: dict[str, list[list[int]]], lines: set[int]) -> set[str]:
    """The test files that ran any of *lines*; all that ran the file if a line has no test to name.

    A line no test names is one run outside any test (module-level code, executed when the file is
    imported) or one no test ran (and a comment or blank line, which nothing runs): the tests that
    touched the file at all are the ones that can be affected.
    """
    named = {
        line for ranges in entry.values() for start, end in ranges for line in range(start, end + 1)
    }
    if not lines <= named:
        return set(entry)
    return {test for test, ranges in entry.items() if covers(ranges, lines)}


def changes_since(commit: str, root: Path) -> list[tuple[str, str, str]]:
    """(status letter, old path, new path) of every file the working tree changed since *commit*.

    A file not yet added to git counts as added: a change run before it is committed misses nothing.
    """
    out = git(["diff", "--name-status", "-M", commit], cwd=root, check=False)
    rows = []
    for row in out.splitlines():
        fields = row.split("\t")
        rows.append((fields[0][0], fields[1], fields[-1]))
    untracked = git(["ls-files", "--others", "--exclude-standard"], cwd=root, check=False)
    rows += [("A", path, path) for path in untracked.splitlines()]
    return rows


def affected(root: Path, impact: dict, change: tuple[str, str, str]) -> set[str] | str:
    """The test files one changed file can affect, or ALL."""
    status, old, new = change
    if is_documentation(new) and is_documentation(old):
        return set()
    if not new.endswith(".py"):
        return ALL
    if is_test_path(new):
        if status == "D":
            return set()
        return {new} if _TEST_FILE.search(new) else ALL  # else conftest.py, a helper or a fixture
    entry = impact[SOURCES].get(old)
    if entry is None:
        return set()  # never run by a test, or new: its tests are the changed ones
    diff = git(["diff", "-U0", "--no-color", impact[COMMIT], "--", old, new], cwd=root, check=False)
    return tests_for_source(entry, old_side_lines(diff))


def select(root: Path, impact: dict, ignore: frozenset[str] = frozenset()) -> set[str] | str:
    """The test files to run for the working tree, or ALL; *ignore* names files that are no change.

    The map itself is one: a run restores it into the checkout, where git sees it as a new file.
    """
    chosen: set[str] = set()
    for change in changes_since(impact[COMMIT], root):
        if change[2] in ignore:
            continue
        picked = affected(root, impact, change)
        if picked == ALL:
            return ALL
        chosen |= picked
    return chosen


def _inside(path: Path, root: Path) -> str:
    """*path* relative to *root*, or as given when it lies elsewhere (so it is no change)."""
    resolved = path.resolve()
    return resolved.relative_to(root).as_posix() if resolved.is_relative_to(root) else str(path)


def commit_present(commit: str, root: Path) -> bool:
    return bool(git(["cat-file", "-t", commit], cwd=root, check=False).strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser(
        "record", help="write the map from a coverage run made with --cov-context=test"
    )
    rec.add_argument("--coverage", default=".coverage", type=Path)
    rec.add_argument("--out", default=DEFAULT_MAP, type=Path)
    sel = sub.add_parser("select", help="print the test files the working tree can affect, or ALL")
    sel.add_argument("--map", default=DEFAULT_MAP, type=Path)
    sel.add_argument("--max-age-days", default=DEFAULT_MAX_AGE_DAYS, type=int)
    for each in (rec, sel):
        each.add_argument("--path", default=".", type=Path, help="the repository root")
    args = parser.parse_args(argv)
    root = args.path.resolve()
    if args.command == "record":
        record(args.coverage, args.out, root)
        return 0
    impact = load_map(args.map, args.max_age_days, datetime.now(UTC))
    if impact is None or not commit_present(impact[COMMIT], root):
        print(ALL)
        return 0
    picked = select(root, impact, frozenset({_inside(args.map, root)}))
    print(picked if picked == ALL else "\n".join(sorted(picked)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
