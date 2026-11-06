"""The mutation ratchet's acceptance rule, behaviourally.

A touched function is accepted when it scores at least the threshold (80%), and refused below it.
There is one bar and nothing stored: the rule has no memory of an earlier score.
"""

from __future__ import annotations

import importlib.util
import json
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


def test_a_function_with_mutants_that_have_no_verdict_is_refused() -> None:
    results = {"f": {"killed": 9, "survived": 0, "no_tests": 0, "other": 0, "pending": 3}}

    violations = evaluate(results)

    assert violations == [
        "f: 3 mutant(s) have no verdict (the run was interrupted, or a test failed to collect)"
    ]


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


# -- judging the mutants mutation_run.py chose --------------------------------------------

MODULE = "pkg/mod.py"
MUTANTS = "mutants"
ERROR_STATUS = 2
SELECTION_KEY = "mutants"
KILLED, SURVIVED = 1, 0
CHOSEN = "pkg.mod.x_f__mutmut_1"
LEFT_OUT = "pkg.mod.x_f__mutmut_2"
SELECTION = "mutation-selection.json"


def record(mutants_dir: Path, outcomes: dict[str, int | None]) -> None:
    """What mutmut keeps for a file: the exit code of each of its mutants."""
    target = mutants_dir / f"{MODULE}.meta"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"exit_code_by_key": outcomes}))


def test_only_the_chosen_mutants_are_judged(tmp_path) -> None:
    record(tmp_path, {CHOSEN: KILLED, LEFT_OUT: SURVIVED})

    results = ratchet.collect_selected_results(tmp_path, {CHOSEN})

    assert results == {f"{MODULE}::f": {**ratchet._no_outcomes(), "killed": 1}}


def test_a_survivor_that_was_not_chosen_does_not_fail_the_function(tmp_path) -> None:
    record(tmp_path, {CHOSEN: KILLED, LEFT_OUT: SURVIVED})

    results = ratchet.collect_selected_results(tmp_path, {CHOSEN})

    assert evaluate(results) == []


def test_a_chosen_mutant_that_was_never_tested_refuses_its_function(tmp_path) -> None:
    record(tmp_path, {CHOSEN: None, LEFT_OUT: KILLED})

    results = ratchet.collect_selected_results(tmp_path, {CHOSEN})

    assert "1 mutant(s) have no verdict" in evaluate(results)[0]


def test_no_selection_file_means_a_plain_mutmut_run(tmp_path) -> None:
    assert ratchet.load_selection(tmp_path) is None


def test_the_selection_file_names_the_chosen_mutants(tmp_path) -> None:
    (tmp_path / SELECTION).write_text(json.dumps({SELECTION_KEY: [CHOSEN]}))

    assert ratchet.load_selection(tmp_path) == {CHOSEN}


@pytest.mark.parametrize("content", ["not json", "{}", f'{{"{SELECTION_KEY}": 3}}'])
def test_a_selection_file_that_cannot_be_read_is_an_error_not_a_fallback(tmp_path, content) -> None:
    (tmp_path / SELECTION).write_text(content)

    with pytest.raises(ratchet.SelectionError, match="run scripts/mutation_run.py again"):
        ratchet.load_selection(tmp_path)


def test_the_ratchet_stops_with_an_error_status_on_an_unreadable_selection(
    tmp_path, capsys
) -> None:
    (tmp_path / MUTANTS).mkdir()
    (tmp_path / MUTANTS / SELECTION).write_text("not json")

    status = ratchet.main(["--base", "HEAD", "--path", str(tmp_path)])

    assert status == ERROR_STATUS
    assert "not a mutation selection" in capsys.readouterr().err


def test_an_empty_selection_has_nothing_to_judge(tmp_path, capsys) -> None:
    (tmp_path / MUTANTS).mkdir()
    (tmp_path / MUTANTS / SELECTION).write_text(json.dumps({SELECTION_KEY: []}))

    status = ratchet.main(["--base", "HEAD", "--path", str(tmp_path)])

    assert status == 0
    assert "nothing to judge" in capsys.readouterr().out
