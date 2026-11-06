#!/usr/bin/env python3
"""Diff-aware mutation-testing ratchet — kill rate for touched functions only.

The mechanical enforcement CRAFTSMANSHIP.md's "Mutation ratchet" section documents.
It has no catalog entry: this is a test-quality gate, not a design heuristic. Independent of every
other gate: doesn't run mutmut itself (a prior `mutmut run` step must have
already populated `mutants/`, normally cached between CI runs the way
`node_modules` or `.venv` are), just reads its results and a git diff.

Fails when a function this change's diff actually touches has a mutation
score (killed / (killed + survived), mutmut's own definition — see
`mutmut badge`) below --threshold. Not base-vs-head like the complexity
ratchet: mutation testing is too expensive to run twice per PR (it reruns
the whole test suite once per mutant), so this checks touched functions
against a floor on the current tree only. The floor is --threshold, the same
for every touched function, new or old: there is no improvement path, so
touching a function whose tests are weak means bringing them to the threshold.
A genuinely equivalent mutant belongs behind mutmut's own
`# pragma: no mutate` (mutmut's answer to this, same idea as coverage.py's
`# pragma: no cover`) — fix the false positive at its source, not by
lowering this gate's bar.

Reaches into mutmut's internals (`mutmut.utils.format_utils.
orig_function_and_class_names_from_key`) to map a mutant key like
"pkg.mod.x_foo__mutmut_3" back to the function it mutated ("foo"), rather
than mutmut's own per-mutant line-span index (`mutants/<file>.spans`) —
verified against a real run that those spans are lines in the *generated*
mutants file, not the original source, so they can't be intersected with
a `git diff` on the original file directly. This is a real coupling to an
internal, not-obviously-public module; pin mutmut's version range and
re-verify this mapping on any major-version bump.

Usage:
    python scripts/check_mutation_ratchet.py [--base origin/main] [--path .]
        [--mutants-dir mutants] [--threshold 80]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
from astfuncs import walk_functions  # noqa: E402
from gitdiff import touched_names  # noqa: E402

DEFAULT_THRESHOLD = 80.0
SELECTION_FILE = "mutation-selection.json"  # in mutants/: the mutants mutation_run.py chose
SELECTION_KEY = "mutants"  # what the selection file calls the list of chosen mutants
MUTANTS_DIR = "mutants"  # where mutmut keeps its work

# mutmut's own exit-code -> outcome mapping (mutmut.stats.status_by_exit_code,
# mirrored rather than imported: that module pulls in mutmut's full click/UI
# stack on import, for a handful of int literals this ratchet needs).
_KILLED_CODES = {1, 3, 36, -24, 24, 152, 255}  # killed, incl. timeout as a kill
_SURVIVED_CODES = {0}
_NO_TESTS_CODES = {5, 33}


def function_ranges(root: Path, rel_path: str) -> dict[str, tuple[int, int]]:
    """Map ``<rel_path>::<qualified function name>`` -> (lineno, endline)."""
    path = root / rel_path
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return {}
    ranges = {}
    for name, node in walk_functions(tree, []):
        end = getattr(node, "end_lineno", node.lineno) or node.lineno
        ranges[f"{rel_path}::{name}"] = (node.lineno, end)
    return ranges


def qualified_name_from_mutant_key(key: str) -> str | None:
    """ "pkg.mod.x_foo__mutmut_3" -> "foo"; "pkg.xǁMyClassǁmethod__mutmut_1" -> "MyClass.method".

    Returns None for a key this mutmut version's naming convention doesn't
    match — treated as "not touched" by the caller (fails safe: at worst
    under-counts, never blocks a PR over a mutant it can't place).
    """
    try:
        from mutmut.utils.format_utils import orig_function_and_class_names_from_key
    except ImportError:
        return None
    try:
        func, cls = orig_function_and_class_names_from_key(key)
    except (AssertionError, ValueError):
        return None
    return f"{cls}.{func}" if cls else func


def mutant_outcome(exit_code: int | None) -> str:
    if exit_code in _KILLED_CODES:
        return "killed"
    if exit_code in _SURVIVED_CODES:
        return "survived"
    if exit_code in _NO_TESTS_CODES:
        return "no_tests"
    if exit_code is None:
        return "pending"  # a verdict dropped (or never made) and not yet re-tested
    return "other"  # skipped / suspicious / caught-by-typecheck / segfault / not-checked


def _meta_files(mutants_dir: Path):
    """(source path, parsed record) of each file mutmut recorded; a bad record is skipped."""
    for meta_path in sorted(mutants_dir.rglob("*.meta")):
        rel = str(meta_path.relative_to(mutants_dir))[: -len(".meta")]
        try:
            yield rel, json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            continue


def _outcomes(
    mutants_dir: Path, place: Callable[[str, str], str | None]
) -> dict[str, dict[str, int]]:
    """Per function, the outcome counts of the mutants *place* accepts.

    *place* gets a file's path and a mutant's key and answers the qualified name of the function it
    belongs to, or None to leave the mutant out.
    """
    results: dict[str, dict[str, int]] = {}
    for rel, meta in _meta_files(mutants_dir):
        for mutant_key, exit_code in meta.get("exit_code_by_key", {}).items():
            qual = place(rel, mutant_key)
            if qual is not None:
                results.setdefault(f"{rel}::{qual}", _no_outcomes())[mutant_outcome(exit_code)] += 1
    return results


def collect_touched_results(
    mutants_dir: Path, touched_by_file: dict[str, set[str]]
) -> dict[str, dict[str, int]]:
    """touched_by_file: {relpath: {touched qualified names}} -> per-name outcome counts."""

    def place(rel: str, mutant_key: str) -> str | None:
        qual = qualified_name_from_mutant_key(mutant_key)
        return qual if qual in touched_by_file.get(rel, ()) else None

    return _outcomes(mutants_dir, place)


def _no_outcomes() -> dict[str, int]:
    return {"killed": 0, "survived": 0, "no_tests": 0, "other": 0, "pending": 0}


class SelectionError(Exception):
    """The file naming the chosen mutants exists but cannot be read."""


def load_selection(mutants_dir: Path) -> set[str] | None:
    """The mutants mutation_run.py chose; None only when it left no selection (a plain mutmut run).

    A selection that is there but unreadable is an error: judging something else in its place would
    give a different verdict with no word said.
    """
    path = mutants_dir / SELECTION_FILE
    if not path.exists():
        return None
    try:
        return set(json.loads(path.read_text())[SELECTION_KEY])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SelectionError(
            f"{path} is not a mutation selection ({error!r}): run scripts/mutation_run.py again"
        ) from error


def collect_selected_results(mutants_dir: Path, selected: set[str]) -> dict[str, dict[str, int]]:
    """Per function, the outcome counts of the *selected* mutants only."""
    return _outcomes(
        mutants_dir,
        lambda _rel, mutant_key: (
            qualified_name_from_mutant_key(mutant_key) if mutant_key in selected else None
        ),
    )


def find_violations(results: dict[str, dict[str, int]], threshold: float) -> list[str]:
    violations = []
    for name, counts in sorted(results.items()):
        tested = counts["killed"] + counts["survived"]
        if tested == 0:
            if counts["no_tests"]:
                violations.append(
                    f"{name}: {counts['no_tests']} mutant(s) with no covering test — untested code"
                )
            continue
        score = 100.0 * counts["killed"] / tested
        if score < threshold:
            violations.append(
                f"{name}: mutation score {score:.0f}% ({counts['killed']}/{tested} killed, "
                f"< {threshold:.0f}%) — strengthen the test, or mark a genuinely equivalent "
                f"mutant `# pragma: no mutate`"
            )
    return violations


def mutation_score(killed: int, tested: int) -> float:
    """Percent of the tested mutants that were killed."""
    return 100.0 * killed / tested


def _pct(score: float) -> str:
    """A percentage with the decimals it needs and no more: 60 -> '60%', 79.5 -> '79.5%'.

    Whole numbers would hide the difference between a score and a threshold a hair above it.
    """
    return f"{score:.2f}".rstrip("0").rstrip(".") + "%"


def evaluate_results(
    results: dict[str, dict[str, int]], threshold: float = DEFAULT_THRESHOLD
) -> list[str]:
    """Apply the one bar to every touched function: it must score at least *threshold*.

    New or old makes no difference, and nothing is compared with an earlier score or stored. A
    function with a mutant that has no verdict (the run was interrupted, or a test failed to
    collect) is refused too: its score would be a guess.
    """
    violations: list[str] = []
    for name, counts in sorted(results.items()):
        if counts.get("pending"):
            violations.append(
                f"{name}: {counts['pending']} mutant(s) have no verdict "
                f"(the run was interrupted, or a test failed to collect)"
            )
            continue
        tested = counts["killed"] + counts["survived"]
        if not tested:
            if counts["no_tests"]:
                violations.append(f"{name}: no covering tests")
            continue
        score = mutation_score(counts["killed"], tested)
        if score < threshold:
            violations.append(f"{name}: mutation score {_pct(score)}, needs >= {_pct(threshold)}")
    return violations


def group_by_file(names: set[str]) -> dict[str, set[str]]:
    """{'rel::qual', ...} -> {rel: {qual, ...}}."""
    grouped: dict[str, set[str]] = {}
    for full in names:
        rel, qual = full.split("::", 1)
        grouped.setdefault(rel, set()).add(qual)
    return grouped


def _touched_results(root: Path, mutants_dir: Path, base: str) -> dict[str, dict[str, int]] | None:
    """Every mutant of the functions the diff touches (a plain `mutmut run`); None when none."""
    all_ranges: dict[str, tuple[int, int]] = {}
    for rel, _meta in _meta_files(mutants_dir):
        all_ranges.update(function_ranges(root, rel))
    if not all_ranges:
        print("Mutation ratchet: no mutated files with recoverable function ranges.")
        return None
    touched = touched_names(root, base, all_ranges)
    if not touched:
        print("Mutation ratchet: no touched functions with mutation data.")
        return None
    return collect_touched_results(mutants_dir, group_by_file(touched))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="git ref to compare against")
    parser.add_argument("--path", default=".", help="source directory to scan")
    parser.add_argument("--mutants-dir", default=MUTANTS_DIR, help="mutmut's output directory")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    return parser


def _report(violations: list[str], threshold: float) -> int:
    """Say what the ratchet found; the exit status."""
    if violations:
        print(f"Mutation ratchet: {len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"Mutation ratchet: OK (touched functions >= {threshold:.0f}% mutation score).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.path)
    mutants_dir = root / args.mutants_dir
    if not mutants_dir.exists():
        print(f"error: {mutants_dir} not found — run `mutmut run` first.", file=sys.stderr)
        return 2

    try:
        selected = load_selection(mutants_dir)
    except SelectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if selected is not None:
        if not selected:
            print("Mutation ratchet: no mutant sits on a changed line; nothing to judge.")
            return 0
        results = collect_selected_results(mutants_dir, selected)
    else:
        results = _touched_results(root, mutants_dir, args.base)
        if results is None:
            return 0
    return _report(evaluate_results(results, args.threshold), args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
