"""Steps for mutation_one_bar.feature: one threshold for every touched function, recorded or not."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("mutation_one_bar.feature")

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_mutation_ratchet.py"
_SPEC = importlib.util.spec_from_file_location("check_mutation_ratchet_steps", _SCRIPT)
assert _SPEC and _SPEC.loader
ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ratchet)

MUTANTS = 100


@pytest.fixture
def world():
    return SimpleNamespace(threshold=0.0, baseline={}, violations=[])


@given(parsers.parse("a threshold of {threshold:d} percent"))
def _threshold(world, threshold: int) -> None:
    world.threshold = float(threshold)


@given(parsers.parse("a function recorded at {baseline:d} percent"))
def _recorded(world, baseline: int) -> None:
    world.baseline = {"f": float(baseline)}


@given("a function that was never recorded")
def _never_recorded(world) -> None:
    world.baseline = {}


@when(parsers.parse("the function now scores {score:d} percent"))
def _scores(world, score: int) -> None:
    counts = {"killed": score, "survived": MUTANTS - score, "no_tests": 0}
    world.violations, _ = ratchet.evaluate_results({"f": counts}, world.baseline, world.threshold)


@then("the ratchet accepts it")
def _accepts(world) -> None:
    assert world.violations == []


@then(parsers.parse("the ratchet refuses it, needing {needed:d}"))
def _refuses(world, needed: int) -> None:
    assert len(world.violations) == 1
    assert f"needs >= {needed}%" in world.violations[0]
