"""Steps for mutation_renames.feature: a moved test file and what the plan makes of it."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import mutation_plan
import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("mutation_renames.feature")

OLD, NEW = "tests/unit/test_a.py", "tests/brick/test_a.py"
FUNCTION = "pkg.mod.x_covered"
TEST = "test_covered"
PYPROJECT = (
    "[tool.mutmut]\n"
    'only_mutate = ["pkg/mod.py"]\n'
    "pytest_add_cli_args_test_selection = ['{selected}', '-m', 'mutation']\n"
)
SELECTION_ARGS = [OLD, "-m", "mutation"]
STATS = {
    "tests_by_mangled_function_name": {FUNCTION: [f"{OLD}::{TEST}"]},
    "duration_by_test": {f"{OLD}::{TEST}": 0.1},
    "config_fingerprint": {"test_selection": mutation_plan.selection_fingerprint(SELECTION_ARGS)},
}


@pytest.fixture
def world(tmp_path):
    return SimpleNamespace(root=tmp_path, mutants=tmp_path / "mutants")


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@given("a mutation cache that knows the tests of tests/unit/test_a.py")
def _cache(world) -> None:
    root = world.root
    git(root, "init", "-q", "-b", "main")
    (root / "pkg").mkdir()
    (root / "pkg/mod.py").write_text("def covered():\n    return 1\n")
    (root / OLD).parent.mkdir(parents=True)
    (root / OLD).write_text("import pkg.mod\n" + "\n".join(f"# line {i}" for i in range(20)) + "\n")
    (root / "pyproject.toml").write_text(PYPROJECT.format(selected=OLD))
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "base")
    world.mutants.mkdir()
    (world.mutants / "mutmut-stats.json").write_text(json.dumps(STATS))


def move(world, *, edit: bool) -> None:
    root = world.root
    (root / NEW).parent.mkdir(parents=True)
    git(root, "mv", OLD, NEW)
    if edit:
        with (root / NEW).open("a") as handle:
            handle.write("# edited\n")
    (root / "pyproject.toml").write_text(PYPROJECT.format(selected=NEW))
    git(root, "add", ".")
    inputs, old_args, new_args = mutation_plan.collect_inputs(root, "HEAD", world.mutants)
    world.plan = mutation_plan.plan(inputs)
    mutation_plan.apply(world.plan, world.mutants, old_args, new_args)


@when("tests/unit/test_a.py is moved to tests/brick/test_a.py")
def _moved(world) -> None:
    move(world, edit=False)


@when("tests/unit/test_a.py is moved to tests/brick/test_a.py and edited")
def _moved_and_edited(world) -> None:
    move(world, edit=True)


@when(
    "tests/unit/test_a.py is moved to tests/brick/test_a.py and edited, "
    "and the function it covers is edited too"
)
def _moved_edited_and_function_touched(world) -> None:
    (world.root / "pkg/mod.py").write_text("def covered():\n    return 2\n")
    move(world, edit=True)


@then("the plan measures those tests again")
def _measured_again(world) -> None:
    assert world.plan.stale_tests == (f"{OLD}::{TEST}",)  # the cache knows them by the old path


@then("the plan re-tests no function")
def _nothing(world) -> None:
    assert world.plan.mode == "incremental"
    assert world.plan.reset_functions == ()


@then("the cache names those tests after tests/brick/test_a.py")
def _renamed_cache(world) -> None:
    stats = json.loads((world.mutants / "mutmut-stats.json").read_text())
    assert list(stats["duration_by_test"]) == [f"{NEW}::{TEST}"]


@then("the plan re-tests the function those tests cover")
def _retests(world) -> None:
    assert world.plan.reset_functions == (FUNCTION,)
