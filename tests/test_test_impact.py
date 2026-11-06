"""Choosing the test files a change can affect, from what the last full run executed."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
import test_impact as ti
from conftest import record_real_run

MAP_FLAG = "--map"
PATH_FLAG = "--path"
SELECT = "select"
IMPACT_FILE = "impact.json"
EXPECTED = "expected"
PLUS_ONE = "x + 1"
TIMES_TWO = "x * 2"
PLUS_TWO = "x + 2"
README, LOCK, CONFTEST, A_TEST = "README.md", "uv.lock", "tests/conftest.py", "tests/test_a.py"
NOW = datetime(2026, 1, 15, tzinfo=UTC)
SOURCE = "pkg/mod.py"
TEST_F, TEST_G = "tests/test_f.py", "tests/test_g.py"
MODULE = "BASE = 1\n\n\ndef f(x):\n    return x + 1\n\n\ndef g(x):\n    return x * 2\n"
TESTS_F = "from pkg.mod import f\n\n\ndef test_f():\n    assert f(1) == 2\n"
TESTS_G = "from pkg.mod import g\n\n\ndef test_g():\n    assert g(2) == 4\n"
# lines of MODULE: 1 BASE (run at import, in no test), 4-5 f (test_f), 8-9 g (test_g)
EXECUTED = {
    SOURCE: {
        1: [""],
        4: [""],
        5: [f"{TEST_F}::test_f|run"],
        8: [""],
        9: [f"{TEST_G}::test_g|run"],
    }
}


def test_a_context_names_its_test_file_and_outside_a_test_it_names_none():
    assert ti.file_of_context("tests/a/test_x.py::test_y|run") == "tests/a/test_x.py"
    assert ti.file_of_context("tests/a/test_x.py::TestC::test_y|setup") == "tests/a/test_x.py"
    assert ti.file_of_context("") is None
    assert ti.file_of_context("|run") is None


def test_consecutive_lines_become_one_range():
    assert ti.to_ranges([]) == []
    assert ti.to_ranges([7]) == [[7, 7]]
    assert ti.to_ranges([9, 1, 2, 3, 7, 10]) == [[1, 3], [7, 7], [9, 10]]


@pytest.mark.parametrize(
    ("lines", EXPECTED),
    [
        ({2}, False),
        ({3}, True),
        ({5}, True),
        ({6}, False),
        ({1, 6}, False),
        ({1, 4}, True),
        (set(), False),
    ],
)
def test_a_range_covers_its_ends_and_nothing_beyond(lines, expected):
    assert ti.covers([[3, 5]], lines) is expected


@pytest.mark.parametrize(
    ("diff", EXPECTED),
    [
        ("@@ -3 +3 @@\n-a\n+b\n", {3}),
        ("@@ -3,2 +3,2 @@\n", {3, 4}),
        ("@@ -3,0 +4,2 @@\n", {3, 4}),
        ("@@ -3,2 +2,0 @@\n", {3, 4}),
        ("@@ -1 +1 @@\n@@ -9,3 +9 @@\n", {1, 9, 10, 11}),
        ("", set()),
    ],
)
def test_the_old_side_of_a_diff_is_the_lines_it_touches(diff, expected):
    assert ti.old_side_lines(diff) == expected


def test_the_map_keeps_what_each_test_file_ran_and_drops_what_ran_outside_any_test():
    built = ti.build_map(EXECUTED, "abc", NOW)

    assert built["version"] == ti.MAP_VERSION
    assert built[ti.TREE] == "abc"
    assert built["created"] == NOW.isoformat()
    assert built[ti.SOURCES] == {SOURCE: {TEST_F: [[5, 5]], TEST_G: [[9, 9]]}}


def test_the_lines_of_one_test_file_are_gathered_across_its_tests():
    executed = {SOURCE: {2: ["t.py::a|run"], 3: ["t.py::b|run"], 4: ["t.py::a|run", "u.py::c|run"]}}

    assert ti.build_map(executed, "abc", NOW)[ti.SOURCES] == {
        SOURCE: {"t.py": [[2, 4]], "u.py": [[4, 4]]}
    }


def _map_file(tmp_path, **changes):
    data = {
        ti.VERSION: ti.MAP_VERSION,
        ti.TREE: "abc",
        ti.CREATED: NOW.isoformat(),
        ti.SOURCES: {},
    }
    data.update(changes)
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data))
    return path


def test_a_fresh_map_is_loaded(tmp_path):
    assert ti.load_map(_map_file(tmp_path), 14, NOW)[ti.TREE] == "abc"


def test_a_map_exactly_as_old_as_the_limit_is_still_used(tmp_path):
    path = _map_file(tmp_path)

    assert ti.load_map(path, 14, NOW + timedelta(days=14)) is not None
    assert ti.load_map(path, 14, NOW + timedelta(days=14, seconds=1)) is None


@pytest.mark.parametrize(
    "damage",
    [{ti.VERSION: ti.MAP_VERSION + 1}, {ti.CREATED: "yesterday"}, {ti.CREATED: None}],
)
def test_a_map_that_cannot_be_trusted_is_not_loaded(tmp_path, damage):
    assert ti.load_map(_map_file(tmp_path, **damage), 14, NOW) is None


def test_a_missing_or_unparsable_map_is_not_loaded(tmp_path):
    assert ti.load_map(tmp_path / "absent.json", 14, NOW) is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert ti.load_map(broken, 14, NOW) is None
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text("{}")
    assert ti.load_map(incomplete, 14, NOW) is None


ENTRY = {TEST_F: [[4, 5]], TEST_G: [[8, 9]]}


def test_the_tests_that_ran_a_changed_line_are_chosen():
    assert ti.tests_for_source(ENTRY, {5}) == {TEST_F}
    assert ti.tests_for_source(ENTRY, {8, 9}) == {TEST_G}
    assert ti.tests_for_source(ENTRY, {5, 8}) == {TEST_F, TEST_G}


def test_a_line_no_test_names_chooses_every_test_that_ran_the_file():
    assert ti.tests_for_source(ENTRY, {1}) == {TEST_F, TEST_G}
    assert ti.tests_for_source(ENTRY, {5, 6}) == {TEST_F, TEST_G}


def test_no_changed_line_chooses_nothing():
    assert ti.tests_for_source(ENTRY, set()) == set()


@pytest.mark.parametrize(
    ("path", EXPECTED),
    [
        (README, True),
        ("docs/a/b.png", True),
        ("LICENSE", True),
        ("CHANGELOG.rst", True),
        (SOURCE, False),
        ("pyproject.toml", False),
        ("notes.txt", True),
    ],
)
def test_documentation_is_told_from_the_rest(path, expected):
    assert ti.is_documentation(path) is expected


@pytest.mark.parametrize(
    ("path", EXPECTED),
    [
        ("tests/test_f.py", True),
        ("tests/sub/conftest.py", True),
        ("test/x.py", True),
        ("pkg/tests_helper.py", False),
        (SOURCE, False),
        ("tests", False),
    ],
)
def test_a_path_under_a_tests_directory_is_a_test_path(path, expected):
    assert ti.is_test_path(path) is expected


@pytest.fixture
def project(repo):
    repo.commit("base", pkg__mod_py=MODULE, tests__test_f_py=TESTS_F, tests__test_g_py=TESTS_G)
    impact = ti.build_map(EXECUTED, repo.sha("HEAD^{tree}"), NOW)
    return repo, impact


def _selected(repo, impact):
    return ti.select(repo.path, impact)


def test_changing_a_line_one_test_ran_selects_that_test_file(project):
    repo, impact = project
    repo.write(SOURCE, MODULE.replace(PLUS_ONE, PLUS_TWO))

    assert _selected(repo, impact) == {TEST_F}


def test_changing_code_that_runs_at_import_selects_every_test_that_ran_the_file(project):
    repo, impact = project
    repo.write(SOURCE, MODULE.replace("BASE = 1", "BASE = 2"))

    assert _selected(repo, impact) == {TEST_F, TEST_G}


def test_inserting_a_line_between_two_functions_selects_the_tests_around_it(project):
    repo, impact = project
    repo.write(SOURCE, MODULE.replace("\n\ndef g", "\nOTHER = 1\n\n\ndef g", 1))

    assert _selected(repo, impact) == {TEST_F, TEST_G}


def test_the_line_numbers_of_the_map_tree_hold_after_main_moved_on(project):
    repo, impact = project
    repo.commit("main moves", pkg__mod_py="# a new header\n# and another\n" + MODULE)
    repo.write(SOURCE, ("# a new header\n# and another\n" + MODULE).replace(TIMES_TWO, "x * 3"))

    assert _selected(repo, impact) == {TEST_G, TEST_F}


def test_a_documentation_change_selects_nothing(project):
    repo, impact = project
    repo.write(README, "hello\n")
    repo.write("docs/x.md", "hello\n")

    assert _selected(repo, impact) == set()


@pytest.mark.parametrize(
    "path",
    [
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        "tests/conftest.py",
        "tests/support.py",
    ],
)
def test_a_file_that_cannot_be_placed_selects_everything(project, path):
    repo, impact = project
    repo.write(path, "x = 1\n")

    assert _selected(repo, impact) is None


def test_a_changed_test_file_selects_itself(project):
    repo, impact = project
    repo.write(TEST_G, TESTS_G + "\n\ndef test_more():\n    assert True\n")
    repo.write("tests/test_new.py", "def test_new():\n    assert True\n")

    assert _selected(repo, impact) == {TEST_G, "tests/test_new.py"}


def test_a_deleted_test_file_selects_nothing(project):
    repo, impact = project
    (repo.path / TEST_F).unlink()

    assert _selected(repo, impact) == set()


def test_a_new_source_file_no_test_ran_selects_nothing(project):
    repo, impact = project
    repo.write("pkg/new.py", "X = 1\n")

    assert _selected(repo, impact) == set()


def test_a_moved_source_file_is_read_against_its_old_path(project):
    repo, impact = project
    (repo.path / "pkg").joinpath("moved.py").write_text(MODULE.replace(TIMES_TWO, "x * 5"))
    (repo.path / SOURCE).unlink()
    repo.git("add", "-A")  # git sees a move only once both sides are staged

    assert _selected(repo, impact) == {TEST_G}


def test_the_working_tree_is_compared_with_the_tree_of_the_map(project):
    repo, impact = project
    repo.write(SOURCE, MODULE.replace(TIMES_TWO, "x * 3"))
    repo.git("add", "-A")
    repo.commit_staged("change g")

    assert _selected(repo, impact) == {TEST_G}


def test_the_main_output_is_one_sorted_test_file_a_line(project, tmp_path, capsys):
    repo, impact = project
    repo.write(SOURCE, MODULE.replace("BASE = 1", "BASE = 2"))
    fresh = ti.build_map(EXECUTED, impact[ti.TREE], datetime.now(UTC))
    path = tmp_path / IMPACT_FILE
    path.write_text(json.dumps(fresh))

    assert ti.main([SELECT, MAP_FLAG, str(path), PATH_FLAG, str(repo.path)]) == 0
    assert capsys.readouterr().out == f"{TEST_F}\n{TEST_G}\n"


def test_the_map_restored_into_the_checkout_is_not_a_change(project, capsys):
    repo, impact = project
    repo.write(SOURCE, MODULE.replace(PLUS_ONE, PLUS_TWO))
    fresh = ti.build_map(EXECUTED, impact[ti.TREE], datetime.now(UTC))
    repo.write(ti.DEFAULT_MAP, json.dumps(fresh))

    assert (
        ti.main([SELECT, MAP_FLAG, str(repo.path / ti.DEFAULT_MAP), PATH_FLAG, str(repo.path)]) == 0
    )
    assert capsys.readouterr().out == f"{TEST_F}\n"


def test_the_main_output_is_all_without_a_usable_map(project, tmp_path, capsys):
    repo, impact = project
    old = ti.build_map(EXECUTED, impact[ti.TREE], NOW - timedelta(days=60))
    path = tmp_path / IMPACT_FILE
    path.write_text(json.dumps(old))
    args = [SELECT, MAP_FLAG, str(path), PATH_FLAG, str(repo.path)]

    assert ti.main(args) == 0
    assert capsys.readouterr().out == "ALL\n"
    assert ti.main([SELECT, MAP_FLAG, str(tmp_path / "none.json"), PATH_FLAG, str(repo.path)]) == 0
    assert capsys.readouterr().out == "ALL\n"


def test_a_map_made_on_a_tree_still_applies_after_the_change_landed_as_another_commit(project):
    repo, _ = project
    repo.git("checkout", "-q", "-b", "queue")
    repo.commit("the change the queue tested", pkg__mod_py=MODULE + "# more\n")
    queued = repo.sha()
    tested = ti.build_map(EXECUTED, repo.sha("HEAD^{tree}"), NOW)
    repo.git("checkout", "-q", "main")
    repo.git("merge", "--squash", "queue")  # lands as a new commit holding the tested tree
    repo.commit_staged("squashed")

    assert repo.sha() != queued
    assert _selected(repo, tested) == set()  # no change since the tree the map was made on


def test_a_commit_id_is_not_a_tree_of_this_checkout(project):
    repo, impact = project

    assert ti.tree_present(impact[ti.TREE], repo.path)
    assert not ti.tree_present(repo.sha(), repo.path)


def test_the_main_output_is_all_when_the_tree_of_the_map_is_not_here(project, tmp_path, capsys):
    repo, impact = project
    gone = ti.build_map(EXECUTED, "0" * 40, datetime.now(UTC))
    path = tmp_path / IMPACT_FILE
    path.write_text(json.dumps(gone))

    assert ti.main([SELECT, MAP_FLAG, str(path), PATH_FLAG, str(repo.path)]) == 0
    assert capsys.readouterr().out == "ALL\n"


def test_a_recorded_run_selects_what_a_real_pytest_run_executed(repo, tmp_path):
    repo.write("pkg/__init__.py", "")
    repo.write(".gitignore", ".coverage\n__pycache__/\n.pytest_cache/\n")
    repo.commit(
        "base",
        pkg__mod_py=MODULE,
        tests__test_f_py=TESTS_F,
        tests__test_g_py=TESTS_G,
    )
    out = tmp_path / IMPACT_FILE
    record_real_run(repo.path, out)

    sources = json.loads(out.read_text())[ti.SOURCES]
    assert set(sources) == {"pkg/__init__.py", SOURCE}
    assert set(sources[SOURCE]) == {TEST_F, TEST_G}
    repo.write(SOURCE, MODULE.replace(PLUS_ONE, PLUS_TWO))
    assert ti.select(repo.path, json.loads(out.read_text())) == {TEST_F}


def _same(status, path):
    return ti.Change(status, path, path)


@pytest.mark.parametrize(
    ("change", "kind"),
    [
        (_same("M", README), ti.NOTHING),
        (_same("M", SOURCE), ti.SOURCE),
        (_same("A", A_TEST), ti.ITSELF),
        (_same("D", A_TEST), ti.NOTHING),
        (_same("M", CONFTEST), ti.EVERYTHING),
        (_same("M", LOCK), ti.EVERYTHING),
        (ti.Change("R", "notes.md", "pkg/notes.py"), ti.SOURCE),
        (ti.Change("R", "pkg/a.py", "docs/a.md"), ti.EVERYTHING),
    ],
)
def test_a_change_is_told_by_its_paths_and_status(change, kind):
    assert ti.classify(change) == kind


def test_git_failing_to_say_what_changed_runs_every_test_and_says_so(
    project, tmp_path, monkeypatch, capsys
):
    repo, impact = project
    fresh = ti.build_map(EXECUTED, impact[ti.TREE], datetime.now(UTC))
    path = tmp_path / IMPACT_FILE
    path.write_text(json.dumps(fresh))
    real = ti.git

    def failing(args, **kwargs):
        if args[0] == "diff":
            raise SystemExit("✗ git diff failed:\nfatal: bad object")
        return real(args, **kwargs)

    monkeypatch.setattr(ti, "git", failing)

    assert ti.run_select(repo.path, path, 14, datetime.now(UTC)) == ti.ALL
    assert "bad object" in capsys.readouterr().err


def test_a_map_path_outside_the_checkout_is_named_as_given(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    elsewhere = tmp_path / "elsewhere" / IMPACT_FILE

    assert ti.ignore_key(root / IMPACT_FILE, root) == IMPACT_FILE
    assert ti.ignore_key(elsewhere, root) == str(elsewhere)
