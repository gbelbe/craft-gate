#!/usr/bin/env python3
"""A change to a file must touch the documentation page that describes it.

`check_knowledge.py` says whether docs/knowledge/ matches the code *now*; `sync_knowledge.py` writes
what the code implies. Neither notices a file whose behaviour changed under a page that still says
the old thing, because the page and the code are each internally fine. This gate closes the gap
the way the other diff-aware gates do: when a change modifies a file that a concept owns (its
`code`), the concept's page must be in the same change.

That is a prompt to look, not proof the text is true: reading the page against the diff is the
reviewer's job (agents/craft-reviewer.md). Files added or removed are already caught by
`check_knowledge.py` (coverage, anchor), so only modified files count here.

A `Docs-Exempt: <reason>` trailer anywhere in the commit range waives it. A repo with no
docs/knowledge/ has nothing to check.

Usage:
    python3 scripts/check_knowledge_touch.py --base <ref> [--head <ref>] [--path .] [--warn-only]

`--warn-only` reports without failing (exit 0), and adds a GitHub annotation in Actions.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
import check_knowledge as ck  # noqa: E402

EXEMPT_TRAILER = "Docs-Exempt:"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


def has_ref(repo: Path, ref: str) -> bool:
    return bool(git(repo, "rev-parse", "--verify", "--quiet", ref).strip())


def modified_files(repo: Path, merge_base: str, head: str) -> set[str]:
    """Repo-relative paths of the files modified (not added, removed or renamed) in the range."""
    out = git(repo, "diff", "--name-only", "--diff-filter=M", merge_base, head)
    return set(out.splitlines())


def exempt(repo: Path, merge_base: str, head: str) -> bool:
    log = git(repo, "log", "--format=%B", f"{merge_base}..{head}")
    return any(line.startswith(EXEMPT_TRAILER) for line in log.splitlines())


def _under(path: str, owner: str) -> bool:
    return path == owner or path.startswith(owner + "/")


def untouched(docs: list[ck.Doc], modified: set[str]) -> list[tuple[str, list[str]]]:
    """(page, modified files it owns) for each page owning one that was not itself modified."""
    owed = []
    for doc in (d for d in docs if d.is_concept):
        page = f"{ck.DOCS}{doc.path}"
        owned = sorted(f for f in modified if any(_under(f, own) for own in doc.code))
        if owned and page not in modified:
            owed.append((page, owned))
    return owed


def report(owed: list[tuple[str, list[str]]], warn_only: bool) -> None:
    mark = "⚠" if warn_only else "✗"
    print(f"{mark} Docs touch: a changed file's page was not changed with it:", file=sys.stderr)
    for page, files in owed:
        print(f"  {page}  (for {', '.join(files)})", file=sys.stderr)
    print(
        "\n  Read the page against your change and update what is no longer true (description,\n"
        "  relations, text; `python3 scripts/sync_knowledge.py` writes the relations), or say why\n"
        f"  nothing needs saying in a {EXEMPT_TRAILER} trailer.",
        file=sys.stderr,
    )
    if warn_only and os.environ.get("GITHUB_ACTIONS") == "true":
        pages = ", ".join(page for page, _ in owed)
        print(f"::warning title=Docs touch::pages not updated with their code: {pages}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", required=True, help="the ref the change branched from")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    parser.add_argument("--warn-only", action="store_true", help="report, but exit 0")
    args = parser.parse_args(argv)
    repo = Path(args.path).resolve()

    if not (repo / ck.DOCS).is_dir():
        return 0
    if not has_ref(repo, args.base):
        print(f"⚠ docs touch: '{args.base}' not found locally — skipping", file=sys.stderr)
        return 0
    merge_base = git(repo, "merge-base", args.base, args.head).strip()
    if exempt(repo, merge_base, args.head):
        print(f"✓ Docs touch: waived by {EXEMPT_TRAILER}")
        return 0
    owed = untouched(ck.load(repo), modified_files(repo, merge_base, args.head))
    if not owed:
        print("✓ Docs touch: OK.")
        return 0
    report(owed, args.warn_only)
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
