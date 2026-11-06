"""The mutation ratchet's acceptance rule, behaviourally.

A touched function is accepted when it scores at least the threshold (80%), and refused below it.
There is one bar: a function that was recorded before, at any score, owes the same as a new one.
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
NEEDS_THE_BAR = "needs >= 80%"  # what a refusal says when the threshold is the default 80
evaluate_domain = ratchet.evaluate_domain


def counts(killed: int, survived: int, no_tests: int = 0) -> dict[str, int]:
    return {"killed": killed, "survived": survived, "no_tests": no_tests}


# -- a function that was never recorded must reach the threshold -----------------


def test_a_new_function_below_the_threshold_is_refused() -> None:
    violations, _ = evaluate({"pkg.py::new": counts(5, 5)}, {})

    assert len(violations) == 1
    assert violations[0].startswith("pkg.py::new:")
    assert "50%" in violations[0]
    assert NEEDS_THE_BAR in violations[0]


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


# -- a function that was recorded before owes the same threshold -----------------


def test_a_recorded_function_below_the_threshold_is_refused_whatever_its_baseline() -> None:
    # 50% -> 60% used to pass as "+20% of 50"; there is no such path any more
    violations, _ = evaluate({"f": counts(6, 4)}, {"f": 50.0})

    assert len(violations) == 1
    assert "60%" in violations[0]
    assert NEEDS_THE_BAR in violations[0]


def test_a_recorded_function_at_the_threshold_passes_whatever_its_baseline() -> None:
    assert evaluate({"f": counts(8, 2)}, {"f": 79.0})[0] == []
    assert evaluate({"f": counts(8, 2)}, {"f": 99.0})[0] == []


def test_a_recorded_function_is_not_asked_to_beat_its_own_score() -> None:
    # recorded at 95%, now 85%: above the bar, so the touch is accepted (and the score recorded)
    violations, updated = evaluate({"f": counts(85, 15)}, {"f": 95.0})

    assert violations == []
    assert updated == {"f": 85.0}


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

    assert [v.split(":")[0] for v in violations] == ["bad", "known"]


# -- functions re-tested because their tests changed (not touched themselves) -----


def test_a_test_change_that_weakens_a_function_is_refused() -> None:
    violations, _ = evaluate_domain({"f": counts(6, 4)}, {"f": 90.0})

    assert len(violations) == 1
    assert violations[0].startswith("f:")
    assert "60%" in violations[0]
    assert "90%" in violations[0]


def test_a_test_change_that_strengthens_a_function_raises_its_baseline() -> None:
    violations, updated = evaluate_domain({"f": counts(9, 1)}, {"f": 60.0})

    assert violations == []
    assert updated == {"f": 90.0}


def test_a_test_change_that_keeps_a_function_where_it_was_passes() -> None:
    violations, updated = evaluate_domain({"f": counts(9, 1)}, {"f": 90.0})

    assert violations == []
    assert updated == {"f": 90.0}


def test_a_re_tested_function_with_no_baseline_is_recorded_not_judged() -> None:
    # only a function the diff touches must reach the threshold; this one is seeded
    violations, updated = evaluate_domain({"f": counts(1, 9)}, {})

    assert violations == []
    assert updated == {"f": 10.0}


def test_a_drop_inside_the_tolerance_passes_and_keeps_the_better_baseline() -> None:
    violations, updated = evaluate_domain({"f": counts(88, 12)}, {"f": 90.0}, tolerance=2.0)

    assert violations == []
    assert updated == {"f": 90.0}


def test_a_drop_that_stays_at_or_above_the_floor_passes_and_keeps_the_better_baseline() -> None:
    violations, updated = evaluate_domain({"f": counts(95, 5)}, {"f": 100.0}, floor=90.0)

    assert violations == []
    assert updated == {"f": 100.0}


def test_a_drop_to_exactly_the_floor_passes() -> None:
    violations, _ = evaluate_domain({"f": counts(9, 1)}, {"f": 100.0}, floor=90.0)

    assert violations == []


def test_a_drop_below_the_floor_is_refused_whatever_the_baseline() -> None:
    violations, _ = evaluate_domain({"f": counts(89, 11)}, {"f": 100.0}, floor=90.0)

    assert len(violations) == 1
    assert "lowered" in violations[0]


def test_without_a_floor_any_drop_is_refused() -> None:
    violations, _ = evaluate_domain({"f": counts(95, 5)}, {"f": 100.0})

    assert len(violations) == 1


def test_a_function_whose_mutants_were_not_all_re_tested_is_flagged() -> None:
    results = {"f": {"killed": 5, "survived": 0, "no_tests": 0, "other": 0, "pending": 3}}

    violations, _ = evaluate_domain(results, {"f": 50.0})

    assert violations == ["f: 3 mutant(s) were not re-tested after the plan reset them"]


# -- the bar is the threshold the caller chose --------------------------------------

BASELINE = 78.0
CHOSEN_THRESHOLD = 90.0


def test_a_recorded_function_just_short_of_the_threshold_is_told_the_threshold() -> None:
    violations, _ = evaluate({"f": counts(79, 21)}, {"f": BASELINE})

    assert len(violations) == 1
    assert NEEDS_THE_BAR in violations[0]


def test_the_bar_follows_the_threshold_the_caller_chose() -> None:
    refused, _ = evaluate({"f": counts(89, 11)}, {"f": BASELINE}, threshold=CHOSEN_THRESHOLD)
    passed, _ = evaluate({"f": counts(90, 10)}, {"f": BASELINE}, threshold=CHOSEN_THRESHOLD)

    assert "needs >= 90%" in refused[0]
    assert passed == []


def test_there_is_no_improvement_margin_to_pass_a_different_way() -> None:
    assert not hasattr(ratchet, "required_score")


# -- a stored score and a fresh one are compared at the same precision -------------

MOST_KILLED = 80
MOST_SURVIVING = 5
STORED_AT_97 = 97.4359  # 38 of 39 killed, as the baseline file stores it
ONE_MORE_SURVIVOR = counts(35, 1)  # 35 of 36: 97.2222, genuinely lower


def test_a_re_tested_function_with_the_counts_it_was_recorded_with_is_never_refused() -> None:
    refused = []
    for killed in range(1, MOST_KILLED):
        for survived in range(1, MOST_SURVIVING):
            results = {"f": counts(killed, survived)}
            _, recorded = evaluate_domain(results, {})
            violations, _ = evaluate_domain(results, recorded)
            if violations:
                refused.append((killed, survived))

    assert refused == []


def test_the_rounding_that_used_to_refuse_38_of_39_no_longer_does() -> None:
    # 100 * 38 / 39 = 97.43589743..., stored as 97.4359, which is above it
    violations, updated = evaluate_domain({"f": counts(38, 1)}, {"f": STORED_AT_97})

    assert violations == []
    assert updated == {"f": STORED_AT_97}


def test_a_drop_that_is_real_is_still_refused_and_the_message_shows_the_decimals() -> None:
    violations, _ = evaluate_domain({"f": ONE_MORE_SURVIVOR}, {"f": STORED_AT_97})

    assert len(violations) == 1
    assert "from 97.44% to 97.22%" in violations[0]


def test_a_percentage_is_shown_with_the_decimals_it_needs_and_no_more() -> None:
    assert [ratchet._pct(60.0), ratchet._pct(STORED_AT_97), ratchet._pct(97.0)] == [
        "60%",
        "97.44%",
        "97%",
    ]
