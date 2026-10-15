"""Steps for ci_timings.feature: the history report, the stage trace, the mutation costs."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import ci_history
import gate_timing
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("ci_timings.feature")

SECONDS_PER_MINUTE = 60


@pytest.fixture
def world(tmp_path):
    return SimpleNamespace(root=tmp_path, jobs={}, stats={}, report="")


def stamp(seconds: int) -> str:
    return f"2026-10-01T{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}Z"


@given(
    parsers.parse(
        'a workflow history where "{slow}" took {a:d} minutes and "{quick}" took {b:d} minute'
    )
)
def _history(world, slow, a, quick, b) -> None:
    world.jobs = {slow: a * SECONDS_PER_MINUTE, quick: b * SECONDS_PER_MINUTE}


@when("the history is analysed")
def _analyse(world) -> None:
    jobs = [
        {
            "name": name,
            "started_at": stamp(0),
            "completed_at": stamp(took),
            "conclusion": "success",
            "steps": [],
        }
        for name, took in world.jobs.items()
    ]
    run = {"run_started_at": stamp(0), "updated_at": stamp(max(world.jobs.values()))}
    world.report = ci_history.render(ci_history.summarize([{"run": run, "jobs": jobs}]))


@then(parsers.parse('the report lists "{first}" before "{second}"'))
def _order(world, first, second) -> None:
    assert world.report.index(f"| {first} |") < world.report.index(f"| {second} |")


@then(parsers.parse('the report says "{job}" takes {share} of the job time'))
def _share(world, job, share) -> None:
    assert f"| {job} | 1 |" in world.report
    assert share in world.report


@given("the timings file is named in the environment")
def _file(world, monkeypatch) -> None:
    world.timings = world.root / "timings.jsonl"
    monkeypatch.setenv(gate_timing.ENV_VAR, str(world.timings))


@when("a gate times a slow stage and a quick stage")
def _stages(world) -> None:
    with gate_timing.step("quick"):
        pass
    with gate_timing.step("slow"):
        time.sleep(0.02)
    world.report = gate_timing.render_steps(gate_timing.read_records(world.timings))


@then("the rendered report lists the slow stage first")
def _slow_first(world) -> None:
    assert world.report.index("| slow |") < world.report.index("| quick |")


@given("mutmut recorded a 4 second test and a half second test for one function")
def _stats(world) -> None:
    world.stats = {
        "duration_by_test": {"t::a": 4.0, "t::b": 0.5},
        "tests_by_mangled_function_name": {"m.x_f__mutmut": ["t::a", "t::b"]},
    }
    (world.root / "mutmut-stats.json").write_text(json.dumps(world.stats))


@when("the mutation costs are asked for")
def _costs(world, capsys) -> None:
    gate_timing.main(["mutants", "--mutants-dir", str(world.root)])
    world.report = capsys.readouterr().out


@then("the function costs 4.5 seconds per mutant")
def _cost(world) -> None:
    assert "| m.x_f__mutmut | 4.50 |" in world.report


@given("a mutation plan that needs a second pass")
def _two_passes(world, monkeypatch) -> None:
    import mutation_plan

    decided = mutation_plan.Plan(mode="incremental", needs_second_pass=True)
    monkeypatch.setattr(mutation_plan, "collect_inputs", lambda *_: (None, [], []))
    monkeypatch.setattr(mutation_plan, "plan", lambda _inputs: decided)
    monkeypatch.setattr(mutation_plan, "apply", lambda *_: 0)
    monkeypatch.setattr(mutation_plan, "record_domain", lambda *_, **__: None)
    monkeypatch.setattr(mutation_plan, "_mutmut_run", lambda _root: 0)


@when("the mutation run executes")
def _mutation_run(world) -> None:
    import mutation_plan

    mutation_plan.run(world.root, "main", world.root / "mutants")


@then(parsers.parse('the trace names the stages "{first}" and "{second}"'))
def _trace(world, first, second) -> None:
    names = [r[gate_timing.NAME] for r in gate_timing.read_records(world.timings)]
    assert first in names
    assert second in names
