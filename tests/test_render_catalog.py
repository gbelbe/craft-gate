#!/usr/bin/env python3
"""render_catalog.py's generated counts, behaviourally."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "render_catalog", ROOT / "scripts" / "render_catalog.py"
)
assert _SPEC and _SPEC.loader
render = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(render)

CATALOG = [
    {"id": "a", "kind": "tidying", "detectors": [{"tool": "ruff"}]},
    {"id": "b", "kind": "tidying", "detectors": []},
    {"id": "c", "kind": "smell-fix"},
    {"id": "d", "kind": "principle", "detectors": [{"tool": "dupes"}]},
]


def test_facts_count_entries_and_only_those_with_detectors() -> None:
    assert render.catalog_facts(CATALOG) == {"entries": 4, "detectable": 2}
    assert render.catalog_facts([]) == {"entries": 0, "detectable": 0}


def test_fill_facts_rewrites_each_span_and_leaves_other_numbers_alone() -> None:
    text = "7 of <!-- fact:entries -->1<!-- /fact --> and <!-- fact:detectable -->9<!-- /fact -->."
    out = render.fill_facts(text, {"entries": 4, "detectable": 2})
    assert (
        out
        == "7 of <!-- fact:entries -->4<!-- /fact --> and <!-- fact:detectable -->2<!-- /fact -->."
    )


def test_fill_facts_is_idempotent() -> None:
    once = render.fill_facts("<!-- fact:entries -->0<!-- /fact -->", {"entries": 4})
    assert render.fill_facts(once, {"entries": 4}) == once


def test_fill_facts_refuses_an_unknown_fact_name() -> None:
    try:
        render.fill_facts("<!-- fact:nope -->1<!-- /fact -->", {"entries": 4})
    except SystemExit as exc:
        assert "unknown fact 'nope'" in str(exc)
        assert "entries" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_badge_is_rewritten_and_other_badges_are_untouched() -> None:
    text = (
        "![x](https://img.shields.io/badge/catalog-35_entries-blue) "
        "![y](https://img.shields.io/badge/sources-5_books-grey)"
    )
    out = render.fill_badge(text, {"entries": 41})
    assert "badge/catalog-41_entries-blue" in out
    assert "badge/sources-5_books-grey" in out


def test_render_doc_updates_tables_and_counts_together() -> None:
    doc = (
        "<!-- BEGIN GENERATED: tidying -->\nold\n<!-- END GENERATED: tidying -->\n"
        "<!-- BEGIN GENERATED: smell-fix -->\nold\n<!-- END GENERATED: smell-fix -->\n"
        "<!-- fact:entries -->0<!-- /fact -->"
    )
    catalog = [
        {"id": "a", "code": "CG1", "name": "A", "kind": "tidying", "smell": "s", "action": "x"},
        {"id": "f", "code": "CG2", "name": "F", "kind": "smell-fix", "smell": "t", "action": "y"},
    ]
    out = render.render_doc(doc, catalog)
    assert "| CG1 | `a` | A | s | x |" in out
    assert "| CG2 | `f` | F | t | y |" in out
    assert out.endswith("<!-- fact:entries -->2<!-- /fact -->")
    assert "old" not in out


def test_the_committed_docs_match_the_committed_catalog() -> None:
    catalog = render.yaml.safe_load(render.CATALOG_PATH.read_text())
    doc, readme = render.DOC_PATH.read_text(), render.README_PATH.read_text()
    assert render.render_doc(doc, catalog) == doc
    assert render.render_readme(readme, catalog) == readme
