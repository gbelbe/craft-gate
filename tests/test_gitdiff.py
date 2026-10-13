"""The shared git/AST helpers, behaviourally, against a real throwaway repository."""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path

import astfuncs
import gitdiff


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
