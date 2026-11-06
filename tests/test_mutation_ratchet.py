"""The mutation ratchet's acceptance rule, behaviourally.

A touched function is accepted when it scores at least the threshold (80%), and refused below it.
There is one bar and nothing stored: the rule has no memory of an earlier score.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "check_mutation_ratchet", ROOT / "scripts" / "check_mutation_ratchet.py"
)
assert _SPEC and _SPEC.loader
ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ratchet)

evaluate = ratchet.evaluate_results
NEEDS_THE_BAR = "needs >= 80%"  # what a refusal says when the threshold is the default 80
CHOSEN_THRESHOLD = 90.0


def counts(killed: int, survived: int, no_tests: int = 0) -> dict[str, int]:
    return {"killed": killed, "survived": survived, "no_tests": no_tests}


# -- the bar --------------------------------------------------------------------------


def test_a_function_below_the_threshold_is_refused() -> None:
    violations = evaluate({"pkg.py::f": counts(5, 5)})

    assert len(violations) == 1
    assert violations[0].startswith("pkg.py::f:")
    assert "50%" in violations[0]
    assert NEEDS_THE_BAR in violations[0]


def test_a_function_at_exactly_the_threshold_passes() -> None:
    assert evaluate({"f": counts(8, 2)}) == []


def test_a_function_just_under_the_threshold_is_refused() -> None:
    assert len(evaluate({"f": counts(79, 21)})) == 1


def test_a_function_above_the_threshold_passes() -> None:
    assert evaluate({"f": counts(9, 1)}) == []


def test_the_threshold_the_caller_chose_is_the_bar() -> None:
    assert evaluate({"f": counts(6, 4)}, threshold=60.0) == []
    assert len(evaluate({"f": counts(5, 5)}, threshold=60.0)) == 1


def test_a_refusal_names_the_threshold_the_caller_chose() -> None:
    refused = evaluate({"f": counts(89, 11)}, threshold=CHOSEN_THRESHOLD)

    assert "needs >= 90%" in refused[0]
    assert evaluate({"f": counts(90, 10)}, threshold=CHOSEN_THRESHOLD) == []


def test_each_function_is_judged_on_its_own() -> None:
    violations = evaluate({"good": counts(9, 1), "bad": counts(1, 9), "weak": counts(6, 4)})

    assert [v.split(":")[0] for v in violations] == ["bad", "weak"]


# -- what is not judged -----------------------------------------------------------------


def test_a_function_no_test_covers_is_refused() -> None:
    assert evaluate({"f": counts(0, 0, no_tests=3)}) == ["f: no covering tests"]


def test_a_function_with_no_mutants_is_ignored() -> None:
    assert evaluate({"f": counts(0, 0)}) == []


# -- nothing is remembered between runs -------------------------------------------------


@pytest.mark.parametrize(
    "gone",
    ["required_score", "evaluate_domain", "load_baseline", "diff_fingerprint", "planned_domain"],
)
def test_the_ratchet_keeps_no_baseline_and_has_no_second_path(gone: str) -> None:
    assert not hasattr(ratchet, gone)


def test_the_ratchet_takes_no_baseline_or_improvement_option() -> None:
    source = (ROOT / "scripts" / "check_mutation_ratchet.py").read_text()

    for option in ("--improvement", "--baseline", "--regression-floor", "--regression-tolerance"):
        assert option not in source
