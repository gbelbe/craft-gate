#!/usr/bin/env python3
"""Regenerate CRAFTSMANSHIP.md's two catalog tables from catalog.yaml.

catalog.yaml is the single thing a contributor edits (see CONTRIBUTING.md).
This script renders its `tidying` and `smell-fix` entries into markdown
tables and writes them back between sentinel comments in CRAFTSMANSHIP.md.
Everything else in that file — the procedure, the new-code principles, the
legacy-code workflow — is hand-written prose and untouched; only content
between `<!-- BEGIN GENERATED: ... -->` / `<!-- END GENERATED: ... -->` is
replaced. `principle` and `workflow` entries aren't tabular (they're
narrative sections that don't reduce to one row per entry without losing
nuance), so they stay hand-edited in both files — see CONTRIBUTING.md.

Usage:
    python3 scripts/render_catalog.py            # regenerate in place
    python3 scripts/render_catalog.py --check     # exit 1 if the file would
                                                   # change (for CI)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog.yaml"
DOC_PATH = ROOT / "CRAFTSMANSHIP.md"

# tag -> (kind, table header)
TABLES = {
    "tidying": (
        "tidying",
        "| Code | id | Name | Smell / when to reach for it | What it does |\n|---|---|---|---|---|",
    ),
    "smell-fix": (
        "smell-fix",
        "| Code | id | Name (smell) | Smell / when to reach for it | What it does |\n"
        "|---|---|---|---|---|",
    ),
}


def render_table(entries: list[dict], header: str) -> str:
    lines = [header]
    for e in entries:
        code = e.get("code", "")
        lines.append(f"| {code} | `{e['id']}` | {e['name']} | {e['smell']} | {e['action']} |")
    return "\n".join(lines)


def replace_between(text: str, tag: str, replacement: str) -> str:
    begin = f"<!-- BEGIN GENERATED: {tag} -->"
    end = f"<!-- END GENERATED: {tag} -->"
    note = (
        f"<!-- Generated from catalog.yaml by scripts/render_catalog.py — don't\n"
        f"     hand-edit this table; edit catalog.yaml and run that script instead.\n"
        f"     See CONTRIBUTING.md. -->"
    )
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(
            f"✗ sentinel '{tag}' not found in {DOC_PATH.name} — did someone remove it?"
        )
    return pattern.sub(f"{begin}\n{note}\n{replacement}\n{end}", text)


def main() -> int:
    check = "--check" in sys.argv
    catalog = yaml.safe_load(CATALOG_PATH.read_text())
    original = DOC_PATH.read_text()

    rendered = original
    for tag, (kind, header) in TABLES.items():
        entries = [e for e in catalog if e["kind"] == kind]
        rendered = replace_between(rendered, tag, render_table(entries, header))

    if rendered == original:
        print(f"✓ {DOC_PATH.name} already matches {CATALOG_PATH.name}")
        return 0

    if check:
        print(f"✗ {DOC_PATH.name} is out of date with {CATALOG_PATH.name} — run:")
        print(f"    python3 scripts/render_catalog.py")
        return 1

    DOC_PATH.write_text(rendered)
    print(f"✓ regenerated {DOC_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
