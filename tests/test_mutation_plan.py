"""What a change invalidates in the mutation cache, and nothing more.

mutmut tracks production functions by hash but cannot see what a test, a fixture, a data file or an
unmutated helper does to a verdict. The planner decides, from the diff and mutmut's own stats, which
cached verdicts to drop so a normal `mutmut run` re-tests exactly those.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "mutation_plan", ROOT / "scripts" / "mutation_plan.py"
)
assert _SPEC and _SPEC.loader
mp = importlib.util.module_from_spec(_SPEC)
sys.modules["mutation_plan"] = mp  # dataclasses look their module up here
_SPEC.loader.exec_module(mp)

LOAD = "ster.store._load_save.x_load"
PROMOTE = "ster.store._load_save.x__promote_one"
CTX = "ster.mcp_context.x_overview"
SERVER = "ster.mcp_server.x_handle_message"

STATS = {
    "tests_by_mangled_function_name": {
        LOAD: ["tests/unit/test_files.py::test_a", "tests/unit/test_ctx.py::test_c"],
        PROMOTE: ["tests/unit/test_promote.py::test_p1", "tests/unit/test_promote.py::test_p2"],
        CTX: ["tests/unit/test_ctx.py::test_c", "tests/unit/test_ctx.py::test_d"],
        SERVER: ["tests/unit/test_server.py::test_s"],
    },
    "duration_by_test": {
        "tests/unit/test_files.py::test_a": 0.1,
        "tests/unit/test_ctx.py::test_c": 0.1,
        "tests/unit/test_ctx.py::test_d": 0.1,
        "tests/unit/test_promote.py::test_p1": 0.1,
        "tests/unit/test_promote.py::test_p2": 0.1,
        "tests/unit/test_server.py::test_s": 0.1,
    },
}

INCREMENTAL = "incremental"
TWO_PASSES, MUTMUT_FAILED = 2, 3
SELECTION = (
    "tests/unit/test_files.py",
    "tests/unit/test_ctx.py",
    "tests/unit/test_promote.py",
    "tests/unit/test_server.py",
)
RESET_VERDICTS = 2
MAP_FEATURE = "tests/features/viz/map.feature"
MUTATED = ("ster/store/_load_save.py", "ster/mcp_context.py", "ster/mcp_server.py")


def make(changes, **overrides):
    """Plan for `changes`; `overrides` replace any of the defaults below."""
    given = {"stats": STATS, "sources": None, "sections": (), "selection": SELECTION, **overrides}
    old_selection = overrides.get("old_selection") or SELECTION
    return mp.plan(
        mp.Inputs(
            changes=tuple(changes),
            mutated_files=frozenset(MUTATED),
            selection=mp.Selection(tuple(given["selection"]), tuple(old_selection)),
            stats=given["stats"],
            sources=given["sources"] or {},
            changed_sections=tuple(given["sections"]),
            keep_on_dependency_change=bool(overrides.get("keep")),
        )
    )


# -- first initialisation and cache-wide causes -----------------------------------


def test_no_cache_means_a_full_initialisation() -> None:
    plan = make([("M", "ster/x.py")], stats=None)

    assert plan.mode == "init"
    assert "no mutation cache" in plan.reasons[0]


def test_a_lock_file_change_means_a_full_rerun() -> None:
    plan = make([("M", "uv.lock")])

    assert plan.mode == "full"
    assert "uv.lock" in plan.reasons[0]


def test_a_dependency_section_change_means_a_full_rerun() -> None:
    plan = make([("M", "pyproject.toml")], sections=["project.dependencies"])

    assert plan.mode == "full"
    assert "project.dependencies" in plan.reasons[0]


def test_a_lock_file_change_keeps_the_cache_when_the_repo_says_so() -> None:
    plan = make([("M", "uv.lock")], keep=True)

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == ()


def test_a_dependency_section_change_keeps_the_cache_when_the_repo_says_so() -> None:
    plan = make([("M", "pyproject.toml")], sections=["project.dependencies"], keep=True)

    assert plan.mode == INCREMENTAL


def test_keeping_the_cache_on_a_dependency_change_does_not_hide_a_test_setup_change() -> None:
    assert make([("M", "pytest.ini")], keep=True).mode == "full"
    assert make([("M", "tests/conftest.py")], keep=True).mode == "full"
    assert make([("M", "pyproject.toml")], sections=["tool.pytest"], keep=True).mode == "full"


def test_a_pyproject_change_outside_the_watched_sections_costs_nothing() -> None:
    plan = make([("M", "pyproject.toml")], sections=[])

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == ()


def test_a_root_conftest_change_affects_every_test() -> None:
    plan = make([("M", "conftest.py")])

    assert plan.mode == "full"


# -- a changed test re-tests the functions it covers, and only those --------------


def test_a_changed_test_file_resets_only_the_functions_it_covers() -> None:
    plan = make([("M", "tests/unit/test_promote.py")])

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == (PROMOTE,)
    assert set(plan.stale_tests) == {
        "tests/unit/test_promote.py::test_p1",
        "tests/unit/test_promote.py::test_p2",
    }


def test_a_test_covering_two_functions_resets_both() -> None:
    plan = make([("M", "tests/unit/test_ctx.py")])

    assert plan.reset_functions == tuple(sorted((CTX, LOAD)))


def test_two_changed_test_files_reset_the_union() -> None:
    plan = make([("M", "tests/unit/test_promote.py"), ("M", "tests/unit/test_server.py")])

    assert plan.reset_functions == tuple(sorted((PROMOTE, SERVER)))


def test_a_deleted_test_file_resets_what_it_used_to_cover() -> None:
    plan = make([("D", "tests/unit/test_promote.py")])

    assert plan.reset_functions == (PROMOTE,)


def test_a_new_test_file_is_unknown_to_the_stats_so_nothing_is_reset_yet() -> None:
    plan = make(
        [("A", "tests/unit/test_new.py")],
        selection=(*SELECTION, "tests/unit/test_new.py"),
    )

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == ()
    assert plan.selection_added == ("tests/unit/test_new.py",)
    assert plan.needs_second_pass is True


def test_a_test_file_outside_the_selection_changes_nothing() -> None:
    plan = make([("M", "tests/integration/test_other.py")])

    assert plan.reset_functions == ()
    assert plan.stale_tests == ()


# -- test support: fixtures, helpers, conftest, data ------------------------------


def test_a_helper_resets_the_tests_that_import_it() -> None:
    plan = make(
        [("M", "tests/helpers.py")],
        sources={
            "tests/unit/test_server.py": "from helpers import build\n",
            "tests/unit/test_files.py": "import os\n",
        },
    )

    assert plan.reset_functions == (SERVER,)


def test_a_helper_is_found_through_a_package_style_import() -> None:
    plan = make(
        [("M", "tests/helpers.py")],
        sources={"tests/unit/test_server.py": "from tests.helpers import build\n"},
    )

    assert plan.reset_functions == (SERVER,)


def test_a_nested_conftest_resets_the_tests_beneath_it() -> None:
    plan = make([("M", "tests/unit/conftest.py")])

    assert set(plan.reset_functions) == {LOAD, PROMOTE, CTX, SERVER}


def test_a_nested_conftest_leaves_tests_elsewhere_alone() -> None:
    stats = {
        "tests_by_mangled_function_name": {
            LOAD: ["tests/unit/test_files.py::test_a"],
            SERVER: ["tests/other/test_s.py::test_s"],
        },
        "duration_by_test": {},
    }
    plan = make([("M", "tests/unit/conftest.py")], stats=stats)

    assert plan.reset_functions == (LOAD,)


def test_a_data_file_resets_the_tests_that_name_it() -> None:
    plan = make(
        [("M", "tests/fixtures/zoo.ttl")],
        sources={
            "tests/unit/test_promote.py": 'FIXTURE = "tests/fixtures/zoo.ttl"\n',
            "tests/unit/test_server.py": "x = 1\n",
        },
    )

    assert plan.reset_functions == (PROMOTE,)


def test_a_data_file_nobody_names_falls_back_to_the_tests_beside_it() -> None:
    plan = make(
        [("M", "tests/unit/data/zoo.ttl")], sources={"tests/unit/test_server.py": "x = 1\n"}
    )

    assert set(plan.reset_functions) == {LOAD, PROMOTE, CTX, SERVER}
    assert any("zoo.ttl" in r for r in plan.reasons)


def test_a_scenario_no_selected_test_names_resets_nothing() -> None:
    plan = make(
        [("M", "tests/features/core/degraded_inputs.feature")],
        sources={"tests/unit/test_server.py": "x = 1\n"},
    )

    assert plan.reset_functions == ()


def test_a_scenario_is_read_by_the_test_that_names_its_file() -> None:
    plan = make(
        [("M", MAP_FEATURE)],
        sources={"tests/unit/test_promote.py": 'scenarios("../features/viz/map.feature")\n'},
    )

    assert plan.reset_functions == (PROMOTE,)


def test_a_scenario_is_read_by_the_test_that_names_its_folder() -> None:
    plan = make(
        [("M", MAP_FEATURE)],
        sources={"tests/unit/test_server.py": 'scenarios("../features/viz")\n'},
    )

    assert plan.reset_functions == (SERVER,)


def test_a_test_that_binds_the_whole_feature_tree_reads_every_scenario() -> None:
    plan = make(
        [("M", MAP_FEATURE)],
        sources={"tests/unit/test_ctx.py": 'scenarios("../features")\n'},
    )

    assert set(plan.reset_functions) == {LOAD, CTX}


# -- production code mutmut cannot see ---------------------------------------------


def test_a_production_function_in_a_mutated_file_is_left_to_mutmut() -> None:
    plan = make([("M", "ster/store/_load_save.py")])

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == ()


def test_an_unmutated_module_resets_what_the_tests_importing_it_cover() -> None:
    plan = mp.plan(
        mp.Inputs(
            changes=(("M", "ster/util.py"),),
            mutated_files=frozenset(MUTATED),
            selection=mp.Selection(SELECTION, SELECTION),
            stats=STATS,
            sources={"tests/unit/test_server.py": "from ster import util\n"},
            changed_sections=(),
            graph=mp.ImportGraph(
                imports={"ster.mcp_server": {"ster.util"}, "ster.util": set()},
                tests={"tests/unit/test_server.py": {"ster.mcp_server"}},
            ),
        )
    )

    assert plan.reset_functions == (SERVER,)


def test_documentation_and_workflow_changes_cost_nothing() -> None:
    plan = make(
        [("M", "README.md"), ("M", ".github/workflows/ci.yml"), ("M", ".mutation-baseline.json")]
    )

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == ()


# -- selection changes ---------------------------------------------------------------


def test_adding_files_to_the_selection_is_not_a_cache_wide_change() -> None:
    plan = make(
        [("M", "pyproject.toml"), ("A", "tests/unit/test_new.py")],
        selection=(*SELECTION, "tests/unit/test_new.py"),
        sections=["tool.mutmut.pytest_add_cli_args_test_selection"],
    )

    assert plan.mode == INCREMENTAL


def test_removing_files_from_the_selection_resets_what_they_covered() -> None:
    plan = make(
        [("M", "pyproject.toml")],
        selection=tuple(f for f in SELECTION if f != "tests/unit/test_promote.py"),
        sections=["tool.mutmut.pytest_add_cli_args_test_selection"],
    )

    assert plan.mode == INCREMENTAL
    assert plan.reset_functions == (PROMOTE,)


def test_changing_pytest_arguments_is_a_cache_wide_change() -> None:
    plan = make([("M", "pyproject.toml")], sections=["tool.mutmut.pytest_add_cli_args"])

    assert plan.mode == "full"


# -- applying a plan to the cache -----------------------------------------------------


def test_resetting_functions_clears_only_their_verdicts() -> None:
    meta = {
        "exit_code_by_key": {
            "ster.store._load_save.x__promote_one__mutmut_1": 1,
            "ster.store._load_save.x__promote_one__mutmut_2": 0,
            "ster.store._load_save.x_load__mutmut_1": 1,
        }
    }

    count = mp.reset_verdicts(meta, {PROMOTE})

    assert count == RESET_VERDICTS
    assert meta["exit_code_by_key"] == {
        "ster.store._load_save.x__promote_one__mutmut_1": None,
        "ster.store._load_save.x__promote_one__mutmut_2": None,
        "ster.store._load_save.x_load__mutmut_1": 1,
    }


def test_a_function_name_that_prefixes_another_does_not_reset_it() -> None:
    meta = {
        "exit_code_by_key": {
            "m.x_load__mutmut_1": 1,
            "m.x_load_all__mutmut_1": 1,
        }
    }

    assert mp.reset_verdicts(meta, {"m.x_load"}) == 1
    assert meta["exit_code_by_key"]["m.x_load_all__mutmut_1"] == 1


def test_dropping_stale_tests_makes_mutmut_collect_them_again() -> None:
    stats = {
        "tests_by_mangled_function_name": {LOAD: ["a::t1", "a::t2"], CTX: ["b::t3"]},
        "duration_by_test": {"a::t1": 1.0, "a::t2": 2.0, "b::t3": 3.0},
    }

    mp.drop_tests(stats, {"a::t1"})

    assert stats["duration_by_test"] == {"a::t2": 2.0, "b::t3": 3.0}
    assert stats["tests_by_mangled_function_name"][LOAD] == ["a::t2"]
    assert stats["tests_by_mangled_function_name"][CTX] == ["b::t3"]


def test_the_selection_fingerprint_follows_mutmuts_scheme() -> None:
    # sha256 of repr(tuple(values)), 12 hex digits: what mutmut 3.8 stores as "test_selection"
    import hashlib

    values = ["tests/a.py", "-m", "mutation"]
    expected = hashlib.sha256(repr(tuple(values)).encode()).hexdigest()[:12]

    assert mp.selection_fingerprint(values) == expected


# -- re-signing the selection fingerprint ---------------------------------------------


ARGS = ["tests/unit/test_a.py", "tests/unit/test_b.py", "-m", "mutation"]


def stats_with(fingerprint: str, tests: list[str]) -> dict:
    return {
        "config_fingerprint": {"test_selection": fingerprint},
        "duration_by_test": dict.fromkeys(tests, 0.1),
    }


def test_a_cache_built_with_the_current_selection_needs_no_re_signing() -> None:
    stats = stats_with(
        mp.selection_fingerprint(ARGS), ["tests/unit/test_a.py::t", "tests/unit/test_b.py::t"]
    )

    mp.resign_selection(stats, old_args=[], new_args=ARGS)

    assert stats["config_fingerprint"]["test_selection"] == mp.selection_fingerprint(ARGS)


def test_a_selection_that_only_grew_is_re_signed() -> None:
    old = ["tests/unit/test_a.py", "-m", "mutation"]
    stats = stats_with(mp.selection_fingerprint(old), ["tests/unit/test_a.py::t"])

    mp.resign_selection(stats, old_args=old, new_args=ARGS)

    assert stats["config_fingerprint"]["test_selection"] == mp.selection_fingerprint(ARGS)


def test_a_cache_built_before_the_base_selection_is_re_signed_when_the_gap_is_unmeasured() -> None:
    # the cache was built from an earlier commit of the branch: it never saw test_b.py
    built_with = ["tests/unit/test_a.py", "-m", "mutation"]
    stats = stats_with(mp.selection_fingerprint(built_with), ["tests/unit/test_a.py::t"])

    mp.resign_selection(stats, old_args=ARGS, new_args=ARGS)

    assert stats["config_fingerprint"]["test_selection"] == mp.selection_fingerprint(ARGS)


def test_a_cache_built_from_an_older_selection_than_the_base_is_re_signed() -> None:
    built = ["tests/unit/test_a.py", "-m", "mutation"]
    base = ["tests/unit/test_a.py", "tests/unit/test_c.py", "-m", "mutation"]
    stats = stats_with(mp.selection_fingerprint(built), ["tests/unit/test_a.py::t"])

    mp.resign_selection(stats, old_args=base, new_args=ARGS, built_args=built)

    assert stats["config_fingerprint"]["test_selection"] == mp.selection_fingerprint(ARGS)


def test_the_selection_the_cache_was_built_from_is_read_at_its_commit(tmp_path) -> None:
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=tmp_path, check=True, capture_output=True, text=True,
        ).stdout.strip()  # fmt: skip

    git("init", "-q", "-b", "main")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\npytest_add_cli_args_test_selection = ["tests/a.py", "-m", "mutation"]\n'
    )
    git("add", "pyproject.toml")
    git("commit", "-q", "-m", "built here")
    (tmp_path / "pyproject.toml").write_text("[tool.mutmut]\n")
    mutants = tmp_path / MUTANTS
    mutants.mkdir()
    (mutants / "mutmut-stats.json").write_text(json.dumps({"git_commit": git("rev-parse", "HEAD")}))

    assert mp.built_selection(tmp_path, mutants) == ["tests/a.py", "-m", "mutation"]


def test_a_cache_with_no_known_commit_has_no_built_selection(tmp_path) -> None:
    (tmp_path / MUTANTS).mkdir()

    assert mp.built_selection(tmp_path, tmp_path / MUTANTS) == []
    (tmp_path / MUTANTS / "mutmut-stats.json").write_text(json.dumps({"git_commit": "0" * 40}))
    assert mp.built_selection(tmp_path, tmp_path / MUTANTS) == []


def test_a_fingerprint_that_matches_no_known_selection_is_refused() -> None:
    stats = stats_with("deadbeef0000", ["tests/unit/test_a.py::t", "tests/unit/test_b.py::t"])

    try:
        mp.resign_selection(stats, old_args=["x.py"], new_args=ARGS)
    except mp.CacheFormatError:
        return
    raise AssertionError("expected CacheFormatError")


def test_the_summary_names_the_new_test_files_it_will_measure() -> None:
    plan = make(
        [("A", "tests/unit/test_new.py")],
        selection=(*SELECTION, "tests/unit/test_new.py"),
    )

    assert "  new test file(s): tests/unit/test_new.py" in mp.summary(plan).splitlines()


def test_the_summary_has_no_new_test_line_without_new_test_files() -> None:
    assert "new test file(s)" not in mp.summary(make([("M", "tests/integration/test_other.py")]))


# -- preparing the cache and running mutmut, with the stages timed -------------------------------

MUTANTS = "mutants"
RUN_MUTMUT, APPLY, RECORD = "_mutmut_run", "apply", "record"


def stub_planning(monkeypatch, tmp_path, decided):
    """collect_inputs/plan/apply/record_domain replaced; returns the calls apply and record saw."""
    seen = {APPLY: 0, RECORD: []}
    monkeypatch.setattr(mp, "collect_inputs", lambda *_: (None, ["old"], ["new"]))
    monkeypatch.setattr(mp, "plan", lambda _inputs: decided)

    def fake_apply(*_args):
        seen[APPLY] += 1
        return 3

    monkeypatch.setattr(mp, APPLY, fake_apply)
    monkeypatch.setattr(
        mp, "record_domain", lambda _dir, functions, *, fresh: seen[RECORD].append(fresh)
    )
    (tmp_path / MUTANTS).mkdir()
    return seen


def test_a_full_plan_clears_the_cache(monkeypatch, tmp_path) -> None:
    stub_planning(monkeypatch, tmp_path, mp.Plan(mode="full"))

    mp._prepare(tmp_path, "main", tmp_path / MUTANTS, 1)

    assert not (tmp_path / MUTANTS).exists()


def test_an_initial_plan_leaves_the_cache_alone(monkeypatch, tmp_path) -> None:
    seen = stub_planning(monkeypatch, tmp_path, mp.Plan(mode="init"))

    mp._prepare(tmp_path, "main", tmp_path / MUTANTS, 1)

    assert (tmp_path / MUTANTS).exists()
    assert seen == {APPLY: 0, RECORD: []}


def test_an_incremental_plan_drops_verdicts_and_records_the_domain(
    monkeypatch, tmp_path, capsys
) -> None:
    seen = stub_planning(monkeypatch, tmp_path, mp.Plan(mode=INCREMENTAL))

    mp._prepare(tmp_path, "main", tmp_path / MUTANTS, 1)
    mp._prepare(tmp_path, "main", tmp_path / MUTANTS, 2)

    assert seen == {APPLY: 2, RECORD: [True, False]}
    assert "dropped 3 cached verdict(s)" in capsys.readouterr().out


def test_the_stages_of_a_run_are_timed_in_order(monkeypatch, tmp_path) -> None:
    timings = tmp_path / "timings.jsonl"
    monkeypatch.setenv("CRAFT_GATE_TIMINGS", str(timings))
    stub_planning(monkeypatch, tmp_path, mp.Plan(mode=INCREMENTAL, needs_second_pass=True))
    runs = []
    monkeypatch.setattr(mp, RUN_MUTMUT, lambda root: runs.append(root) or 0)

    code = mp.run(tmp_path, "main", tmp_path / MUTANTS)

    names = [json.loads(line)["name"] for line in timings.read_text().splitlines()]
    assert code == 0
    assert len(runs) == TWO_PASSES
    assert names == [
        "mutation plan: read the repo and decide",
        f"mutation plan: prepare the cache ({INCREMENTAL})",
        "mutmut run (pass 1)",
        "mutation plan: read the repo and decide",
        f"mutation plan: prepare the cache ({INCREMENTAL})",
        "mutmut run (pass 2)",
    ]


def test_a_failing_mutmut_run_is_not_repeated(monkeypatch, tmp_path) -> None:
    stub_planning(monkeypatch, tmp_path, mp.Plan(mode=INCREMENTAL, needs_second_pass=True))
    codes = iter([3, 0])
    monkeypatch.setattr(mp, RUN_MUTMUT, lambda _root: next(codes))

    assert mp.run(tmp_path, "main", tmp_path / MUTANTS) == MUTMUT_FAILED


def test_a_planning_failure_falls_back_to_a_full_run(monkeypatch, tmp_path, capsys) -> None:
    stub_planning(monkeypatch, tmp_path, mp.Plan(mode=INCREMENTAL))
    monkeypatch.setattr(mp, "collect_inputs", lambda *_: 1 / 0)
    runs = []
    monkeypatch.setattr(mp, RUN_MUTMUT, lambda root: runs.append(root) or 0)

    assert mp.run(tmp_path, "main", tmp_path / MUTANTS) == 0
    assert len(runs) == 1
    assert not (tmp_path / MUTANTS).exists()
    assert "running in full" in capsys.readouterr().err


# -- the second pass only measures what the first could not ------------------------------------


def test_the_second_pass_looks_only_at_the_test_files_just_measured() -> None:
    inputs = mp.Inputs(
        changes=(("M", "ster/api.py"), ("A", "tests/unit/test_new.py")),
        mutated_files=frozenset(MUTATED),
        selection=mp.Selection(SELECTION, SELECTION),
        stats=STATS,
    )

    narrowed = mp._measured_now(inputs, ("tests/unit/test_new.py",))

    assert narrowed.changes == (("A", "tests/unit/test_new.py"),)
    assert narrowed.stats is STATS


def test_the_second_pass_does_not_drop_again_what_the_first_one_re_tested(
    monkeypatch, tmp_path
) -> None:
    seen = []
    first = mp.Plan(
        mode=INCREMENTAL, selection_added=("tests/unit/test_new.py",), needs_second_pass=True
    )
    inputs = mp.Inputs(
        changes=(("M", "ster/api.py"), ("A", "tests/unit/test_new.py")),
        mutated_files=frozenset(MUTATED),
        selection=mp.Selection(SELECTION, SELECTION),
        stats=STATS,
    )
    monkeypatch.setattr(mp, "collect_inputs", lambda *_: (inputs, [], []))
    monkeypatch.setattr(mp, "plan", lambda given: seen.append(given.changes) or first)
    monkeypatch.setattr(mp, "apply", lambda *_: 0)
    monkeypatch.setattr(mp, "record_domain", lambda *_a, **_k: None)
    (tmp_path / MUTANTS).mkdir()

    mp._prepare(tmp_path, "main", tmp_path / MUTANTS, 1)
    mp._prepare(tmp_path, "main", tmp_path / MUTANTS, 2, ("tests/unit/test_new.py",))

    assert seen == [inputs.changes, (("A", "tests/unit/test_new.py"),)]


def test_a_run_hands_the_second_pass_the_files_the_first_one_added(monkeypatch, tmp_path) -> None:
    passes = []
    first = mp.Plan(
        mode=INCREMENTAL, selection_added=("tests/unit/test_new.py",), needs_second_pass=True
    )
    monkeypatch.setattr(
        mp,
        "_prepare",
        lambda _r, _b, _d, attempt, measured=(): passes.append((attempt, measured)) or first,
    )
    monkeypatch.setattr(mp, RUN_MUTMUT, lambda _root: 0)

    mp.run(tmp_path, "main", tmp_path / MUTANTS)

    assert passes == [(1, ()), (2, ("tests/unit/test_new.py",))]
