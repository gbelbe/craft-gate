"""Git helpers shared by the gate scripts.

Every gate that reasons about "what did this change touch" needs the same three
things: run git, find the lines a diff changed, and see whether a commit range
carries a `Tidy-Exempt:` trailer. They live here once so the gates agree on the
answers — a script copying them would drift the first time one was fixed.

Copied into consuming repos next to the scripts that import it (see bootstrap.sh).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def git(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """stdout of ``git <args>``; with *check*, a non-zero exit aborts with git's stderr."""
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        raise SystemExit(f"✗ git {' '.join(args)} failed:\n{proc.stderr}")
    return proc.stdout


def base_ref_parser(description: str | None) -> argparse.ArgumentParser:
    """An argument parser that already takes the ``--base`` ref every diff-aware gate needs."""
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base", required=True, help="base ref this branch diverged from, e.g. origin/main"
    )
    return parser


def changed_lines(base_ref: str, root: Path, rel_path: str) -> set[int]:
    """Line numbers in *rel_path*'s current working-tree content that this
    change added, modified, or deleted at, versus *base_ref* — via
    `git diff -U0`.

    Zero context means every hunk's "+" side is exactly the lines that
    changed, nothing surrounding. A pure-deletion hunk reports a new-side
    count of 0; its anchor line (the insertion point) is still counted as
    touched, since deleting the last statement in a function is a change
    *to* that function even though nothing was added.
    """
    out = git(["diff", "--no-color", "-U0", base_ref, "--", rel_path], cwd=root, check=False)
    lines: set[int] = set()
    for m in _HUNK_HEADER.finditer(out):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        lines.update(range(start, start + count)) if count else lines.add(start)
    return lines


def touched_names(root: Path, base_ref: str, ranges: dict[str, tuple[int, int]]) -> set[str]:
    """Names from *ranges* (``<relpath>::<qualified name>`` → (lineno, endline))
    whose line range overlaps a line this change touched in that file.

    One `git diff` per file, not per function — cheap enough, and a file
    with no diff at all skips straight past without running git per name.
    """
    by_file: dict[str, list[str]] = {}
    for name in ranges:
        by_file.setdefault(name.split("::", 1)[0], []).append(name)

    touched: set[str] = set()
    for file_rel, names in by_file.items():
        changed = changed_lines(base_ref, root, file_rel)
        if not changed:
            continue
        for name in names:
            start, end = ranges[name]
            if any(start <= line <= end for line in changed):
                touched.add(name)
    return touched


def has_tidy_exempt(base_ref: str, head_ref: str = "HEAD", cwd: Path | None = None) -> bool:
    """True when a `Tidy-Exempt:` trailer appears anywhere in `base_ref..head_ref`.

    One exemption mechanism for every gate this project ships (the tidy
    ratchet, Refactor First, the complexity ratchet, the mutation ratchet),
    not a separate one per script.
    """
    out = git(["log", "--format=%B", f"{base_ref}..{head_ref}"], cwd=cwd, check=False)
    return any(line.startswith("Tidy-Exempt:") for line in out.splitlines())
