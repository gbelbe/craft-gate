"""Steps for mutation_baseline_rounding.feature: a stored score is compared at its own precision."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("mutation_baseline_rounding.feature")

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_mutation_ratchet.py"
_SPEC = importlib.util.spec_from_file_location("check_mutation_ratchet_rounding", _SCRIPT)
assert _SPEC and _SPEC.loader
ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ratchet)


@pytest.fixture
def world():
    return SimpleNamespace(recorded=0.0, violations=[])


@given(parsers.parse("a function recorded at {recorded:f} percent"))  # noqa: V103
def _recorded(world, recorded: float) -> None:
    world.recorded = recorded


@when(
    parsers.parse(
        "a test change leaves it with {killed:d} killed and {survived:d} surviving mutants"
    )
)  # noqa: V103
def _retested(world, killed: int, survived: int) -> None:
    counts = {"killed": killed, "survived": survived, "no_tests": 0}
    world.violations, _ = ratchet.evaluate_domain({"f": counts}, {"f": world.recorded})


@then("the ratchet accepts it")  # noqa: V103
def _accepts(world) -> None:
    assert world.violations == []


@then(parsers.parse("the ratchet refuses it, {message}"))  # noqa: V103
def _refuses(world, message: str) -> None:
    assert len(world.violations) == 1
    assert message in world.violations[0]
