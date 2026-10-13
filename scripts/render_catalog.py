#!/usr/bin/env python3
"""Regenerate what catalog.yaml determines in the docs: tables and counts.

catalog.yaml is the single thing a contributor edits (see CONTRIBUTING.md).
This script renders its `tidying` and `smell-fix` entries into markdown
tables and writes them back between sentinel comments in CRAFTSMANSHIP.md.
Everything else in that file — the procedure, the new-code principles, the
legacy-code workflow — is hand-written prose and untouched; only content
between `<!-- BEGIN GENERATED: ... -->` / `<!-- END GENERATED: ... -->` is
replaced. `principle` and `workflow` entries aren't tabular (they're
narrative sections that don't reduce to one row per entry without losing
nuance), so they stay hand-edited in both files — see CONTRIBUTING.md.

Counts derived from the catalog (how many entries, how many craftCov can
detect) are kept in step the same way, so no prose or badge can go stale:
`<!-- fact:NAME -->value<!-- /fact -->` in CRAFTSMANSHIP.md, and the
README's entry-count badge.

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
README_PATH = ROOT / "README.md"

FACT_MARKER = re.compile(r"(<!-- fact:(\w+) -->)(.*?)(<!-- /fact -->)")
ENTRIES_BADGE = re.compile(r"(img\.shields\.io/badge/catalog-)\d+(_entries)")

# tag -> (kind, table header)
TABLES = {
    "tidying": (
        "tidying",
        "| Code | id | Name | Smell / when to reach for it | What it does |\n|---|---|---|---|---|",
    ),
    "smell-fix": (
        "smell-fix",
        (
            "| Code | id | Name (smell) | Smell / when to reach for it | What it does |\n"
            "|---|---|---|---|---|"
        ),
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
        "<!-- Generated from catalog.yaml by scripts/render_catalog.py — don't\n"
        "     hand-edit this table; edit catalog.yaml and run that script instead.\n"
        "     See CONTRIBUTING.md. -->"
    )
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(
            f"✗ sentinel '{tag}' not found in {DOC_PATH.name} — did someone remove it?"
        )
    return pattern.sub(f"{begin}\n{note}\n{replacement}\n{end}", text)


def catalog_facts(catalog: list[dict]) -> dict[str, int]:
    """Counts that prose and badges quote; the catalog is their only source."""
    return {
        "entries": len(catalog),
        "detectable": sum(1 for e in catalog if e.get("detectors")),
    }


def fill_facts(text: str, facts: dict[str, int]) -> str:
    """Rewrite every `<!-- fact:NAME -->…<!-- /fact -->` span to *facts*[NAME]."""

    def fill(m: re.Match) -> str:
        name = m.group(2)
        if name not in facts:
            raise SystemExit(f"✗ unknown fact '{name}' in {DOC_PATH.name} (known: {sorted(facts)})")
        return f"{m.group(1)}{facts[name]}{m.group(4)}"

    return FACT_MARKER.sub(fill, text)


def fill_badge(text: str, facts: dict[str, int]) -> str:
    return ENTRIES_BADGE.sub(rf"\g<1>{facts['entries']}\g<2>", text)


def render_doc(doc: str, catalog: list[dict]) -> str:
    """CRAFTSMANSHIP.md with its generated tables and counts brought up to date."""
    for tag, (kind, header) in TABLES.items():
        entries = [e for e in catalog if e["kind"] == kind]
        doc = replace_between(doc, tag, render_table(entries, header))
    return fill_facts(doc, catalog_facts(catalog))


def render_readme(readme: str, catalog: list[dict]) -> str:
    return fill_badge(readme, catalog_facts(catalog))


def main() -> int:
    check = "--check" in sys.argv
    catalog = yaml.safe_load(CATALOG_PATH.read_text())
    renderers = {DOC_PATH: render_doc, README_PATH: render_readme}
    rendered = {path: fn(path.read_text(), catalog) for path, fn in renderers.items()}
    stale = [path for path, text in rendered.items() if text != path.read_text()]

    if not stale:
        print(f"✓ {', '.join(p.name for p in renderers)} already match {CATALOG_PATH.name}")
        return 0

    if check:
        names = ", ".join(p.name for p in stale)
        print(f"✗ {names} out of date with {CATALOG_PATH.name} — run:")
        print("    python3 scripts/render_catalog.py")
        return 1

    for path in stale:
        path.write_text(rendered[path])
    print(f"✓ regenerated {', '.join(p.name for p in stale)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
