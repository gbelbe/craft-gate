"""Steps for test_impact_selection.feature: a project, its recorded run, the change under test."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import test_impact as ti
from conftest import record_real_run
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("test_impact_selection.feature")

SOURCE = "pkg/mod.py"
FIRST, SECOND = "tests/test_first.py", "tests/test_second.py"
MODULE = "BASE = 1\n\n\ndef first(x):\n    return x + 1\n\n\ndef second(x):\n    return x * 2\n"
FIRST_TEST = "from pkg.mod import first\n\n\ndef test_first():\n    assert first(1) == 2\n"
SECOND_TEST = "from pkg.mod import second\n\n\ndef test_second():\n    assert second(2) == 4\n"
EXECUTED = {
    SOURCE: {
        1: [""],
        4: [""],
        5: [f"{FIRST}::test_first|run"],
        8: [""],
        9: [f"{SECOND}::test_second|run"],
    }
}
GITIGNORE = ".coverage\n__pycache__/\n.pytest_cache/\n"
FIRST_EDIT = "a line only the first test ran is edited"
EDITS = {
    FIRST_EDIT: (SOURCE, MODULE.replace("x + 1", "x + 2")),
    "a line that runs at import is edited": (SOURCE, MODULE.replace("BASE = 1", "BASE = 2")),
    "a test file is edited": (SECOND, SECOND_TEST + "\n\ndef test_more():\n    assert True\n"),
    "only the readme is edited": ("README.md", "hello\n"),
    "a new source file no test ran is added": ("pkg/extra.py", "EXTRA = 1\n"),
    "the lock file is edited": ("uv.lock", "x = 1\n"),
    "conftest.py is edited": ("tests/conftest.py", "x = 1\n"),
}
SELECTIONS = {  # what `select` prints, one entry a line
    "the first test": [FIRST],
    "both tests": [FIRST, SECOND],
    "that test": [SECOND],
    "no test": [],
    "every test": [ti.ALL],
}


@pytest.fixture
def world(repo):
    repo.write("pkg/__init__.py", "")
    repo.write(".gitignore", GITIGNORE)
    repo.commit(
        "base",
        pkg__mod_py=MODULE,
        tests__test_first_py=FIRST_TEST,
        tests__test_second_py=SECOND_TEST,
    )
    return SimpleNamespace(
        repo=repo, impact=None, map_path=repo.path.parent / "impact.json", picked=None
    )


def _save(world, when_made) -> None:
    world.impact = ti.build_map(EXECUTED, world.repo.sha("HEAD^{tree}"), when_made)
    world.map_path.write_text(json.dumps(world.impact))


def _select(world, extra=()) -> str:
    args = ["select", "--map", str(world.map_path), "--path", str(world.repo.path), *extra]
    return subprocess.run(
        [sys.executable, ti.__file__, *args], capture_output=True, text=True, check=True
    ).stdout


@given("a project with two tests, one for each of its two functions")
def _project(world) -> None:
    assert (world.repo.path / SOURCE).exists()


@given("the full run recorded which test ran which line")
def _recorded(world) -> None:
    _save(world, datetime.now(UTC))


@given("that map is older than the limit")
def _old(world) -> None:
    _save(world, datetime.now(UTC) - timedelta(days=ti.DEFAULT_MAX_AGE_DAYS + 1))


@given("the map is restored into the checkout")
def _restored(world) -> None:
    world.map_path = world.repo.path / ti.DEFAULT_MAP
    world.map_path.write_text(json.dumps(world.impact))


@when(parsers.parse('the change is "{change}"'))
def _change(world, change: str) -> None:
    path, content = EDITS[change]
    world.repo.write(path, content)


@when("a change edits a line only the first test ran")
def _edit_first(world) -> None:
    path, content = EDITS[FIRST_EDIT]
    world.repo.write(path, content)


@when("the tests run with per-test coverage and the map is recorded")
def _real_run(world) -> None:
    record_real_run(world.repo.path, world.map_path)
    world.impact = json.loads(world.map_path.read_text())


@then(parsers.parse("the pull request runs {selection}"))
def _runs(world, selection: str) -> None:
    assert _select(world).split() == SELECTIONS[selection]


@then("the map names each test file against the lines it ran")
def _names(world) -> None:
    assert world.impact["sources"][SOURCE] == {FIRST: [[5, 5]], SECOND: [[9, 9]]}


@then("a change to a line only the first test ran selects the first test")
def _selects_first(world) -> None:
    path, content = EDITS[FIRST_EDIT]
    world.repo.write(path, content)
    assert _select(world).split() == [FIRST]
