#!/usr/bin/env python3
"""The mutation ratchet's acceptance rule, behaviourally (no pytest dependency).

A touched function is accepted when it scores at least the threshold (80%), or, only when it
already has a recorded baseline score, when it improves on that score by at least the improvement
margin (20%). A function with no recorded baseline gets no second path: it must reach the threshold.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "check_mutation_ratchet", ROOT / "scripts" / "check_mutation_ratchet.py"
)
assert _SPEC and _SPEC.loader
ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ratchet)

evaluate = ratchet.evaluate_results


def counts(killed: int, survived: int, no_tests: int = 0) -> dict[str, int]:
    return {"killed": killed, "survived": survived, "no_tests": no_tests}


# -- a function with no recorded baseline must reach the threshold ----------------


def test_a_new_function_below_the_threshold_is_refused() -> None:
    violations, _ = evaluate({"pkg.py::new": counts(5, 5)}, {})

    assert len(violations) == 1
    assert violations[0].startswith("pkg.py::new:")
    assert "50%" in violations[0]
    assert "80%" in violations[0]
    assert "baseline" in violations[0]


def test_a_new_function_at_exactly_the_threshold_passes() -> None:
    violations, updated = evaluate({"pkg.py::new": counts(8, 2)}, {})

    assert violations == []
    assert updated == {"pkg.py::new": 80.0}


def test_a_new_function_just_under_the_threshold_is_refused() -> None:
    violations, _ = evaluate({"pkg.py::new": counts(79, 21)}, {})

    assert len(violations) == 1


def test_a_new_function_above_the_threshold_passes_and_is_recorded() -> None:
    violations, updated = evaluate({"pkg.py::new": counts(9, 1)}, {})

    assert violations == []
    assert updated == {"pkg.py::new": 90.0}


def test_the_threshold_the_caller_chose_is_the_one_a_new_function_must_reach() -> None:
    assert evaluate({"f": counts(6, 4)}, {}, threshold=60.0)[0] == []
    assert len(evaluate({"f": counts(5, 5)}, {}, threshold=60.0)[0]) == 1


# -- a function with a recorded baseline keeps the improvement path ---------------


def test_a_known_function_may_pass_by_improving_twenty_percent() -> None:
    # 50% -> 60% is exactly +20% of 50
    violations, updated = evaluate({"f": counts(6, 4)}, {"f": 50.0})

    assert violations == []
    assert updated == {"f": 60.0}


def test_a_known_function_short_of_the_improvement_is_refused() -> None:
    violations, _ = evaluate({"f": counts(59, 41)}, {"f": 50.0})

    assert len(violations) == 1
    assert "59%" in violations[0]
    assert "needs >= 60%" in violations[0]


def test_a_known_function_at_the_threshold_passes_whatever_its_baseline() -> None:
    assert evaluate({"f": counts(8, 2)}, {"f": 79.0})[0] == []


# -- unchanged behaviour ----------------------------------------------------------


def test_a_function_no_test_covers_is_refused() -> None:
    violations, _ = evaluate({"f": counts(0, 0, no_tests=3)}, {})

    assert violations == ["f: no covering tests"]


def test_a_function_with_no_mutants_is_ignored() -> None:
    violations, updated = evaluate({"f": counts(0, 0)}, {})

    assert violations == []
    assert updated == {}


def test_other_functions_baselines_are_kept() -> None:
    _, updated = evaluate({"f": counts(9, 1)}, {"g": 42.0})

    assert updated == {"g": 42.0, "f": 90.0}


def test_each_function_is_judged_on_its_own() -> None:
    violations, _ = evaluate(
        {"good": counts(9, 1), "bad": counts(1, 9), "known": counts(6, 4)}, {"known": 50.0}
    )

    assert [v.split(":")[0] for v in violations] == ["bad"]


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
    print("mutation ratchet rule tests passed")
