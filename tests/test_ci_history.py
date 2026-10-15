"""ci_history.py: what a workflow's recent runs say about where its time goes."""

from __future__ import annotations

import json

import ci_history as ch

PYTEST, SETUP = "pytest", "setup"
TWO_AND_A_HALF_MINUTES, TWO_MINUTES = 150.0, 120.0


def at(minute: int, second: int = 0) -> str:
    return f"2026-10-01T10:{minute:02d}:{second:02d}Z"


def span(name, start, end, conclusion="success"):
    return {"name": name, "started_at": start, "completed_at": end, "conclusion": conclusion}


def job(name, start, end, steps=(), conclusion="success"):
    return {**span(name, start, end, conclusion), "steps": [span(*step) for step in steps]}


def entry(jobs, start=None, end=None):
    return {"run": {"run_started_at": start, "updated_at": end}, "jobs": jobs}


def test_seconds_between_two_times() -> None:
    assert ch.seconds_between(at(0), at(2, 30)) == TWO_AND_A_HALF_MINUTES


def test_a_missing_time_is_no_duration() -> None:
    assert ch.seconds_between(None, at(1)) is None
    assert ch.seconds_between(at(1), None) is None


def test_a_negative_span_is_clamped_to_zero() -> None:
    assert ch.seconds_between(at(5), at(4)) == 0.0


def test_percentile_is_the_nearest_rank() -> None:
    values = [float(n) for n in range(1, 11)]

    assert (ch.percentile(values, 0.9), ch.percentile([4.0], 0.9)) == (9.0, 4.0)


def test_a_skipped_job_is_not_counted() -> None:
    skipped = job("lint", at(0), at(1), conclusion="skipped")

    assert ch.job_seconds(skipped) is None


def test_a_run_consumes_each_job_rounded_up_to_a_minute() -> None:
    jobs = [job("a", at(0), at(0, 10)), job("b", at(0), at(2, 1))]

    assert ch.run_job_minutes(entry(jobs)) == 1 + 3


def test_the_summary_gives_each_job_and_step_median_and_p90() -> None:
    history = [
        entry(
            [job("test", at(0), at(10), [(PYTEST, at(1), at(9)), (SETUP, at(0), at(1))])],
            start=at(0),
            end=at(11),
        ),
        entry(
            [job("test", at(0), at(6), [(PYTEST, at(1), at(5)), (SETUP, at(0), at(1))])],
            start=at(0),
            end=at(7),
        ),
    ]

    summary = ch.summarize(history)

    tested = summary.jobs["test"]
    assert (summary.runs, summary.wall_clock.median, summary.job_minutes.median) == (2, 540.0, 8.0)
    assert (tested.stats.median, tested.steps[PYTEST].p90) == (480.0, 480.0)
    assert tested.steps[SETUP].total == TWO_MINUTES


def test_skipped_steps_are_ignored() -> None:
    item = job("t", at(0), at(2), [("kept", at(0), at(1))])
    item["steps"].append(span("cut", at(1), at(2), "skipped"))

    assert set(ch.summarize([entry([item])]).jobs["t"].steps) == {"kept"}


def test_the_report_orders_jobs_by_their_share_of_the_time() -> None:
    history = [
        entry(
            [
                job("small", at(0), at(1), [("s", at(0), at(1))]),
                job("big", at(0), at(9), [("b", at(0), at(9))]),
            ],
            start=at(0),
            end=at(9),
        )
    ]

    lines = ch.render(ch.summarize(history)).splitlines()

    expected = "**1 runs.** Wall clock: median 9m00s, p90 9m00s."
    assert lines[0] == f"{expected} Job minutes per run: median 10, p90 10."
    assert lines[4] == "| big | 1 | 9m00s | 9m00s | 90% |"
    assert lines[5] == "| small | 1 | 1m00s | 1m00s | 10% |"


def test_the_heaviest_steps_are_cut_to_top() -> None:
    steps = [(f"s{n}", at(0), at(n + 1)) for n in range(4)]
    history = [entry([job("j", at(0), at(9), steps)])]

    text = ch.render(ch.summarize(history), top=2)

    assert "| j | s3 |" in text
    assert "| j | s2 |" in text
    assert "| j | s0 |" not in text


def test_no_runs_says_so() -> None:
    assert ch.render(ch.summarize([])) == "No completed runs to analyse."


def test_the_cli_analyses_a_saved_history_and_needs_no_network(tmp_path, capsys) -> None:
    saved = tmp_path / "h.json"
    saved.write_text(json.dumps([entry([job("j", at(0), at(1))], start=at(0), end=at(1))]))

    assert ch.main(["--from-json", str(saved)]) == 0
    assert "| j | 1 | 1m00s |" in capsys.readouterr().out


def test_fetch_asks_for_the_runs_then_the_jobs_of_each(monkeypatch) -> None:
    asked = []

    def fake(*args):
        asked.append(args[1])
        if "workflows" in args[1]:
            return {"workflow_runs": [{"id": 7}]}
        return {"jobs": [{"name": "j"}]}

    monkeypatch.setattr(ch, "gh_json", fake)

    history = ch.fetch("o/r", "ci.yml", 5, "main")

    assert asked == [
        "repos/o/r/actions/workflows/ci.yml/runs?status=completed&per_page=5&branch=main",
        "repos/o/r/actions/runs/7/jobs?per_page=100",
    ]
    assert history == [{"run": {"id": 7}, "jobs": [{"name": "j"}]}]
