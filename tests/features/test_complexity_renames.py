"""Steps for complexity_renames.feature: a moved file keeps the history of what it carries."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("complexity_renames.feature")

LIMIT = 15
OVER_THE_LIMIT = LIMIT + 2
OLD = "mod.py"
NEW = "pkg/mod.py"
MAIN = "main"
RETURN = "    return r"
PATH_FLAG = "--path"
MODULE = "\n".join(
    [
        "def long(x):",
        "    r = 0",
        *[f"    if x == {i}:\n        r += {i}" for i in range(OVER_THE_LIMIT)],
        RETURN,
        "",
        "",
        'FIRST = "the same text"',
        'SECOND = "the same text"',
        'THIRD = "the same text"',
        "",
    ]
)


@pytest.fixture
def world(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(repo=repo, exit=None, touched=None)


@given("a base commit whose module has an over-limit function and a thrice-used literal")
def _base(world) -> None:
    world.repo.commit("base", mod_py=MODULE)
    world.repo.branch("feature")


def move(world, content: str, keep_original: bool = False) -> None:
    if not keep_original:
        world.repo.git("rm", "-q", OLD)
    world.repo.write(NEW, content)
    world.repo.git("add", "-A")
    world.repo.commit_staged("move the module")


@when("the module moves to another folder unchanged")
def _moved(world) -> None:
    move(world, MODULE)


@when("the module moves to another folder and its long function gains a branch")
def _moved_and_worse(world) -> None:
    move(world, MODULE.replace(RETURN, "    if x == 99:\n        r += 99\n    return r", 1))


@when("the module moves to another folder and gains a new function over the limit")
def _moved_and_extended(world) -> None:
    extra = "\n".join(
        [
            "def added(x):",
            "    r = 0",
            *[f"    if x == {i}:\n        r += {i}" for i in range(OVER_THE_LIMIT)],
            RETURN,
            "",
        ]
    )
    move(world, MODULE + "\n\n" + extra)


@when("the module is copied to another folder and the original kept")
def _copied(world) -> None:
    move(world, MODULE, keep_original=True)


@then(parsers.re(r"the complexity ratchet (?P<verdict>passes|fails)"))
def _verdict(world, run_main, verdict) -> None:
    import check_complexity_ratchet as ratchet

    world.exit = run_main(ratchet, "--base", MAIN, PATH_FLAG, ".")

    assert (world.exit == 0) == (verdict == "passes"), f"exit code {world.exit}"


@then("no function of it counts as touched")
def _untouched(world) -> None:
    import gitdiff

    ranges = {f"{NEW}::long": (1, OVER_THE_LIMIT * 2 + 3)}
    moved_from = {NEW: OLD}

    assert gitdiff.touched_names(world.repo.path, MAIN, ranges, moved_from) == set()
