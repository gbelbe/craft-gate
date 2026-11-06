"""Choosing the mutants on the lines a diff changed, and running only those.

mutmut writes each mutant as a full copy of its function with one change, so the tests build real
mutmut modules from small sources and ask which mutants a set of changed lines selects.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_SPEC = importlib.util.spec_from_file_location("mutation_run", ROOT / "scripts" / "mutation_run.py")
assert _SPEC and _SPEC.loader
mr = importlib.util.module_from_spec(_SPEC)
sys.modules["mutation_run"] = mr
_SPEC.loader.exec_module(mr)

MODULE_FILE = "pkg/mod.py"
PYPROJECT = "pyproject.toml"
MUTANTS = "mutants"
CHOSEN = "mutants"  # the key of the selection file
SOURCE = '''\
def first(value):
    """A docstring."""
    doubled = value * 2
    return doubled + 1


class Box:
    def size(self, n):
        return n + 1
'''
FIRST_LINES = (2, 3, 4)  # the docstring, `doubled = value * 2`, `return doubled + 1`


def forget_mutmut_configuration(monkeypatch) -> None:
    """mutmut reads the repo's configuration once per process; each test has its own repo."""
    import mutmut.configuration as configuration

    monkeypatch.setattr(configuration, "_config", None)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A directory mutmut can read its configuration from, holding the source above."""
    forget_mutmut_configuration(monkeypatch)
    (tmp_path / "pkg").mkdir()
    (tmp_path / MODULE_FILE).write_text(SOURCE)
    (tmp_path / PYPROJECT).write_text(
        f'[tool.mutmut]\nsource_paths = ["pkg"]\nonly_mutate = ["{MODULE_FILE}"]\n'
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def select(repo: Path, changed: set[int]) -> list[str]:
    ranges = mr.function_ranges(repo, MODULE_FILE)
    return mr.mutants_on_lines(MODULE_FILE, SOURCE, ranges, changed)


# -- the pieces -----------------------------------------------------------------------------


def test_a_module_is_named_the_way_mutmut_names_its_mutants() -> None:
    assert mr.module_of("pkg/mod.py") == "pkg.mod"
    assert mr.module_of("pkg/__init__.py") == "pkg"


def test_a_function_and_a_method_are_named_by_what_they_are() -> None:
    assert mr.qualified("x_load") == "load"
    assert mr.qualified("xǁBoxǁsize") == "Box.size"


def test_a_name_of_a_shape_it_does_not_know_is_left_as_it_is() -> None:
    assert mr.qualified("mystery") == "mystery"


def test_only_the_lines_a_mutant_changed_differ_from_the_original() -> None:
    original = ["def f():", "    a = 1", "    return a"]
    mutant = ["def g():", "    a = 2", "    return a"]

    assert mr.differing_offsets(original, mutant) == {1}


def test_an_inserted_line_counts_as_a_changed_line() -> None:
    original = ["def f():", "    return 1"]
    mutant = ["def g():", "    x = 0", "    return 1"]

    assert mr.differing_offsets(original, mutant) == {1}


# -- choosing the mutants ---------------------------------------------------------------------


def test_a_change_on_one_line_selects_the_mutants_of_that_line_only(repo) -> None:
    on_the_assignment = select(repo, {3})
    everywhere = select(repo, set(range(1, 12)))

    assert on_the_assignment
    assert set(on_the_assignment) < set(everywhere)
    assert all(name.startswith("pkg.mod.x_first__mutmut_") for name in on_the_assignment)


def test_a_line_no_mutant_sits_on_selects_nothing(repo) -> None:
    assert select(repo, {1}) == []  # the def line differs by name alone, not by a mutation


def test_a_change_outside_every_function_selects_nothing(repo) -> None:
    assert select(repo, {5, 6}) == []


def test_a_method_is_selected_by_the_line_inside_it(repo) -> None:
    names = select(repo, {9})

    assert names
    assert all(n.startswith("pkg.mod.xǁBoxǁsize__mutmut_") for n in names)


def test_the_chosen_names_are_the_ones_mutmut_runs(repo) -> None:
    names = select(repo, set(FIRST_LINES))

    assert names == sorted(names, key=lambda n: int(n.rsplit("_", 1)[1])) or names


# -- which files are looked at ----------------------------------------------------------------


def test_the_mutated_files_are_the_tracked_ones_only_mutate_names(repo) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "pkg" / "other.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    assert mr.mutated_files(repo) == [MODULE_FILE]


def test_without_only_mutate_every_tracked_file_under_the_source_paths_is_mutated(repo) -> None:
    (repo / PYPROJECT).write_text('[tool.mutmut]\nsource_paths = ["pkg"]\n')
    (repo / "pkg" / "other.py").write_text("x = 1\n")
    (repo / "elsewhere.py").write_text("y = 2\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    assert mr.mutated_files(repo) == [MODULE_FILE, "pkg/other.py"]


def test_a_file_whose_name_is_not_ascii_is_still_a_mutated_file(repo) -> None:
    (repo / PYPROJECT).write_text('[tool.mutmut]\nonly_mutate = ["café.py"]\n')
    (repo / "café.py").write_text("def f():\n    return 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    assert mr.mutated_files(repo) == ["café.py"]


def test_a_repo_with_no_mutmut_configuration_has_nothing_to_mutate(tmp_path) -> None:
    assert mr.mutated_files(tmp_path) == []


# -- the selection the ratchet reads ---------------------------------------------------------


def test_the_selection_is_written_where_the_ratchet_reads_it(tmp_path) -> None:
    mr.write_selection(tmp_path / MUTANTS, ["pkg.mod.x_first__mutmut_1"])

    written = json.loads((tmp_path / MUTANTS / mr.SELECTION_FILE).read_text())
    assert written == {CHOSEN: ["pkg.mod.x_first__mutmut_1"]}


def test_nothing_to_run_is_said_and_recorded_without_starting_mutmut(repo, capsys) -> None:
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], cwd=repo, check=True)

    status = mr.run(repo, "HEAD")

    assert status == 0
    assert "nothing to run" in capsys.readouterr().out
    assert json.loads((repo / MUTANTS / mr.SELECTION_FILE).read_text()) == {CHOSEN: []}


# -- the whole path, with real mutmut ---------------------------------------------------------

ENGINE = """\
def untouched(value):
    return value - 1


def price(value):
    return value + 1
"""
CHANGED_ENGINE = ENGINE.replace("return value + 1", "return value + 2")
STRONG_TEST = "from pkg.engine import price\n\n\ndef test_price():\n    assert price(1) == 3\n"
WEAK_TEST = "from pkg.engine import price\n\n\ndef test_price():\n    assert price(1)\n"
END_TO_END_CONFIG = (
    "[tool.mutmut]\n"
    'source_paths = ["pkg"]\n'
    'only_mutate = ["pkg/engine.py"]\n'
    'pytest_add_cli_args_test_selection = ["tests"]\n'
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def change_one_line(tmp_path: Path, test_source: str, monkeypatch) -> Path:
    """A repo with `untouched` and `price`, committed; then `price` changed on one line."""
    forget_mutmut_configuration(monkeypatch)
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "engine.py").write_text(ENGINE)
    (repo / "tests" / "test_engine.py").write_text(test_source)
    (repo / PYPROJECT).write_text(END_TO_END_CONFIG)
    _git(repo.parent, "init", "-q", "-b", "main", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    (repo / "pkg" / "engine.py").write_text(CHANGED_ENGINE)
    return repo


def run_and_judge(repo: Path) -> int:
    """Run the changed lines' mutants with real mutmut and judge them; the cwd is put back."""
    ratchet = sys.modules["check_mutation_ratchet"]
    try:
        assert mr.run(repo, "HEAD") == 0
        return ratchet.main(["--base", "HEAD", "--path", str(repo)])
    finally:
        os.chdir(ROOT)


def test_a_strong_test_passes_the_whole_path(tmp_path, monkeypatch) -> None:
    repo = change_one_line(tmp_path, STRONG_TEST, monkeypatch)

    assert run_and_judge(repo) == 0


def test_only_the_mutants_of_the_changed_line_are_run(tmp_path, monkeypatch) -> None:
    repo = change_one_line(tmp_path, STRONG_TEST, monkeypatch)

    run_and_judge(repo)

    chosen = json.loads((repo / MUTANTS / mr.SELECTION_FILE).read_text())[CHOSEN]
    assert chosen
    assert all(".x_price__mutmut_" in name for name in chosen)  # none of `untouched`'s


def test_a_weak_test_fails_the_whole_path(tmp_path, monkeypatch, capsys) -> None:
    repo = change_one_line(tmp_path, WEAK_TEST, monkeypatch)

    assert run_and_judge(repo) == 1
    assert "price" in capsys.readouterr().err
