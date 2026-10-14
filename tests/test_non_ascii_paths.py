"""A file whose name is not ASCII is still seen by every gate; git quotes such names by default."""

from __future__ import annotations

import check_complexity_ratchet as complexity
import check_refactor_first as refactor_first
import gitdiff
import mutation_plan
from craftcov_core.discovery import discover_python_files

NAME = "café.py"
CALM = "def calm(x):\n    return x + 1\n"
MAIN = "main"
BRANCHES = 16


def tangled() -> str:
    body = "".join(f"    if x == {i}:\n        r += {i}\n" for i in range(BRANCHES))
    return f"def tangled(x):\n    r = 0\n{body}    return r\n"


def accented_change(repo) -> None:
    repo.commit("base", other_py=CALM)
    repo.branch("feature")
    repo.commit("add", **{"café_py": tangled()})


def test_git_is_asked_for_names_unquoted(repo) -> None:
    accented_change(repo)

    assert gitdiff.git(["ls-files", "*.py"], cwd=repo.path).splitlines() == [NAME, "other.py"]


def test_the_touched_files_include_the_accented_one(repo) -> None:
    accented_change(repo)

    pairs = gitdiff.touched_python_files(repo.path, repo.sha(MAIN), "HEAD")

    assert pairs == [(NAME, NAME)]


def test_craftcov_discovers_the_accented_file(repo) -> None:
    accented_change(repo)

    assert NAME in discover_python_files(repo.path)


def test_the_complexity_ratchet_sees_the_accented_file(repo, run_main, monkeypatch) -> None:
    accented_change(repo)
    monkeypatch.chdir(repo.path)

    assert run_main(complexity, "--base", MAIN, "--path", ".") == 1


def test_refactor_first_does_not_crash_on_the_accented_file(repo, run_main) -> None:
    accented_change(repo)

    code = run_main(refactor_first, "--base", MAIN, "--path", str(repo.path))

    assert code in (0, 1)  # a verdict, not a FileNotFoundError


def test_the_mutation_plan_reads_the_accented_change(repo) -> None:
    accented_change(repo)

    assert ("A", NAME) in mutation_plan.read_changes(repo.path, MAIN)
