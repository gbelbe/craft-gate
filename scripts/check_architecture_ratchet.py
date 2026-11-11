#!/usr/bin/env python3
"""Architecture ratchet — a touched module must pay down the breaches it carries.

`architecture.yaml` lists, under `known_violations`, the imports that break the declared layering
today (`importer -> imported`). That list may only shrink, but nothing makes it shrink: a change
can edit a module that owns ten of them and leave all ten. This gate closes that gap, the way
Refactor First does for craftCov findings: when a change touches a `.py` file whose module is the
importer of one or more known violations, the list must hold fewer of that module's entries than
it did where the branch diverged from its base.

One fewer is enough. The point is that every visit to a tangled module leaves it less tangled, not
that a one-line fix pays for the whole module.

A `Tidy-Exempt:` trailer anywhere in the commit range waives it (the same escape hatch the other
gates use, and the same `[exemptions] legacy-debt` switch). Opt-in: a repo with no
`architecture.yaml` at either end of the range has nothing to check.

Usage:
    python3 scripts/check_architecture_ratchet.py --base <ref> [--head <ref>] [--path .]
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
from gate_config import ConfigError, find_root, load_settings, waive_from  # noqa: E402
from gitdiff import base_ref_parser, git, has_tidy_exempt, touched_python_files  # noqa: E402

SOURCE = "architecture.yaml"
KNOWN_KEY = "known_violations"
SOURCE_ROOT_KEY = "source_root"
ARROW = "->"
INIT = "__init__"
ERROR_EXIT = 2


def declaration_at(repo: Path, ref: str) -> dict | None:
    """The parsed `architecture.yaml` as of *ref*, or None when the repo had none then."""
    text = git(["show", f"{ref}:{SOURCE}"], cwd=repo, check=False)
    return (yaml.safe_load(text) or {}) if text.strip() else None


def module_of(path: str, source_root: str) -> str | None:
    """The dotted module a repo-relative `.py` path is, under *source_root*; None if outside it."""
    relative = Path(path)
    try:
        relative = relative.relative_to(source_root)
    except ValueError:
        return None
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == INIT:
        parts.pop()
    return ".".join(parts) or None


def breaches_by_importer(data: dict) -> Counter[str]:
    """How many known violations each importing module owns."""
    importers = (entry.split(ARROW)[0].strip() for entry in data.get(KNOWN_KEY) or [])
    return Counter(importers)


def _owned(data: dict, path: str) -> int:
    module = module_of(path, data.get(SOURCE_ROOT_KEY, "."))
    return breaches_by_importer(data)[module] if module else 0


def unpaid(pairs: list[tuple[str, str]], base: dict, head: dict) -> list[tuple[str, int, int]]:
    """(path, before, after) for each touched file that owned breaches and still owns as many."""
    found = []
    for old, new in pairs:
        before, after = _owned(base, old), _owned(head, new)
        if before and after >= before:
            found.append((new, before, after))
    return found


def report(failures: list[tuple[str, int, int]]) -> None:
    print("✗ Architecture ratchet: a touched module must lose a known violation:", file=sys.stderr)
    for path, before, after in failures:
        print(f"  {path}: {before} listed in {SOURCE}, still {after}", file=sys.stderr)
    print(
        f"\n  Move the code so one of those imports goes away, then delete its line from\n"
        f"  {KNOWN_KEY} (python3 scripts/render_architecture.py --breaches lists what is left).\n"
        "  If this change cannot pay any down, say why in a Tidy-Exempt: trailer.",
        file=sys.stderr,
    )


def exempt(repo: Path, merge_base: str, head: str) -> bool:
    """True when a `Tidy-Exempt:` trailer in the range waives the legacy-debt rules here."""
    settings = load_settings(find_root(repo))
    return waive_from(settings, has_tidy_exempt(merge_base, head, cwd=repo)).legacy_debt


def main() -> int:
    parser = base_ref_parser(__doc__)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    args = parser.parse_args()
    repo = Path(args.path).resolve()

    if not git(["rev-parse", "--verify", "--quiet", args.base], cwd=repo, check=False).strip():
        print(
            f"⚠ architecture ratchet: '{args.base}' not found locally — skipping", file=sys.stderr
        )
        return 0
    merge_base = git(["merge-base", args.base, args.head], cwd=repo).strip()
    base, head = declaration_at(repo, merge_base), declaration_at(repo, args.head)
    if base is None or head is None:
        return 0  # no declaration at one end: nothing was baselined, or nothing is declared
    try:
        waived = exempt(repo, merge_base, args.head)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return ERROR_EXIT
    failures = (
        [] if waived else unpaid(touched_python_files(repo, merge_base, args.head), base, head)
    )
    if failures:
        report(failures)
        return 1
    print("✓ Architecture ratchet: " + ("waived by Tidy-Exempt." if waived else "OK."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
