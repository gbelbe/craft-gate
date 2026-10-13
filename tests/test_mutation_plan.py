#!/usr/bin/env python3
"""What a change invalidates in the mutation cache, and nothing more (no pytest dependency).

mutmut tracks production functions by hash but cannot see what a test, a fixture, a data file or an
unmutated helper does to a verdict. The planner decides, from the diff and mutmut's own stats, which
cached verdicts to drop so a normal `mutmut run` re-tests exactly those.
"""

from __future__ import annotations

import importlib.util
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

SELECTION = (
    "tests/unit/test_files.py",
    "tests/unit/test_ctx.py",
    "tests/unit/test_promote.py",
    "tests/unit/test_server.py",
)
MUTATED = ("ster/store/_load_save.py", "ster/mcp_context.py", "ster/mcp_server.py")


def make(
    changes, *, stats=STATS, sources=None, sections=(), selection=SELECTION, old_selection=None
):
    return mp.plan(
        mp.Inputs(
            changes=tuple(changes),
            mutated_files=frozenset(MUTATED),
            selection=tuple(selection),
            old_selection=tuple(SELECTION if old_selection is None else old_selection),
            stats=stats,
            sources=sources or {},
            changed_sections=tuple(sections),
            all_modules=frozenset(),
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


def test_a_pyproject_change_outside_the_watched_sections_costs_nothing() -> None:
    plan = make([("M", "pyproject.toml")], sections=[])

    assert plan.mode == "incremental"
    assert plan.reset_functions == ()


def test_a_root_conftest_change_affects_every_test() -> None:
    plan = make([("M", "conftest.py")])

    assert plan.mode == "full"


# -- a changed test re-tests the functions it covers, and only those --------------


def test_a_changed_test_file_resets_only_the_functions_it_covers() -> None:
    plan = make([("M", "tests/unit/test_promote.py")])

    assert plan.mode == "incremental"
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

    assert plan.mode == "incremental"
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


# -- production code mutmut cannot see ---------------------------------------------


def test_a_production_function_in_a_mutated_file_is_left_to_mutmut() -> None:
    plan = make([("M", "ster/store/_load_save.py")])

    assert plan.mode == "incremental"
    assert plan.reset_functions == ()


def test_an_unmutated_module_resets_what_the_tests_importing_it_cover() -> None:
    plan = mp.plan(
        mp.Inputs(
            changes=(("M", "ster/util.py"),),
            mutated_files=frozenset(MUTATED),
            selection=SELECTION,
            old_selection=SELECTION,
            stats=STATS,
            sources={"tests/unit/test_server.py": "from ster import util\n"},
            changed_sections=(),
            all_modules=frozenset({"ster.util", "ster.mcp_server"}),
            imports={"ster.mcp_server": {"ster.util"}, "ster.util": set()},
            test_modules={"tests/unit/test_server.py": {"ster.mcp_server"}},
        )
    )

    assert plan.reset_functions == (SERVER,)


def test_documentation_and_workflow_changes_cost_nothing() -> None:
    plan = make(
        [("M", "README.md"), ("M", ".github/workflows/ci.yml"), ("M", ".mutation-baseline.json")]
    )

    assert plan.mode == "incremental"
    assert plan.reset_functions == ()


# -- selection changes ---------------------------------------------------------------


def test_adding_files_to_the_selection_is_not_a_cache_wide_change() -> None:
    plan = make(
        [("M", "pyproject.toml"), ("A", "tests/unit/test_new.py")],
        selection=(*SELECTION, "tests/unit/test_new.py"),
        sections=["tool.mutmut.pytest_add_cli_args_test_selection"],
    )

    assert plan.mode == "incremental"


def test_removing_files_from_the_selection_resets_what_they_covered() -> None:
    plan = make(
        [("M", "pyproject.toml")],
        selection=tuple(f for f in SELECTION if f != "tests/unit/test_promote.py"),
        sections=["tool.mutmut.pytest_add_cli_args_test_selection"],
    )

    assert plan.mode == "incremental"
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

    assert count == 2
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


def test_a_fingerprint_that_matches_no_known_selection_is_refused() -> None:
    stats = stats_with("deadbeef0000", ["tests/unit/test_a.py::t", "tests/unit/test_b.py::t"])

    try:
        mp.resign_selection(stats, old_args=["x.py"], new_args=ARGS)
    except mp.CacheFormatError:
        return
    raise AssertionError("expected CacheFormatError")


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
    print("mutation plan tests passed")
