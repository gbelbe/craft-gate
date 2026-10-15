"""Steps for mutation_selection.feature: the selection, the marker and the gate's verdict."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import gate_config
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("mutation_selection.feature")

UNIT = Path("tests/unit")
MARKED = "import pytest\n\n\n@pytest.mark.mutation\ndef test_a():\n    assert True\n"
PYPROJECT = (
    "[tool.mutmut]\n"
    "pytest_add_cli_args_test_selection = ['tests/unit/test_a.py', '-m', 'mutation']\n"
)
REGISTRATION = "[tool.pytest.ini_options]\nmarkers = ['mutation: focused tests']\n"


@pytest.fixture
def world(tmp_path):
    return SimpleNamespace(root=tmp_path, pyproject=PYPROJECT)


def write_test(root, name: str) -> None:
    (root / UNIT).mkdir(parents=True, exist_ok=True)
    (root / UNIT / name).write_text(MARKED)


@given("a repo that selects tests/unit/test_a.py with -m mutation")
def _selects(world) -> None:
    write_test(world.root, "test_a.py")


@given("the marker is registered")
def _registered(world) -> None:
    world.pyproject += REGISTRATION


@given("the marker is not registered")
def _unregistered(world) -> None:
    pass


@given("the selected file is deleted")
def _deleted(world) -> None:
    world.pyproject += REGISTRATION
    (world.root / UNIT / "test_a.py").unlink()


@given("another test file also carries the marker")
def _orphan(world) -> None:
    world.pyproject += REGISTRATION
    write_test(world.root, "test_orphan.py")


@when("the workflow asks for the mutation gate")
def _ask(world) -> None:
    (world.root / "pyproject.toml").write_text(world.pyproject)
    world.decision = gate_config.decide(world.root, gate_config.MUTATION)


@then("the mutation gate runs")
def _runs(world) -> None:
    assert world.decision.status == gate_config.RUN


@then(parsers.parse("the mutation gate stops: {text}"))
def _stops(world, text) -> None:
    assert world.decision.status == gate_config.ERROR
    assert text in world.decision.reason
