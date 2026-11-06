#!/usr/bin/env python3
"""Plan a diff-scoped mutation run: drop only the cached verdicts a change can have staled.

`mutmut run` already re-tests a production function whose source hash changed. What it cannot see is
everything else that decides a verdict: a test that was edited, a fixture or helper those tests
import,
a data file they read, an unmutated module a mutated function calls. Its only answer to those is the
blunt one (`on_dependency_change = "rerun"`): reset every verdict and rerun the whole campaign —
minutes
spent re-proving functions the change cannot have touched.

This script turns the diff into the narrowest set of cached verdicts to drop, then lets an ordinary
`mutmut run` re-test exactly those (it re-tests every mutant whose verdict is empty). Only a
function the diff touches is judged, so only its verdicts are dropped; a function merely covered
by an edited test keeps its cached verdicts, though the edited tests are still measured again so
a touched function sees the right ones:

    mutation_plan.py run --base origin/main      # plan, drop, `mutmut run`, repeat once if needed
    mutation_plan.py plan --base origin/main     # read-only: what would be dropped, and why

The first initialisation of a repo (no `mutants/` cache), and the few causes that really are
cache-wide
(a lock file, the dependency list, pytest's own arguments, the root conftest), still run in full.
A repo may set `[mutation] dependency-change = "keep"` in craft-gate.toml: a lock file or dependency
list change then keeps the cached verdicts (the nightly campaign starts from nothing and rebuilds
them), instead of re-running every mutant for a bump that touches no function. Test setup
(`pytest.ini`, `tool.pytest`, the root conftest) still runs in full.
Likewise `unmutated-change = "defer"`: a change to a module mutmut does not mutate then resets
nothing in a pull request (the nightly campaign re-tests what it reaches), instead of every function
covered by a test that imports it, however indirectly. The functions the diff touches are still
re-tested and judged.
A test file git sees renamed with its content unchanged (a folder of tests moved into bricks) is
the same tests: the cache follows it to its new path, nothing it covered is reset, and nothing is
measured again. A rename that also edits the file is a changed test, as ever; a conftest or helper
added where tests arrived by rename resets nothing for them.
Pair it with `on_dependency_change = "warn"` and no `tests/**/*.py` in
`cache_invalidation_files`, or
mutmut's own invalidation resets everything before this script has a say.

It reads and rewrites mutmut 3.8's `mutants/` files (the `.meta` verdicts, `mutmut-stats.json`).
That is
the same kind of coupling `check_mutation_ratchet.py` already accepts; every assumption about
the format
is checked before use and a mismatch falls back to a full run rather than a wrong incremental one.

Usage:
    python scripts/mutation_plan.py plan  [--base origin/main] [--path .] [--json]
    python scripts/mutation_plan.py apply [--base origin/main] [--path .]
    python scripts/mutation_plan.py run   [--base origin/main] [--path .]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
from check_mutation_ratchet import function_ranges  # noqa: E402
from gate_config import load_settings  # noqa: E402
from gate_timing import step  # noqa: E402
from gitdiff import touched_names  # noqa: E402

try:  # Python 3.11+; older interpreters fall back to a full run rather than guessing
    import tomllib
except ImportError:  # pragma: no cover - exercised only on 3.10
    tomllib = None  # type: ignore[assignment]

# A change to any of these can alter every verdict: rerun everything.
FULL_RERUN_FILES = (
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "requirements*.txt",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
)
LOCK_FILES = ("uv.lock", "poetry.lock", "Pipfile.lock", "requirements*.txt")
FULL_RERUN_SECTIONS = (
    "project.dependencies",
    "project.optional-dependencies",
    "build-system",
    "tool.pytest",
    "tool.mutmut.pytest_add_cli_args",
)
# What `dependency-change = "keep"` stops treating as cache-wide: dependency lists, not test setup.
DEPENDENCY_SECTIONS = ("project.dependencies", "project.optional-dependencies", "build-system")
_RENAME_PATHS = 2  # `git diff --name-status` names a rename as old<TAB>new
MUTATION_GATE = "mutation"
_PASSES = 2  # plan and run once, and once more when new tests had to be measured first
_SELECTION_KEY = "tool.mutmut.pytest_add_cli_args_test_selection"


@dataclass(frozen=True)
class Selection:
    """The test files in mutmut's selection, now and at the base ref."""

    now: tuple[str, ...]
    before: tuple[str, ...]


@dataclass(frozen=True)
class ImportGraph:
    """Who imports whom among the repo's own modules, and what each selected test file imports."""

    imports: dict[str, set[str]] = field(default_factory=dict)  # module -> repo modules it imports
    tests: dict[str, set[str]] = field(default_factory=dict)  # test file -> modules it imports


@dataclass(frozen=True)
class Inputs:  # pylint: disable=too-many-instance-attributes  # a record: one field per fact the decision reads
    """Everything the decision needs, gathered up front so the decision itself does no I/O."""

    changes: tuple[tuple[str, str], ...]  # (status A/M/D, repo-relative path)
    mutated_files: frozenset[str]  # files mutmut mutates
    selection: Selection
    stats: dict | None  # mutants/mutmut-stats.json, None when there is no cache
    sources: dict[str, str] = field(default_factory=dict)  # path -> text, tests and mutated files
    changed_sections: tuple[str, ...] = ()  # pyproject sections that differ from the base
    graph: ImportGraph = field(default_factory=ImportGraph)
    keep_on_dependency_change: bool = False  # dependency-change = "keep": cached verdicts survive
    defer_unmutated_change: bool = (
        False  # unmutated-change = "defer": the nightly run re-tests them
    )
    renamed: tuple[tuple[str, str], ...] = ()  # (old, new) test files moved with no change
    touched: frozenset[tuple[str, str]] | None = (
        None  # (module, qualified name) of the mutated functions the diff touches; None: not known
    )


@dataclass(frozen=True)
class Plan:
    mode: str  # "init" (no cache), "full" (cache-wide cause) or "incremental"
    reasons: tuple[str, ...] = ()
    reset_functions: tuple[str, ...] = ()  # mutmut's mangled names whose verdicts are dropped
    stale_tests: tuple[str, ...] = ()  # test ids whose coverage must be collected again
    selection_added: tuple[str, ...] = ()
    needs_second_pass: bool = (
        False  # new tests: their coverage is only known after one `mutmut run`
    )
    renamed: tuple[tuple[str, str], ...] = ()  # test files moved: their cached tests follow them


# ── the decision ────────────────────────────────────────────────────────────────────────────────


def plan(inputs: Inputs) -> Plan:
    if inputs.stats is None:
        return Plan("init", ("no mutation cache: first initialisation",))
    full = _full_rerun_reasons(inputs)
    if full:
        return Plan("full", tuple(full))
    return _incremental(inputs)


def _full_rerun_reasons(inputs: Inputs) -> list[str]:
    reasons = []
    for _status, path in inputs.changes:
        name = path.rsplit("/", 1)[-1]
        if _matches(name, FULL_RERUN_FILES) and not (
            inputs.keep_on_dependency_change and _matches(name, LOCK_FILES)
        ):
            reasons.append(f"{path} changed: it can alter any verdict")
        if path in ("conftest.py", "tests/conftest.py"):
            reasons.append(f"{path} changed: it applies to every test")
    reasons += [
        f"{section} changed in pyproject.toml: it can alter any verdict"
        for section in inputs.changed_sections
        if section in FULL_RERUN_SECTIONS
        and not (inputs.keep_on_dependency_change and section in DEPENDENCY_SECTIONS)
    ]
    return reasons


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


@dataclass
class _Domain:
    """What the changes so far have staled: the tests to re-measure, and why."""

    reasons: list[str] = field(default_factory=list)
    stale: set[str] = field(default_factory=set)
    second_pass: bool = False

    def add(self, tests: set[str], why: str) -> None:
        if tests:
            self.stale.update(tests)
            self.reasons.append(why)

    def note(self, why: str) -> None:
        """A reason that stales nothing: the change was seen and deliberately left alone."""
        self.reasons.append(why)


@dataclass(frozen=True)
class _Context:
    inputs: Inputs
    known_tests: set[str]
    selected: set[str]
    removed: set[str]
    arrived: frozenset[str] = frozenset()  # tests that came by rename: nothing about them is new

    def tests_in(self, prefixes: tuple[str, ...]) -> set[str]:
        return {t for t in self.known_tests if t.startswith(prefixes)}


def _selection_after_moves(inputs: Inputs) -> tuple[set[str], set[str], tuple[str, ...], set[str]]:
    """(selected, left, joined, landed): the selection now, the files that left it, those that
    joined it, and those that only arrived by a move, which is neither leaving nor joining."""
    before, selected = set(inputs.selection.before), set(inputs.selection.now)
    left_paths = {old for old, _new in inputs.renamed}
    landed = {new for _old, new in inputs.renamed}
    return (
        selected,
        before - selected - left_paths,
        tuple(sorted(selected - before - landed)),
        landed,
    )


def _incremental(inputs: Inputs) -> Plan:
    stats = renamed_stats(inputs.stats or {}, inputs.renamed)
    by_function: dict[str, list[str]] = stats.get("tests_by_mangled_function_name", {})
    known = set(stats.get("duration_by_test", {})).union(*map(set, by_function.values()))
    selected, removed, added, landed = _selection_after_moves(inputs)
    arrived = frozenset(t for t in known if t.split("::", 1)[0] in landed)
    ctx = _Context(inputs, known, selected, removed, arrived)

    domain = _Domain()
    domain.add(ctx.tests_in(tuple(f"{f}::" for f in removed)), "left the mutation selection")
    for status, path in inputs.changes:
        _classify(ctx, status, path, domain)

    reset = _functions_covered_by(by_function, domain.stale)
    reset |= _functions_reading_data(inputs, by_function)
    reset, left_alone = _touched_only(reset, inputs.touched)
    if left_alone:
        domain.note(
            f"{left_alone} function(s) covered by a changed test but not touched by the diff: "
            f"not re-tested (only touched functions are judged)"
        )
    return Plan(
        "incremental",
        tuple(domain.reasons),
        tuple(sorted(reset)),
        tuple(sorted(domain.stale)),
        added,
        domain.second_pass or bool(added),
        inputs.renamed,
    )


def _touched_only(
    reset: set[str], touched: frozenset[tuple[str, str]] | None
) -> tuple[set[str], int]:
    """(the functions to re-test, how many were left alone).

    Only a function the diff touches is judged, so only its verdicts need to be fresh; the others
    would be re-proved for nothing. The tests a change staled are still re-measured, which is what
    keeps a touched function's own coverage right. With *touched* unknown, nothing is narrowed.
    """
    if touched is None:
        return reset, 0
    kept = {fn for fn in reset if _function_key(fn) in touched}
    return kept, len(reset) - len(kept)


def _function_key(mangled: str) -> tuple[str, str]:
    """'pkg.mod.x_load' -> ('pkg.mod', 'load'); 'pkg.mod.xǁKǁrun' -> ('pkg.mod', 'K.run')."""
    module, name = split_mangled(mangled)
    if name.startswith("xǁ"):
        _marker, klass, method = name.split("ǁ", 2)
        return module, f"{klass}.{method}"
    return module, name[2:] if name.startswith("x_") else name


def _classify(ctx: _Context, status: str, path: str, domain: _Domain) -> None:
    """Add to *domain* whatever the change to *path* can have staled."""
    if path in ctx.selected or path in ctx.removed:
        tests = ctx.tests_in((f"{path}::",))
        if status == "A" and not tests:
            domain.second_pass = True  # new tests: nothing to reset until mutmut has measured them
            domain.reasons.append(f"{path} is new: its coverage is collected on the next run")
        else:
            domain.add(tests, f"{path} {_verb(status)}")
    elif path.startswith("tests/"):
        domain.add(_support_tests_for(ctx, status, path), f"{path} changed (test support)")
    elif path.endswith(".py") and path not in ctx.inputs.mutated_files:
        if ctx.inputs.defer_unmutated_change:
            domain.note(f"{path} changed (unmutated module): left to the nightly run")
            return
        stale = _dependent_tests(ctx.inputs, path, ctx.known_tests)
        domain.add(stale, f"{path} changed (unmutated module)")
    # a mutated file is left to mutmut, which hashes its functions itself


def _verb(status: str) -> str:
    return {"D": "was deleted", "A": "was added"}.get(status, "changed")


def _functions_covered_by(by_function: dict[str, list[str]], tests: set[str]) -> set[str]:
    return {fn for fn, covering in by_function.items() if tests.intersection(covering)}


def _support_tests_for(ctx: _Context, status: str, path: str) -> set[str]:
    """What a changed file under tests/ stales; a file *added* does not stale tests that moved in.

    Those tests were not there before, so nothing about them can have changed: a conftest created
    in the brick they moved to is part of the move.
    """
    tests = _support_tests(ctx.inputs, path, ctx.known_tests)
    return tests - ctx.arrived if status == "A" else tests


def _support_tests(inputs: Inputs, path: str, known_tests: set[str]) -> set[str]:
    """The tests a changed file under tests/ can affect: a conftest's subtree, a helper's importers,
    a data file's readers, else the tests nearest it."""
    name = path.rsplit("/", 1)[-1]
    directory = path.rsplit("/", 1)[0] if "/" in path else ""
    if name == "conftest.py":
        return {t for t in known_tests if t.startswith(f"{directory}/")}
    if name.endswith(".py"):
        files = _files_importing(inputs, path)
    elif name.endswith(".feature"):
        files = _feature_readers(
            inputs, path
        )  # a scenario nobody selected is read by no selected test
    else:
        files = {f for f in inputs.selection.now if name in inputs.sources.get(f, "")}
        files = files or _nearest_test_files(inputs, directory)
    return {t for t in known_tests if t.split("::", 1)[0] in files}


def _feature_readers(inputs: Inputs, path: str) -> set[str]:
    """The selected test files that bind this scenario file: by its name, or by a folder above it.

    pytest-bdd reads a feature only where a test names it (``scenarios("../features/viz")`` or
    ``scenarios("x.feature")``); with no selected test naming it, it cannot change a verdict.
    """
    parts = path.split("/")
    folders = ["/".join(parts[i:-1]) for i in range(len(parts) - 1)]
    markers = {parts[-1], *(folder for folder in folders if "/" in folder)}
    whole_tree = re.compile(r"features/?['\"]")
    return {
        f
        for f in inputs.selection.now
        if any(m in inputs.sources.get(f, "") for m in markers)
        or whole_tree.search(inputs.sources.get(f, ""))
    }


def _files_importing(inputs: Inputs, path: str) -> set[str]:
    stem = path.rsplit("/", 1)[-1][: -len(".py")]
    dotted = path[: -len(".py")].replace("/", ".")
    found = set()
    for test_file in inputs.selection.now:
        for module in _imported_names(inputs.sources.get(test_file, "")):
            if module in (stem, dotted) or module.endswith(f".{stem}"):
                found.add(test_file)
    return found


def _imported_names(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _nearest_test_files(inputs: Inputs, directory: str) -> set[str]:
    parts = directory.split("/")
    for depth in range(len(parts), 0, -1):
        prefix = "/".join(parts[:depth]) + "/"
        near = {f for f in inputs.selection.now if f.startswith(prefix)}
        if near:
            return near
    return set(inputs.selection.now)


def _module_of(path: str) -> str:
    dotted = path[: -len(".py")].replace("/", ".")
    return dotted[: -len(".__init__")] if dotted.endswith(".__init__") else dotted


def _dependent_tests(inputs: Inputs, path: str, known_tests: set[str]) -> set[str]:
    """Tests whose imports lead, directly or not, to the changed unmutated module."""
    reverse: dict[str, set[str]] = {}
    for module, imported in inputs.graph.imports.items():
        for target in imported:
            reverse.setdefault(target, set()).add(module)
    start = _module_of(path)
    reached, queue = {start}, deque([start])
    while queue:
        for importer in reverse.get(queue.popleft(), ()):
            if importer not in reached:
                reached.add(importer)
                queue.append(importer)
    files = {f for f, modules in inputs.graph.tests.items() if reached & modules}
    return {t for t in known_tests if t.split("::", 1)[0] in files}


def _functions_reading_data(inputs: Inputs, by_function: dict[str, list[str]]) -> set[str]:
    """Every function of a mutated module that names a changed non-Python source-tree file."""
    roots = {f.split("/", 1)[0] for f in inputs.mutated_files}
    names = [
        path.rsplit("/", 1)[-1]
        for _status, path in inputs.changes
        if not path.endswith((".py", ".md")) and path.split("/", 1)[0] in roots
    ]
    modules = {
        _module_of(f)
        for f in inputs.mutated_files
        if any(n in inputs.sources.get(f, "") for n in names)
    }
    return {fn for fn in by_function if split_mangled(fn)[0] in modules}


# ── mutmut's file formats ───────────────────────────────────────────────────────────────────────


def split_mangled(mangled: str) -> tuple[str, str]:
    """'pkg.mod.x_load' -> ('pkg.mod', 'x_load'); class methods are 'pkg.mod.xǁClassǁmethod'."""
    cut = max(mangled.rfind(".x_"), mangled.rfind(".xǁ"))
    return (mangled[:cut], mangled[cut + 1 :]) if cut >= 0 else (mangled, "")


def reset_verdicts(meta: dict, mangled_functions: set[str]) -> int:
    """Empty the cached verdict of each mutant of *mangled_functions*; mutmut re-tests those."""
    codes = meta.get("exit_code_by_key", {})
    prefixes = tuple(f"{fn}__mutmut_" for fn in mangled_functions)
    count = 0
    for key in codes:
        if key.startswith(prefixes) and codes[key] is not None:
            codes[key] = None
            count += 1
    return count


def drop_tests(stats: dict, tests: set[str]) -> None:
    """Forget these tests: with no duration on record, mutmut measures them again as new."""
    for test in tests:
        stats.get("duration_by_test", {}).pop(test, None)
    by_function = stats.get("tests_by_mangled_function_name", {})
    for function, covering in by_function.items():
        by_function[function] = [t for t in covering if t not in tests]


def renamed_stats(stats: dict, renames: tuple[tuple[str, str], ...]) -> dict:
    """*stats* with the tests of each moved test file under its new path (*stats* itself when
    nothing moved; otherwise a copy, and the argument is left alone).

    A moved test file is the same tests: what they covered and how long they took still holds, so
    the cache follows them instead of forgetting them and measuring them as new. The planner
    calls this to decide, and ``apply`` to rewrite the file on disk: the same mapping, one function.
    """
    if not renames:
        return stats
    moves = dict(renames)

    def rename(test: str) -> str:
        file, separator, rest = test.partition("::")
        return f"{moves[file]}{separator}{rest}" if file in moves else test

    renamed = dict(stats)
    renamed["duration_by_test"] = {
        rename(t): d for t, d in stats.get("duration_by_test", {}).items()
    }
    renamed["tests_by_mangled_function_name"] = {
        fn: [rename(t) for t in tests]
        for fn, tests in stats.get("tests_by_mangled_function_name", {}).items()
    }
    return renamed


def selection_fingerprint(values: list[str] | tuple[str, ...]) -> str:
    """mutmut 3.8's fingerprint of the test-selection arguments (configuration.py, `_hash`)."""
    return hashlib.sha256(repr(tuple(values)).encode()).hexdigest()[:12]


# ── gathering the inputs ────────────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout if out.returncode == 0 else ""


def diff_rows(root: Path, base: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The rows of ``git diff --name-status -M``: (status, paths), read once for everyone."""
    rows = []
    for line in _git(root, "diff", "--name-status", "-M", base, "--").splitlines():
        status, *paths = line.split("\t")
        rows.append((status, tuple(paths)))
    return tuple(rows)


def read_changes(
    root: Path, base: str, rows: tuple[tuple[str, tuple[str, ...]], ...] | None = None
) -> tuple[tuple[str, str], ...]:
    changes = []
    for status, paths in diff_rows(root, base) if rows is None else rows:
        if status.startswith("R") and len(paths) == _RENAME_PATHS:
            changes += [("D", paths[0]), ("A", paths[1])]
        elif paths:
            changes.append((status[0], paths[0]))
    # a file not yet added to git is a change too (locally; in CI everything is committed)
    seen = {path for _status, path in changes}
    changes += [
        ("A", p)
        for p in _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
        if p not in seen
    ]
    return tuple(changes)


def pure_renames(
    rows: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[tuple[str, str], ...]:
    """(old, new) of each file git sees renamed with its content unchanged (a 100% rename)."""
    return tuple(
        (paths[0], paths[1])
        for status, paths in rows
        if status == "R100" and len(paths) == _RENAME_PATHS
    )


def followed_renames(
    renames: tuple[tuple[str, str], ...], selection: Selection
) -> tuple[tuple[str, str], ...]:
    """The moves of test files that stay in the mutation selection."""
    return tuple(
        (old, new) for old, new in renames if old in selection.before and new in selection.now
    )


def without_renames(
    changes: tuple[tuple[str, str], ...], renames: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    """*changes* minus the deletion and the addition a followed rename shows up as."""
    moved = {path for pair in renames for path in pair}
    return tuple(change for change in changes if change[1] not in moved)


def _pyproject(text: str) -> dict:
    if tomllib is None or not text:
        return {}
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}


def _lookup(doc: dict, dotted: str):
    for part in dotted.split("."):
        if not isinstance(doc, dict) or part not in doc:
            return None
        doc = doc[part]
    return doc


def changed_sections(old: dict, new: dict) -> tuple[str, ...]:
    watched = (*FULL_RERUN_SECTIONS, _SELECTION_KEY)
    return tuple(s for s in watched if _lookup(old, s) != _lookup(new, s))


def selection_files(doc: dict) -> tuple[str, ...]:
    args = _lookup(doc, _SELECTION_KEY) or []
    return tuple(a for a in args if isinstance(a, str) and a.endswith(".py"))


def _repo_python_files(root: Path) -> list[str]:
    listed = _git(root, "ls-files", "*.py").splitlines()
    return [p for p in listed if not p.startswith(("mutants/", ".venv/"))]


def _resolve(module: str | None, level: int, current: str, is_package: bool) -> str | None:
    if level == 0:
        return module
    parts = current.split(".")
    base = parts if is_package else parts[:-1]
    base = base[: len(base) - (level - 1)] if level > 1 else base
    return ".".join([*base, module] if module else base) or None


def import_graph(root: Path, files: list[str]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """module -> repo modules it imports, and test file -> repo modules it imports."""
    modules = {_module_of(f): f for f in files}
    graph: dict[str, set[str]] = {}
    by_file: dict[str, set[str]] = {}
    for module, rel in modules.items():
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        package = rel.endswith("__init__.py")
        found: set[str] = set()
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = _resolve(node.module, node.level, module, package)
                if base:
                    names = [base, *(f"{base}.{a.name}" for a in node.names)]
            found.update(n for n in names if n in modules)
        graph[module] = found
        by_file[rel] = found
    return graph, by_file


def _mutation_settings(root: Path) -> dict:
    """The repo's settings for the mutation gate; unreadable means none, so no policy is relaxed."""
    try:
        return load_settings(root)[MUTATION_GATE]
    except Exception:  # noqa: BLE001  # a config that cannot be read must not weaken the plan
        return {}


def _touched_functions(
    root: Path, base: str, mutated: frozenset[str]
) -> frozenset[tuple[str, str]] | None:
    """The mutated functions the diff touches, as (module, qualified name); None if git cannot say.

    The same functions the ratchet will judge, found the same way.
    """
    if not _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").strip():
        return (
            None  # git reports its errors as "nothing changed", which would narrow everything away
        )
    try:
        ranges: dict[str, tuple[int, int]] = {}
        for rel in sorted(mutated):
            ranges.update(function_ranges(root, rel))
        names = touched_names(root, base, ranges)
    except Exception:  # noqa: BLE001  # unknown means no narrowing, never a wrong plan
        return None
    return frozenset((_module_of(rel), qual) for rel, qual in (n.split("::", 1) for n in names))


def collect_inputs(root: Path, base: str, mutants_dir: Path) -> tuple[Inputs, list[str], list[str]]:
    new_doc = _pyproject(
        (root / "pyproject.toml").read_text() if (root / "pyproject.toml").exists() else ""
    )
    old_doc = _pyproject(_git(root, "show", f"{base}:pyproject.toml"))
    mutate = _lookup(new_doc, "tool.mutmut.only_mutate") or []
    files = _repo_python_files(root)
    mutated = frozenset(f for f in files if any(fnmatch.fnmatch(f, p) for p in mutate))
    selection = selection_files(new_doc)
    wanted = {*selection, *selection_files(old_doc), *mutated}
    sources = {}
    for rel in wanted:
        try:
            sources[rel] = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    stats_path = mutants_dir / "mutmut-stats.json"
    try:
        stats = json.loads(stats_path.read_text())
    except (OSError, json.JSONDecodeError):
        stats = None
    graph, by_file = import_graph(root, files)
    settings = _mutation_settings(root)
    chosen = Selection(selection, selection_files(old_doc) if old_doc else selection)
    rows = diff_rows(root, base)
    renames = followed_renames(pure_renames(rows), chosen)
    inputs = Inputs(
        keep_on_dependency_change=settings.get("dependency-change") == "keep",
        defer_unmutated_change=settings.get("unmutated-change") == "defer",
        changes=without_renames(read_changes(root, base, rows), renames),
        renamed=renames,
        mutated_files=mutated,
        selection=chosen,
        stats=stats,
        sources=sources,
        changed_sections=changed_sections(old_doc, new_doc) if old_doc else (),
        graph=ImportGraph(graph, {f: by_file.get(f, set()) for f in selection}),
        touched=_touched_functions(root, base, mutated),
    )
    return (
        inputs,
        list(_lookup(old_doc, _SELECTION_KEY) or []),
        list(_lookup(new_doc, _SELECTION_KEY) or []),
    )


# ── applying a plan ─────────────────────────────────────────────────────────────────────────────


class CacheFormatError(Exception):
    """The cache does not look like the mutmut version this script was written against."""


def resign_selection(
    stats: dict, old_args: list[str], new_args: list[str], built_args: list[str] | None = None
) -> None:
    """Make mutmut see the test selection as unchanged when the files it adds have simply not been
    measured yet; it would otherwise reset every verdict.

    The cache was built from some earlier selection, which is not necessarily the base ref's.
    Three candidates are tried: the base ref's, the current one without the files the cache has no
    test from, and the selection at the commit the cache was built from (a cache restored from an
    older main predates any selection edit merged since). The stored fingerprint must match one of
    them exactly, or the format is not what this script knows and the caller runs in full.
    """
    fingerprint = stats.setdefault("config_fingerprint", {})
    stored = fingerprint.get("test_selection")
    wanted = selection_fingerprint(new_args)
    if stored == wanted:
        return
    measured = {test.split("::", 1)[0] for test in stats.get("duration_by_test", {})}
    unmeasured = {a for a in new_args if a.endswith(".py") and a not in measured}
    candidates = (old_args, [a for a in new_args if a not in unmeasured], built_args or [])
    if not any(selection_fingerprint(candidate) == stored for candidate in candidates):
        raise CacheFormatError("the stored test-selection fingerprint matches no known selection")
    fingerprint["test_selection"] = wanted


def apply(
    plan_: Plan,
    mutants_dir: Path,
    old_args: list[str],
    new_args: list[str],
    built_args: list[str] | None = None,
) -> int:
    """Drop the planned verdicts and stale tests; returns how many mutant verdicts were dropped."""
    stats_path = mutants_dir / "mutmut-stats.json"
    stats = json.loads(stats_path.read_text())
    stats = renamed_stats(stats, plan_.renamed)
    resign_selection(stats, old_args, new_args, built_args)
    drop_tests(stats, set(plan_.stale_tests))
    stats_path.write_text(json.dumps(stats, indent=4))

    by_module: dict[str, set[str]] = {}
    for function in plan_.reset_functions:
        module, _ = split_mangled(function)
        by_module.setdefault(module, set()).add(function)
    dropped = 0
    for module, functions in by_module.items():
        meta_path = mutants_dir / (module.replace(".", "/") + ".py.meta")
        if not meta_path.exists():
            meta_path = mutants_dir / (module.replace(".", "/") + "/__init__.py.meta")
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        dropped += reset_verdicts(meta, functions)
        meta_path.write_text(json.dumps(meta, indent=4))
    return dropped


def built_selection(root: Path, mutants_dir: Path) -> list[str]:
    """The test selection at the commit the cache was built from; empty when it cannot be told."""
    try:
        commit = json.loads((mutants_dir / "mutmut-stats.json").read_text())["git_commit"]
        doc = _pyproject(_git(root, "show", f"{commit}:pyproject.toml"))
    except (OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError):
        return []
    return list(_lookup(doc, _SELECTION_KEY) or [])


def _mutmut_run(root: Path) -> int:
    return subprocess.run([sys.executable, "-m", "mutmut", "run"], cwd=root, check=False).returncode


def _measured_now(inputs: Inputs, files: tuple[str, ...]) -> Inputs:
    """The second pass's view of the diff: the test files whose coverage has just been measured.

    Every other change was handled by the first pass, whose verdicts are fresh; deciding again from
    the whole diff would drop them a second time and run the same mutants twice.
    """
    return replace(inputs, changes=tuple(("A", f) for f in files))


def _prepare(
    root: Path, base: str, mutants_dir: Path, attempt: int, measured: tuple[str, ...] = ()
) -> Plan:
    """Decide, then leave the cache ready for a plain `mutmut run`."""
    with step("mutation plan: read the repo and decide"):
        inputs, old_args, new_args = collect_inputs(root, base, mutants_dir)
        decided = plan(_measured_now(inputs, measured) if attempt > 1 and measured else inputs)
    print(summary(decided))
    with step(f"mutation plan: prepare the cache ({decided.mode})"):
        if decided.mode == "full" and mutants_dir.exists():
            shutil.rmtree(mutants_dir)
        elif decided.mode == "incremental":
            built = built_selection(root, mutants_dir)
            dropped = apply(decided, mutants_dir, old_args, new_args, built)
            print(f"dropped {dropped} cached verdict(s)")
    return decided


def run(root: Path, base: str, mutants_dir: Path) -> int:
    """Plan, drop, `mutmut run`; once more when new tests had to be measured first.

    Anything unexpected in planning falls back to the campaign mutmut would have run anyway: a
    wrong plan must cost time, never a wrong verdict.
    """
    measured: tuple[str, ...] = ()
    for attempt in range(1, _PASSES + 1):
        try:
            decided = _prepare(root, base, mutants_dir, attempt, measured)
        except Exception as exc:  # noqa: BLE001 - any failure here means "run in full"
            print(f"mutation plan failed ({exc!r}): running in full", file=sys.stderr)
            shutil.rmtree(mutants_dir, ignore_errors=True)
            return _mutmut_run(root)
        with step(f"mutmut run (pass {attempt})"):
            code = _mutmut_run(root)
        if code != 0 or not decided.needs_second_pass or attempt == _PASSES:
            return code
        measured = decided.selection_added
    return 0


def summary(decided: Plan) -> str:
    lines = [f"mutation plan: {decided.mode}"]
    lines += [f"  - {reason}" for reason in decided.reasons]
    if decided.mode == "incremental":
        lines.append(
            f"  {len(decided.reset_functions)} function(s) to re-test, "
            f"{len(decided.stale_tests)} test(s) to re-measure"
        )
        if decided.selection_added:
            lines.append(f"  new test file(s): {', '.join(decided.selection_added)}")
        if decided.renamed:
            lines.append(f"  {len(decided.renamed)} test file(s) moved: their verdicts follow them")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("plan", "apply", "run"))
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--path", default=".")
    parser.add_argument("--mutants-dir", default="mutants")
    parser.add_argument("--json", action="store_true", help="plan: print the plan as JSON")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    mutants_dir = root / args.mutants_dir
    if args.command == "run":
        return run(root, args.base, mutants_dir)
    inputs, old_args, new_args = collect_inputs(root, args.base, mutants_dir)
    decided = plan(inputs)
    if args.command == "plan":
        if args.json:
            print(json.dumps(decided.__dict__, indent=2))
        else:
            print(summary(decided))
        return 0
    print(summary(decided))
    if decided.mode == "incremental":
        built = built_selection(root, mutants_dir)
        print(f"dropped {apply(decided, mutants_dir, old_args, new_args, built)} cached verdict(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
