"""Steps for architecture_wired.feature: the real check, on a throwaway repository."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import render_architecture as arch
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("architecture_wired.feature")

RATCHET_RUN = "run: python3 scripts/check_architecture_ratchet.py --base origin/main\n"
WORKFLOW = ".github/workflows/ci.yml"
HOOKS = ".pre-commit-config.yaml"


@pytest.fixture
def world(tmp_path):
    return SimpleNamespace(root=tmp_path, exit=None, report="")


def put(world, path: str, text: str) -> None:
    (world.root / path).parent.mkdir(parents=True, exist_ok=True)
    (world.root / path).write_text(text)


@given("a repository that declares its layers and has generated the architecture files")
def _declared(world) -> None:
    put(world, arch.SOURCE, "root_package: shop\nlayers: [adapters, domain]\n")
    assert arch.main(["--path", str(world.root)]) == 0


@given("a workflow runs the ratchet")
def _workflow(world) -> None:
    put(world, WORKFLOW, RATCHET_RUN)


@given("a pre-commit hook runs the ratchet")
def _hook(world) -> None:
    put(world, HOOKS, RATCHET_RUN)


@given("a workflow only mentions the ratchet in a comment")
def _comment(world) -> None:
    put(world, WORKFLOW, f"# {RATCHET_RUN}")


@when("the architecture check runs")
def _check(world, capsys) -> None:
    capsys.readouterr()
    world.exit = arch.main(["--path", str(world.root), "--check"])
    world.report = capsys.readouterr().err


@then("the architecture check fails")
def _fails(world) -> None:
    assert world.exit == 1


@then("the architecture check passes")
def _passes(world) -> None:
    assert world.exit == 0


@then(parsers.parse('the report names "{text}"'))
def _names(world, text: str) -> None:
    assert text in world.report
