"""check_knowledge_touch.py: a modified file owes its page a change, in a real git range."""

from __future__ import annotations

import subprocess
from pathlib import Path

import check_knowledge as knowledge
import check_knowledge_touch as touch
import pytest

BASE, WARN, PATH = "--base", "--warn-only", "--path"
ALPHA_FILE, OTHER_FILE = "scripts/alpha.py", "scripts/other.py"
ALPHA_PAGE = f"{knowledge.DOCS}/g/alpha.md"
OTHER_PAGE = f"{knowledge.DOCS}/g/other.md"
PKG_FILE = "scripts/pkg/mod.py"
EDITED = "x = 2\n"


def page(code: str, text: str = "") -> str:
    return f"---\ntype: Tool\ncode:\n- {code}\n---\n{text}\n"


def run(repo: Path, *args: str) -> None:
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", *identity, *args], cwd=repo, check=True, capture_output=True)


def put(repo: Path, path: str, text: str) -> None:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)


def commit(repo: Path, message: str) -> None:
    run(repo, "add", "-A")
    run(repo, "commit", "-m", message)


@pytest.fixture
def repo(tmp_path):
    """main holds two scripts, a package and a page for each; a `feature` branch is checked out."""
    run(tmp_path, "init", "-b", "main")
    put(tmp_path, ALPHA_FILE, "x = 1\n")
    put(tmp_path, OTHER_FILE, "y = 1\n")
    put(tmp_path, PKG_FILE, "z = 1\n")
    put(tmp_path, ALPHA_PAGE, page(ALPHA_FILE))
    put(tmp_path, OTHER_PAGE, page(OTHER_FILE))
    put(tmp_path, f"{knowledge.DOCS}/g/pkg.md", page("scripts/pkg"))
    commit(tmp_path, "base")
    run(tmp_path, "checkout", "-b", "feature")
    return tmp_path


def edit_alpha(repo: Path, message: str = "change alpha") -> None:
    put(repo, ALPHA_FILE, EDITED)
    commit(repo, message)


def gate(repo: Path, *extra: str) -> int:
    return touch.main([BASE, "main", PATH, str(repo), *extra])


def test_a_modified_file_whose_page_was_not_touched_fails_and_names_both(repo, capsys) -> None:
    edit_alpha(repo)

    assert gate(repo) == 1

    err = capsys.readouterr().err
    assert f"{ALPHA_PAGE}  (for {ALPHA_FILE})" in err
    assert OTHER_PAGE not in err


def test_touching_the_page_in_the_same_range_passes(repo, capsys) -> None:
    put(repo, ALPHA_FILE, EDITED)
    put(repo, ALPHA_PAGE, page(ALPHA_FILE, "now says more"))
    commit(repo, "change alpha and its page")

    assert gate(repo) == 0
    assert "OK" in capsys.readouterr().out


def test_the_page_may_be_touched_in_another_commit_of_the_range(repo) -> None:
    edit_alpha(repo)
    put(repo, ALPHA_PAGE, page(ALPHA_FILE, "now says more"))
    commit(repo, "describe it")

    assert gate(repo) == 0


def test_a_file_inside_an_owned_directory_owes_the_directorys_page(repo, capsys) -> None:
    put(repo, PKG_FILE, "z = 2\n")
    commit(repo, "change pkg")

    assert gate(repo) == 1
    assert f"{knowledge.DOCS}/g/pkg.md  (for {PKG_FILE})" in capsys.readouterr().err


def test_a_file_added_to_an_owned_directory_owes_nothing_here(repo) -> None:
    put(repo, "scripts/pkg/new.py", "")
    commit(repo, "add to pkg")

    assert gate(repo) == 0


def test_a_modified_file_no_page_owns_is_left_to_the_coverage_rule(repo) -> None:
    put(repo, "scripts/free.py", "")
    commit(repo, "add free")
    run(repo, "checkout", "-b", "second")
    put(repo, "scripts/free.py", "changed = True\n")
    commit(repo, "edit free")

    assert touch.main([BASE, "feature", PATH, str(repo)]) == 0


def test_a_docs_exempt_trailer_waives_it(repo, capsys) -> None:
    edit_alpha(repo, "reformat alpha\n\nDocs-Exempt: whitespace only")

    assert gate(repo) == 0
    assert "waived" in capsys.readouterr().out


def test_a_tidy_exempt_trailer_does_not_waive_it(repo) -> None:
    edit_alpha(repo, "change alpha\n\nTidy-Exempt: legacy")

    assert gate(repo) == 1


def test_warn_only_reports_but_exits_zero(repo, capsys) -> None:
    edit_alpha(repo)

    assert gate(repo, WARN) == 0
    assert "⚠ Docs touch" in capsys.readouterr().err


def test_warn_only_adds_a_github_annotation_in_actions(repo, capsys, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    edit_alpha(repo)

    gate(repo, WARN)

    assert f"::warning title=Docs touch::pages not updated with their code: {ALPHA_PAGE}" in (
        capsys.readouterr().out
    )


def test_a_repo_with_no_bundle_has_nothing_to_check(tmp_path, capsys) -> None:
    assert touch.main([BASE, "main", PATH, str(tmp_path)]) == 0
    assert capsys.readouterr().err == ""


def test_a_base_ref_that_is_not_there_is_skipped_with_a_warning(repo, capsys) -> None:
    assert touch.main([BASE, "no-such-ref", PATH, str(repo)]) == 0
    assert "'no-such-ref' not found locally" in capsys.readouterr().err
