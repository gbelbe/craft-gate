#!/usr/bin/env python3
"""Run mutmut on the mutants of the lines a diff changed, from a clean slate, and nothing else.

The mutation ratchet judges one thing: that the tests covering the code a change touches kill at
least `[mutation] threshold` percent of the mutants on that code. So this script runs exactly those
mutants. Nothing is kept between runs: it empties `mutants/`, asks mutmut to generate every mutant,
picks those whose mutated line is a line the diff changed, and has `mutmut run` test only them. A
cold run costs mutmut's fixed start-up (generating mutants and measuring which tests cover which
function, a couple of minutes) plus the few mutants chosen; a cache would be faster but could serve
a stale verdict for a function whose tests changed, which is the class of bug this design avoids.

How a mutant is placed on a line: mutmut writes every mutant as a full copy of the function with
one change (`x_foo__mutmut_3` beside `x_foo__mutmut_orig`), so comparing the two bodies line by
line gives the line the mutation changed, and the function's own start line turns that into a
line of the source.

It writes the names it chose to `mutants/mutation-selection.json`; `check_mutation_ratchet.py`
judges exactly those. A file mutmut is not set to mutate (`[tool.mutmut] only_mutate`, else
`source_paths`) is never looked at.

Usage:
    python scripts/mutation_run.py --base origin/main [--path .]
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import difflib
import fnmatch
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import tomllib

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
from check_mutation_ratchet import (  # noqa: E402
    MUTANTS_DIR,
    SELECTION_FILE,
    SELECTION_KEY,
    function_ranges,
)
from gate_timing import step  # noqa: E402
from gitdiff import changed_lines, git  # noqa: E402
from mutmut.mutation.file_mutation import MutatedFile, mutate_file_contents  # noqa: E402

_ORIGINAL = "__mutmut_orig"
_MUTANT = "__mutmut_"


def generate_mutants(rel: str, source: str) -> MutatedFile:
    """Every mutant of *source*, as mutmut would write them, without running any test.

    The one call into mutmut's internals; it needs the repo's configuration, read from the working
    directory. No line is known to be covered or excluded, so nothing is left out.
    """
    return mutate_file_contents(rel, source, covered_lines=None, coverage_excluded_lines=None)


def mutated_files(root: Path) -> list[str]:
    """The repo's Python files mutmut mutates: `only_mutate`, else everything in `source_paths`."""
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    table = config.get("tool", {}).get("mutmut", {})
    tracked = git(["ls-files", "*.py"], cwd=root, check=False).splitlines()
    patterns = table.get("only_mutate")
    if patterns:
        return sorted(f for f in tracked if any(fnmatch.fnmatch(f, p) for p in patterns))
    sources = tuple(f"{p.rstrip('/')}/" for p in table.get("source_paths", []))
    return sorted(f for f in tracked if f.startswith(sources)) if sources else []


def module_of(rel: str) -> str:
    """'pkg/mod.py' -> 'pkg.mod'; 'pkg/__init__.py' -> 'pkg' (how mutmut names its mutants)."""
    dotted = rel[: -len(".py")].replace("/", ".")
    return dotted[: -len(".__init__")] if dotted.endswith(".__init__") else dotted


def qualified(base: str) -> str:
    """mutmut's 'x_load' -> 'load'; 'xǁKlassǁrun' -> 'Klass.run'; any other shape as it is."""
    if base.startswith("xǁ") and base.count("ǁ") == 2:  # noqa: PLR2004  # xǁClassǁmethod
        _marker, klass, method = base.split("ǁ")
        return f"{klass}.{method}"
    return base[2:] if base.startswith("x_") else base


def function_bodies(code: str) -> dict[str, list[str]]:
    """{generated function name: its source lines}, for each original and mutant in the module."""
    lines = code.splitlines()
    return {
        node.name: lines[node.lineno - 1 : node.end_lineno]
        for node in ast.walk(ast.parse(code))
        if isinstance(node, ast.FunctionDef) and _MUTANT in node.name
    }


def differing_offsets(original: list[str], mutant: list[str]) -> set[int]:
    """The offsets, from the `def` line, of the lines the mutant changed.

    The mutant's `def` line is read as the original's: it differs by the function's name alone.
    A replaced or deleted line is its own offset; an inserted line is the line it precedes.
    """
    mutant = [original[0], *mutant[1:]]
    offsets: set[int] = set()
    for tag, start, end, _mutant_start, _mutant_end in difflib.SequenceMatcher(
        None, original, mutant, autojunk=False
    ).get_opcodes():
        if tag in ("replace", "delete"):
            offsets.update(range(start, end))
        elif tag == "insert":
            offsets.add(start)
    return offsets


def mutant_lines(bodies: dict[str, list[str]], name: str, start: int) -> set[int]:
    """The lines of the source that mutant *name* changes, its function starting at line *start*."""
    base = name.rsplit(_MUTANT, 1)[0]
    original, mutant = bodies.get(f"{base}{_ORIGINAL}"), bodies.get(name)
    if original is None or mutant is None:
        return set()
    return {start + offset for offset in differing_offsets(original, mutant)}


@dataclass(frozen=True)
class SourceFile:
    """A mutated file: its path, its source, and the line range of each of its functions."""

    rel: str
    source: str
    ranges: dict[str, tuple[int, int]]


def mutants_on_lines(file: SourceFile, changed: set[int]) -> list[str]:
    """The names (as `mutmut run` takes them) of *file*'s mutants on a line in *changed*.

    Needs the repo's mutmut configuration: run it from the repository root.
    """
    generated = generate_mutants(file.rel, file.source)
    bodies = function_bodies(generated.code)
    module = module_of(file.rel)
    chosen = []
    for name in generated.mutant_names:
        span = file.ranges.get(f"{file.rel}::{qualified(name.rsplit(_MUTANT, 1)[0])}")
        if span is not None and mutant_lines(bodies, name, span[0]) & changed:
            chosen.append(f"{module}.{name}")
    return chosen


def select(root: Path, base: str) -> list[str]:
    """Every mutant, in the mutated files, on a line the diff against *base* changed."""
    names: list[str] = []
    for rel in mutated_files(root):
        changed = changed_lines(base, root, rel)
        if changed:
            source = (root / rel).read_text(encoding="utf-8")
            names += mutants_on_lines(SourceFile(rel, source, function_ranges(root, rel)), changed)
    return names


def write_selection(mutants_dir: Path, names: list[str]) -> None:
    mutants_dir.mkdir(parents=True, exist_ok=True)
    (mutants_dir / SELECTION_FILE).write_text(json.dumps({SELECTION_KEY: names}, indent=2) + "\n")


def run_selected(root: Path, names: list[str]) -> int:
    """Start from an empty `mutants/`, have mutmut test *names*, record them; its exit status."""
    mutants_dir = root / MUTANTS_DIR
    shutil.rmtree(mutants_dir, ignore_errors=True)
    print(f"Mutation run: {len(names)} mutant(s) on changed lines.")
    with step("mutation run: mutmut run"):
        status = subprocess.run(
            [sys.executable, "-m", "mutmut", "run", *names], cwd=root, check=False
        ).returncode
    write_selection(mutants_dir, names)
    return status


def run(root: Path, base: str) -> int:
    """Choose the mutants on the lines changed since *base* and run them; mutmut's exit status."""
    with step("mutation run: choose the mutants on changed lines"), contextlib.chdir(root):
        names = select(
            root, base
        )  # mutmut reads the repo's configuration from the working directory
    if names:
        return run_selected(root, names)
    shutil.rmtree(root / MUTANTS_DIR, ignore_errors=True)
    print("Mutation run: no mutant sits on a changed line of a mutated file; nothing to run.")
    write_selection(root / MUTANTS_DIR, [])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="git ref to compare against")
    parser.add_argument("--path", default=".", help="the repository root")
    args = parser.parse_args(argv)
    return run(Path(args.path).resolve(), args.base)


if __name__ == "__main__":
    raise SystemExit(main())
