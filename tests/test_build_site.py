"""build_site.py: what each computed part says, and what it leaves out."""

from __future__ import annotations

from pathlib import Path

import build_site as site
import check_knowledge as ck
import pytest
from check_knowledge import parse

ALPHA, BETA = "/g/alpha.md", "/g/beta.md"
ALPHA_ROOT = Path("/nonexistent")
SCRIPT = "scripts/a.py"


def page_text(code: str | None = None, relations: dict | None = None, body: str = "# A\n\nText.\n"):
    lines = ["---", "type: Tool", "title: A"]
    if code:
        lines += ["code:", f"- {code}"]
    for kind, targets in (relations or {}).items():
        lines += ["relations:", f"  {kind}:", *(f"  - {t}" for t in targets)]
    return "\n".join([*lines, "---", body])


def bundle_of(texts: dict[str, str]) -> site.Bundle:
    pages = {}
    for path, text in texts.items():
        pages[path] = site.Page(parse(text, path), text.split("---\n", 2)[-1])
    edges = [
        site.Edge(kind, path, target)
        for path, page in pages.items()
        for kind, targets in page.doc.relations.items()
        for target in targets
    ]
    return site.Bundle(pages, edges)


def site_of(bundle, root=ALPHA_ROOT, steps=None, defines=()) -> site.Site:
    unit = ck.Unit(1, frozenset(defines), frozenset())
    return site.Site(bundle, root, steps or {}, dict.fromkeys(bundle.pages, unit), ck.FEATURES_DIR)


def many(count: int) -> dict[str, str]:
    return {f"/t/p{n}.md": page_text() for n in range(count)}


def test_a_title_falls_back_to_the_file_name() -> None:
    bundle = bundle_of({ALPHA: "---\ntype: Tool\n---\nx"})

    assert bundle.title(ALPHA) == "alpha"


def test_a_link_is_relative_to_the_page_it_is_written_in() -> None:
    bundle = bundle_of({ALPHA: page_text(), "/t/p.md": page_text()})

    assert bundle.link(ALPHA, "/t/p.md") == "[A](../t/p.md)"


def targets_of(count: int) -> tuple[site.Bundle, str]:
    texts = {ALPHA: page_text(relations={"calls": list(many(count))}), **many(count)}
    bundle = bundle_of(texts)
    return bundle, site.mermaid(bundle, bundle.edges)


def test_up_to_the_cap_each_target_is_drawn_one_by_one() -> None:
    _, drawn = targets_of(site.CAP)

    assert drawn.count("-->|calls|") == site.CAP


def test_beyond_the_cap_the_targets_collapse_into_one_arrow_per_folder() -> None:
    _, drawn = targets_of(site.CAP + 1)

    assert drawn.count("-->|calls|") == 1
    assert f'["{site.CAP + 1} t pages"]' in drawn


def test_the_focused_page_is_highlighted_and_others_are_not() -> None:
    bundle = bundle_of({ALPHA: page_text(relations={"imports": [BETA]}), BETA: page_text()})

    assert f"style g_alpha_md {site.FOCUS_STYLE}" in site.mermaid(bundle, bundle.edges, ALPHA)
    assert "style" not in site.mermaid(bundle, bundle.edges)


def test_a_page_with_no_relation_has_no_table_and_no_diagram() -> None:
    bundle = bundle_of({ALPHA: page_text()})

    assert site.relation_table(bundle, "Depends on", {}, ALPHA) == ""
    assert "Around this page" not in site.render_page(site_of(bundle), ALPHA)


def test_the_relation_lines_of_the_text_are_replaced_by_the_tables() -> None:
    body = "# A\n\nImports: [B](b.md)\nKept.\n"
    bundle = bundle_of({ALPHA: page_text(code=SCRIPT, body=body)})

    text = site.with_header(bundle.pages[ALPHA])

    assert "Imports:" not in text
    assert "Kept." in text
    assert text.startswith("# A\n\n> **Tool** · code: `scripts/a.py`\n")


def test_a_page_without_a_code_anchor_gets_no_header() -> None:
    bundle = bundle_of({ALPHA: page_text()})

    assert site.with_header(bundle.pages[ALPHA]) == "# A\n\nText.\n"


def test_a_page_without_a_title_line_gets_the_header_first() -> None:
    bundle = bundle_of({ALPHA: page_text(code=SCRIPT, body="Just text.\n")})

    assert site.with_header(bundle.pages[ALPHA]).startswith("> **Tool** · code: `scripts/a.py`")


def test_a_script_without_argparse_has_no_usage(tmp_path) -> None:
    (tmp_path / "a.py").write_text("print('hi')\n")

    assert site.usage_of(tmp_path, ("a.py",)) == ""


def test_a_script_whose_help_fails_has_no_usage(tmp_path) -> None:
    (tmp_path / "a.py").write_text("import argparse, sys\nsys.exit(3)\n")

    assert site.usage_of(tmp_path, ("a.py",)) == ""


def test_a_code_anchor_that_is_not_python_has_no_usage(tmp_path) -> None:
    assert site.usage_of(tmp_path, ("templates/x.yml", "missing.py")) == ""


def test_a_feature_named_by_a_steps_file_without_the_feature_file_is_left_out(tmp_path) -> None:
    (tmp_path / ck.FEATURES_DIR).mkdir(parents=True)
    (tmp_path / ck.FEATURES_DIR / "test_a.py").write_text('import a\nscenarios("gone.feature")\n')

    steps = site.steps_by_feature(tmp_path, ck.FEATURES_DIR)

    assert steps == {"gone": frozenset({"a"})}
    assert (
        site.scenarios_of(site_of(bundle_of({ALPHA: page_text()}), tmp_path, steps, {"a"}), ALPHA)
        == ""
    )


def test_a_page_whose_modules_no_feature_imports_has_no_scenarios(tmp_path) -> None:
    bundle = bundle_of({ALPHA: page_text()})

    assert site.scenarios_of(site_of(bundle, tmp_path, {"f": frozenset({"b"})}, {"a"}), ALPHA) == ""


def test_the_system_page_counts_relations_inside_a_folder_and_arrows_between_folders() -> None:
    bundle = bundle_of(
        {
            "/g/index.md": "# Gates\n",
            "/t/index.md": "# Tooling\n",
            ALPHA: page_text(relations={"imports": [BETA, "/t/x.md"]}),
            BETA: page_text(),
            "/t/x.md": page_text(),
        }
    )

    text = site.overview(bundle)

    assert '  g["Gates<br/>2 pages<br/>1 inside"]' in text
    assert '  t["Tooling<br/>1 pages<br/>0 inside"]' in text
    assert "  g -->|imports 1| t" in text
    assert "g -->|imports 1| g" not in text


@pytest.mark.parametrize("path", ["/g/alpha.md", "/x.md"])
def test_the_folder_of_a_path_is_its_first_segment(path: str) -> None:
    assert site.folder_of(path) == path.strip("/").split("/")[0]


def test_main_writes_the_site_and_says_how_many_pages(tmp_path, capsys) -> None:
    (tmp_path / "docs/knowledge").mkdir(parents=True)
    (tmp_path / "docs/knowledge/index.md").write_text("# Home\n")
    out = tmp_path / "site"

    assert site.main(["--path", str(tmp_path), "--out", str(out)]) == 0

    assert "✓ wrote 2 pages" in capsys.readouterr().out
    assert (out / "index.md").read_text() == "# Home\n"
    assert (out / "graph.md").is_file()


def test_a_relation_to_a_missing_page_is_titled_by_its_file_name() -> None:
    assert bundle_of({ALPHA: page_text()}).title("/g/gone.md") == "gone"


def test_a_folder_without_a_hub_or_with_an_empty_one_is_named_by_the_folder() -> None:
    bundle = bundle_of({ALPHA: page_text(), "/h/x.md": page_text(), "/h/index.md": ""})

    assert site.folders(bundle) == {"g": "g", "h": "h"}


def test_a_hub_title_loses_the_heading_marker_and_nothing_else() -> None:
    bundle = bundle_of({ALPHA: page_text(), "/g/index.md": "## #1 Gates\n"})

    assert site.hub_title(bundle, "g") == "#1 Gates"


def test_a_script_whose_help_hangs_has_no_usage_and_says_so(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "a.py").write_text("import argparse, time\ntime.sleep(5)\n")
    monkeypatch.setattr(site, "HELP_TIMEOUT", 0.2)

    assert site.usage_of(tmp_path, ("a.py",)) == ""
    assert "'a.py --help' failed" in capsys.readouterr().err


def test_features_are_read_from_the_folder_the_layout_names(tmp_path) -> None:
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "test_a.py").write_text('import a\nscenarios("x.feature")\n')
    (tmp_path / "spec" / "x.feature").write_text("Feature: x\n")
    steps = site.steps_by_feature(tmp_path, "spec")
    bundle = bundle_of({ALPHA: page_text()})
    one = site.Site(bundle, tmp_path, steps, site_of(bundle, defines={"a"}).units, "spec")

    text = site.scenarios_of(one, ALPHA)

    assert "Feature: x" in text
    assert "`spec/x.feature`" in text
