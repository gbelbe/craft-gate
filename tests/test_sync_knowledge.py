"""sync_knowledge.py: writes what the code says, leaves prose alone, stubs what is unowned."""

from __future__ import annotations

import check_knowledge as knowledge
import pytest
import sync_knowledge as sync
import yaml
from conftest import ROOT

ALPHA, BETA, BOOT, HUB = "/g/alpha.md", "/g/beta.md", "/g/boot.md", "/g/index.md"
ALPHA_CODE, BETA_CODE = "scripts/alpha.py", "scripts/beta.py"
IMPORTS_LINE = "Imports: [Beta](beta.md)."
INSTALLS_LINE = "Installs: [Alpha](alpha.md), [Beta](beta.md)."
PROSE = "Alpha does the work."
STUB_PAGE = "/unsorted/gamma-py.md"
SCRIPTS, GAMMA, PATH_FLAG = "scripts", "gamma.py", "--path"
IMPORTS, INSTALLS = "imports", "installs"


def page(title: str, code: str, relations: dict | None = None, body: str = "") -> str:
    meta = {"type": "Tool", "title": title, "description": f"{title} does a thing", "code": [code]}
    if relations:
        meta["relations"] = relations
    return f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n# {title}\n\n{body}\n"


@pytest.fixture
def project(tmp_path):
    """alpha imports beta; the installer lists both; each has a page, and a hub links them."""
    (tmp_path / SCRIPTS).mkdir()
    (tmp_path / ALPHA_CODE).write_text("import beta\n")
    (tmp_path / BETA_CODE).write_text("")
    (tmp_path / knowledge.INSTALLER).write_text("scripts/alpha.py\nscripts/beta.py\n")
    (tmp_path / knowledge.DOCS / "g").mkdir(parents=True)
    put(tmp_path, ALPHA, page("Alpha", ALPHA_CODE, body=PROSE))
    put(tmp_path, BETA, page("Beta", BETA_CODE))
    put(tmp_path, BOOT, page("Boot", knowledge.INSTALLER))
    put(tmp_path, HUB, "[a](alpha.md) [b](beta.md) [c](boot.md)\n")
    return tmp_path


def put(project, path: str, text: str) -> None:
    (project / knowledge.DOCS / path.lstrip("/")).write_text(text)


def text(project, path: str) -> str:
    return (project / knowledge.DOCS / path.lstrip("/")).read_text()


def relations(project, path: str) -> dict:
    return yaml.safe_load(text(project, path).split("---\n")[1]).get("relations", {})


def test_an_import_the_code_has_is_added_to_the_frontmatter_and_the_text(project) -> None:
    assert sync.sync(project) == [ALPHA, BOOT]

    assert relations(project, ALPHA) == {IMPORTS: [BETA]}
    assert IMPORTS_LINE in text(project, ALPHA)


def test_an_import_the_code_no_longer_has_is_removed_from_both(project) -> None:
    put(project, BETA, page("Beta", BETA_CODE, {IMPORTS: [ALPHA]}, "Imports: [Alpha](alpha.md)."))

    sync.sync(project)

    assert relations(project, BETA) == {}
    assert "Imports:" not in text(project, BETA)


def test_the_installer_lists_the_files_a_page_installs_and_the_text_says_so(project) -> None:
    sync.sync(project)

    assert relations(project, BOOT) == {INSTALLS: [ALPHA, BETA]}
    assert INSTALLS_LINE in text(project, BOOT)


def test_a_name_that_only_contains_a_listed_path_is_not_installed(project) -> None:
    (project / knowledge.INSTALLER).write_text("scripts/alpha.py\nscripts/beta.py.orig\n")

    sync.sync(project)

    assert relations(project, BOOT) == {INSTALLS: [ALPHA]}


def test_a_directory_is_never_claimed_as_installed(project) -> None:
    (project / SCRIPTS / "pkg").mkdir()
    put(project, "/g/pkg.md", page("Pkg", "scripts/pkg"))
    put(project, HUB, text(project, HUB) + "[p](pkg.md)\n")
    (project / knowledge.INSTALLER).write_text("scripts/alpha.py\nscripts/pkg/\n")

    sync.sync(project)

    assert relations(project, BOOT) == {INSTALLS: [ALPHA]}


def test_hand_written_relations_and_all_prose_are_left_alone(project) -> None:
    put(
        project,
        ALPHA,
        page("Alpha", ALPHA_CODE, {"writes": [BETA]}, f"{PROSE}\n\nWrites: [Beta](beta.md)."),
    )

    sync.sync(project)

    assert relations(project, ALPHA) == {IMPORTS: [BETA], "writes": [BETA]}
    assert f"{PROSE}\n\nWrites: [Beta](beta.md)." in text(project, ALPHA)
    assert IMPORTS_LINE in text(project, ALPHA)


def test_an_unowned_file_gets_a_stub_that_the_checker_refuses_until_it_is_described(
    project,
) -> None:
    (project / SCRIPTS / GAMMA).write_text("")

    sync.sync(project)

    assert relations(project, STUB_PAGE) == {}
    assert "- [gamma-py](gamma-py.md)" in text(project, "/unsorted/index.md")
    assert knowledge.problems_in(project) == [
        f"todo: {STUB_PAGE} still has the placeholder description"
    ]


def test_a_second_stub_is_added_to_the_unsorted_index_without_repeating_the_first(project) -> None:
    (project / SCRIPTS / GAMMA).write_text("")
    sync.sync(project)
    (project / SCRIPTS / "delta.py").write_text("")

    sync.sync(project)

    index = text(project, "/unsorted/index.md")
    assert index.count("- [gamma-py]") == 1
    assert index.count("- [delta-py]") == 1


def test_running_it_again_changes_nothing(project) -> None:
    (project / SCRIPTS / GAMMA).write_text("")
    sync.sync(project)

    assert sync.sync(project) == []


def test_check_lists_what_would_change_and_writes_nothing(project, capsys) -> None:
    before = text(project, ALPHA)

    assert sync.main([PATH_FLAG, str(project), "--check"]) == 1

    assert text(project, ALPHA) == before
    seen = capsys.readouterr()
    assert f"would change {knowledge.DOCS}{ALPHA}" in seen.out
    assert "run: python3 tools/sync_knowledge.py" in seen.err


def test_main_writes_and_exits_zero_then_reports_nothing_to_do(project, capsys) -> None:
    assert sync.main([PATH_FLAG, str(project)]) == 0
    assert f"wrote {knowledge.DOCS}{ALPHA}" in capsys.readouterr().out

    assert sync.main([PATH_FLAG, str(project), "--check"]) == 0
    assert "already in sync" in capsys.readouterr().out


def test_this_repos_bundle_is_in_sync_with_its_code() -> None:
    assert sync.sync(ROOT, write=False) == []
