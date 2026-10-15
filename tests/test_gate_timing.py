"""gate_timing.py: the stage trace, its report, and the cost of each mutation test."""

from __future__ import annotations

import json
import time

import gate_timing as gt
import pytest

TIMINGS, FAST, SLOW = "t.jsonl", "t::fast", "t::slow"
STATS = {
    "duration_by_test": {FAST: 0.5, SLOW: 4.0, "t::mid": 1.5},
    "tests_by_mangled_function_name": {
        "m.x_a__mutmut": [FAST, SLOW],
        "m.x_b__mutmut": ["t::mid"],
    },
}


def test_a_step_prints_its_duration_to_stderr(capsys, monkeypatch) -> None:
    monkeypatch.delenv(gt.ENV_VAR, raising=False)

    with gt.step("plan"):
        pass

    err = capsys.readouterr().err
    assert err.startswith("⏱ plan: 0.0s")


def test_a_step_appends_a_json_line_when_the_file_is_named(tmp_path, monkeypatch) -> None:
    target = tmp_path / TIMINGS
    monkeypatch.setenv(gt.ENV_VAR, str(target))

    with gt.step("one"):
        time.sleep(0.01)
    with gt.step("two"):
        pass

    records = [json.loads(line) for line in target.read_text().splitlines()]
    assert [r["name"] for r in records] == ["one", "two"]
    assert records[0][gt.SECONDS] >= 0.01


def test_a_failing_step_is_still_timed_and_the_error_propagates(tmp_path, monkeypatch) -> None:
    target = tmp_path / TIMINGS
    monkeypatch.setenv(gt.ENV_VAR, str(target))

    with pytest.raises(ValueError), gt.step("boom"):
        raise ValueError

    assert json.loads(target.read_text())["name"] == "boom"


def test_nothing_is_written_without_the_variable(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(gt.ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)

    gt.record("x", 1.0)

    assert list(tmp_path.iterdir()) == []


def test_a_missing_timings_file_reads_as_no_measurements(tmp_path) -> None:
    assert gt.read_records(tmp_path / "absent.jsonl") == []


def test_the_report_lists_the_slowest_step_first_with_its_share() -> None:
    records = [{"name": "small", gt.SECONDS: 1.0}, {"name": "big", gt.SECONDS: 3.0}]

    lines = gt.render_steps(records).splitlines()

    assert lines[0] == "**Gate steps, 4.0s in all**"
    assert lines[4] == "| big | 3.0s | 75% |"
    assert lines[5] == "| small | 1.0s | 25% |"


def test_the_report_says_so_when_nothing_was_timed() -> None:
    assert gt.render_steps([]) == "No gate steps were timed."


def test_a_functions_cost_is_the_time_of_the_tests_that_cover_it() -> None:
    tests, functions = gt.mutation_costs(STATS)

    assert tests[0] == (SLOW, 4.0)
    assert functions == [("m.x_a__mutmut", 4.5), ("m.x_b__mutmut", 1.5)]


def test_the_mutation_report_keeps_only_the_top_rows() -> None:
    text = gt.render_mutation_costs(STATS, top=1)

    assert "| t::slow | 4.00 |" in text
    assert FAST not in text
    assert "| m.x_a__mutmut | 4.50 |" in text


def test_without_recorded_durations_the_report_says_to_run_mutmut() -> None:
    assert "run `mutmut run` first" in gt.render_mutation_costs({}, top=5)


def test_the_cli_renders_a_timings_file(tmp_path, capsys) -> None:
    target = tmp_path / TIMINGS
    target.write_text(json.dumps({"name": "only", gt.SECONDS: 2.0}) + "\n")

    assert gt.main(["report", str(target)]) == 0
    assert "| only | 2.0s | 100% |" in capsys.readouterr().out


def test_the_cli_reads_mutmuts_stats(tmp_path, capsys) -> None:
    (tmp_path / "mutmut-stats.json").write_text(json.dumps(STATS))

    assert gt.main(["mutants", "--mutants-dir", str(tmp_path), "--top", "2"]) == 0
    assert SLOW in capsys.readouterr().out
