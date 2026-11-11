"""Steps for architecture_ratchet.feature: a real git repo, the real gate."""

from __future__ import annotations

from types import SimpleNamespace

import check_architecture_ratchet as gate
import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("architecture_ratchet.feature")

BAD = "shop/domain/bad.py"
FIRST = "shop.domain.bad -> shop.adapters.db"
SECOND = "shop.domain.bad -> shop.adapters.web"
SOURCE = gate.SOURCE
EDITED = "x = 2\n"


@pytest.fixture
def world(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(repo=repo, exit=None, report="", violations=[FIRST, SECOND])


def declare(world, violations: list[str]) -> None:
    declaration = {"root_package": "shop", "layers": ["adapters", "domain"]}
    world.repo.write(SOURCE, yaml.safe_dump({**declaration, gate.KNOWN_KEY: violations}))


@given("a repository with the modules shop.domain.bad and shop.domain.clean")
def _modules(world) -> None:
    world.repo.commit("base", shop__domain__bad_py="x = 1\n", shop__domain__clean_py="y = 1\n")


@given("architecture.yaml lists two known violations in shop.domain.bad")
def _listed(world) -> None:
    declare(world, world.violations)
    world.repo.git("add", "-A")
    world.repo.commit_staged("declare the architecture")


@given("a branch for the change")
def _branch(world) -> None:
    world.repo.branch("feature")


@when(parsers.parse("the change edits {path}"))
def _edit(world, path: str) -> None:
    world.repo.commit("change", **{path.replace("/", "__").replace(".py", "_py"): EDITED})


@when(parsers.parse("the change edits {path} with a Tidy-Exempt trailer"))
def _edit_exempt(world, path: str) -> None:
    world.repo.write(path, EDITED)
    world.repo.git("add", "-A")
    world.repo.commit_staged("change\n\nTidy-Exempt: nothing to pay down yet")


@when("the change removes one known violation")
def _remove_one(world) -> None:
    declare(world, [SECOND])
    world.repo.git("add", "-A")
    world.repo.commit_staged("pay one down")


@then("the architecture ratchet fails")
def _fails(world, run_main, capsys) -> None:
    world.exit = run_main(gate, "--base", "main")
    world.report = capsys.readouterr().err
    assert world.exit == 1


@then("the architecture ratchet passes")
def _passes(world, run_main) -> None:
    assert run_main(gate, "--base", "main") == 0


@then(parsers.parse('the report names "{line}"'))
def _names(world, line: str) -> None:
    assert line in world.report
