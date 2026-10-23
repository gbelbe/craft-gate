"""The shared git/AST helpers, behaviourally, against a real throwaway repository."""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path

import astfuncs
import gitdiff
import pytest

MOVED = "pkg/f.py"


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp: str, content: str) -> Path:
    repo = Path(tmp)
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    (repo / "f.py").write_text(content)
    _run(repo, "add", ".")
    _run(repo, "commit", "-q", "-m", "base")
    return repo


def _commit(repo: Path, message: str) -> None:
    _run(repo, "commit", "-q", "-a", "--allow-empty", "-m", message)


def test_changed_lines_reports_modified_added_and_deleted_anchor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "a\nb\nc\nd\n")
        (repo / "f.py").write_text("a\nB\nc\nd\ne\n")
        assert gitdiff.changed_lines("HEAD", repo, "f.py") == {2, 5}
        (repo / "f.py").write_text("a\nb\nd\n")  # "c" deleted: anchor line still counts
        assert gitdiff.changed_lines("HEAD", repo, "f.py") == {2}


def test_changed_lines_is_empty_without_a_diff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "a\n")
        assert gitdiff.changed_lines("HEAD", repo, "f.py") == set()


def test_touched_names_selects_only_functions_overlapping_the_diff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "def a():\n    return 1\n\n\ndef b():\n    return 2\n")
        (repo / "f.py").write_text("def a():\n    return 1\n\n\ndef b():\n    return 3\n")
        ranges = {"f.py::a": (1, 2), "f.py::b": (5, 6)}
        assert gitdiff.touched_names(repo, "HEAD", ranges) == {"f.py::b"}
        assert gitdiff.touched_names(repo, "HEAD", {"f.py::a": (1, 2)}) == set()


def test_has_tidy_exempt_only_matches_a_trailer_line_in_range() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "a\n")
        (repo / "f.py").write_text("b\n")
        _commit(repo, "feat: x\n\nTidy-Exempt: nothing applies")
        assert gitdiff.has_tidy_exempt("HEAD~1", cwd=repo)
        assert not gitdiff.has_tidy_exempt("HEAD", cwd=repo)  # empty range
        (repo / "f.py").write_text("c\n")
        _commit(repo, "feat: mentions Tidy-Exempt: mid-line only")
        assert not gitdiff.has_tidy_exempt("HEAD~1", cwd=repo)


def test_git_aborts_with_stderr_on_failure_unless_unchecked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "a\n")
        assert gitdiff.git(["rev-parse", "nope"], cwd=repo, check=False) == "nope\n"
        try:
            gitdiff.git(["rev-parse", "--verify", "nope"], cwd=repo)
        except SystemExit as exc:
            assert "git rev-parse --verify nope failed" in str(exc)
        else:
            raise AssertionError("expected SystemExit")


def test_walk_functions_qualifies_methods_and_nested_functions() -> None:
    tree = ast.parse(
        "def f():\n    def g(): ...\n\nclass C:\n    def m(self): ...\n    async def n(self): ...\n"
    )
    assert [name for name, _ in astfuncs.walk_functions(tree, [])] == [
        "f",
        "f.g",
        "C.m",
        "C.n",
    ]
    assert astfuncs.qualified([], "x") == "x"
    assert astfuncs.qualified(["A", "B"], "x") == "A.B.x"


def test_base_ref_parser_requires_a_base_and_keeps_the_scripts_own_description() -> None:
    parser = gitdiff.base_ref_parser("what this gate does")

    assert parser.parse_args(["--base", "origin/main"]).base == "origin/main"
    assert parser.description == "what this gate does"
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_added_lines_are_the_new_side_of_every_hunk_and_skip_pure_deletions(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)  # noqa: E731
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (repo / "f.py").write_text("a\nb\nc\nd\ne\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    (repo / "f.py").write_text("a\nB\nc\ne\nf\ng\n")  # b rewritten, d deleted, f and g added
    git("commit", "-qam", "change")

    assert gitdiff.added_lines(base, "HEAD", repo, ("f.py",)) == {2, 5, 6}


def test_renamed_files_maps_each_old_path_to_its_new_one_and_ignores_other_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "def a():\n    return 1\n")
        (repo / "g.py").write_text("x = 1\n")
        _run(repo, "add", ".")
        _commit(repo, "second file")
        (repo / "pkg").mkdir()
        _run(repo, "mv", "f.py", MOVED)
        (repo / "g.py").write_text("x = 2\n")
        _run(repo, "add", "-A")
        _commit(repo, "move one, edit the other")

        assert gitdiff.renamed_files("HEAD~1", repo) == {"f.py": MOVED}


def test_a_file_that_only_moved_has_no_changed_lines_when_its_old_path_is_given() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "a\nb\n")
        (repo / "pkg").mkdir()
        _run(repo, "mv", "f.py", MOVED)
        _run(repo, "add", "-A")
        _commit(repo, "move")

        assert gitdiff.changed_lines("HEAD~1", repo, MOVED, "f.py") == set()
        assert gitdiff.changed_lines("HEAD~1", repo, MOVED) == {1, 2}


def test_a_line_added_while_the_file_moves_is_the_only_one_changed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repo(tmp, "a\nb\nc\nd\n")
        (repo / "pkg").mkdir()
        _run(repo, "mv", "f.py", MOVED)
        (repo / "pkg" / "f.py").write_text("a\nb\nc\nd\ne\n")
        _run(repo, "add", "-A")
        _commit(repo, "move and extend")

        assert gitdiff.changed_lines("HEAD~1", repo, MOVED, "f.py") == {5}
