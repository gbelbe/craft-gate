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

QUOTEPATH_OFF = "core.quotepath=false"  # else git prints non-ASCII paths as "caf\303\251.py"
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def git(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """stdout of ``git <args>``; with *check*, a non-zero exit aborts with git's stderr."""
    proc = subprocess.run(
        ["git", "-c", QUOTEPATH_OFF, *args], cwd=cwd, capture_output=True, text=True, check=False
    )
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


def changed_lines(
    base_ref: str, root: Path, rel_path: str, renamed_from: str | None = None
) -> set[int]:
    """Line numbers in *rel_path*'s current working-tree content that this
    change added, modified, or deleted at, versus *base_ref* — via
    `git diff -U0`.

    A file moved from *renamed_from* is compared with what it was there, so a move that
    changes nothing touches nothing; without it the whole file would read as added.

    Zero context means every hunk's "+" side is exactly the lines that
    changed, nothing surrounding. A pure-deletion hunk reports a new-side
    count of 0; its anchor line (the insertion point) is still counted as
    touched, since deleting the last statement in a function is a change
    *to* that function even though nothing was added.
    """
    paths = [rel_path] if renamed_from is None else [renamed_from, rel_path]
    out = git(["diff", "--no-color", "-U0", "-M", base_ref, "--", *paths], cwd=root, check=False)
    lines: set[int] = set()
    for m in _HUNK_HEADER.finditer(out):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        lines.update(range(start, start + count)) if count else lines.add(start)
    return lines


def added_lines(base_ref: str, head_ref: str, root: Path, rel_paths: tuple[str, ...]) -> set[int]:
    """Line numbers, in the content at *head_ref*, of lines added or rewritten since *base_ref*.

    Unlike `changed_lines` this reads two commits, not the working tree, and leaves out a
    pure deletion's anchor line: nothing was written there. *rel_paths* is the file's path
    (both of them for a rename, so git can follow it).
    """
    out = git(
        ["diff", "--no-color", "-U0", "-M", base_ref, head_ref, "--", *rel_paths],
        cwd=root,
        check=False,
    )
    lines: set[int] = set()
    for m in _HUNK_HEADER.finditer(out):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        lines.update(range(start, start + count))
    return lines


def touched_python_files(repo: Path, base_sha: str, head_ref: str) -> list[tuple[str, str]]:
    """(old_rel, new_rel) for every added/copied/modified/renamed .py file
    between base_sha and head_ref — old == new except for a real rename."""
    out = git(
        ["diff", "--name-status", "-M", "--diff-filter=ACMR", base_sha, head_ref, "--", "*.py"],
        cwd=repo,
    )
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            pairs.append((parts[1], parts[2]))
        else:
            pairs.append((parts[1], parts[1]))
    return pairs


def renamed_files(base_ref: str, root: Path) -> dict[str, str]:
    """``{old path: new path}`` for every .py file moved since *base_ref*, relative to *root*.

    Git's own rename detection (``-M``): a file moved with edits is still followed, and one
    moved unchanged is a rename with no hunks. Paths outside *root* are left out.
    """
    out = git(
        ["diff", "--name-status", "-M", "--relative", "--diff-filter=R", base_ref, "--", "*.py"],
        cwd=root,
        check=False,
    )
    moved: dict[str, str] = {}
    for line in out.splitlines():
        status, _tab, paths = line.partition("\t")
        if status.startswith("R"):
            old, _tab, new = paths.partition("\t")
            moved[old] = new
    return moved


def touched_names(
    root: Path,
    base_ref: str,
    ranges: dict[str, tuple[int, int]],
    renamed_from: dict[str, str] | None = None,
) -> set[str]:
    """Names from *ranges* (``<relpath>::<qualified name>`` → (lineno, endline))
    whose line range overlaps a line this change touched in that file.

    *renamed_from* maps a file's new path to the path it moved from, so a file that only
    moved is not taken for a file written from scratch.

    One `git diff` per file, not per function — cheap enough, and a file
    with no diff at all skips straight past without running git per name.
    """
    by_file: dict[str, list[str]] = {}
    for name in ranges:
        by_file.setdefault(name.split("::", 1)[0], []).append(name)

    touched: set[str] = set()
    for file_rel, names in by_file.items():
        changed = changed_lines(base_ref, root, file_rel, (renamed_from or {}).get(file_rel))
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
