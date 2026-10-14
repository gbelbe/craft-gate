"""config_loosening: which moves of a value are reported, and how they are shown."""

from __future__ import annotations

import re

import config_loosening as cl
import gate_config as cfg
import pytest
from conftest import ROOT

CYCLOMATIC, COMPLEXITY = "cyclomatic", "complexity"
ENABLED, EXCLUDE, MUTATION, PATCH = "enabled", "exclude", "mutation", "patch-coverage"
FEATURE_BRANCH, ONE_LINE = "feature", "x = 1\n"
TABLE = (ROOT / "tests" / "features" / "config_loosening.feature").read_text()
ROW_KEYS = set(re.findall(r"^\s*\|\s*([a-z-]+\.[a-z-]+)\s*\|", TABLE, re.M))
SCHEMA_KEYS = {f"{section}.{key}" for section, keys in cfg.DEFAULTS.items() for key in keys}
LOOSE, TIGHT, MAIN, BAD_CONFIG = 40, 10, "main", 2


def settings(**changes):
    """The defaults with *changes* applied, as {"section.key": value}."""
    merged = {section: dict(keys) for section, keys in cfg.DEFAULTS.items()}
    for dotted, value in changes.items():
        section, key = dotted.replace("__", ".").split(".", 1)
        merged[section][key.replace("_", "-")] = value
    return merged


def moved(section, key, before, after):
    return cl.loosened(
        {**settings(), section: {**cfg.DEFAULTS[section], key: before}},
        {**settings(), section: {**cfg.DEFAULTS[section], key: after}},
    )


# -- every value has been ruled on --------------------------------------------------------------


def test_every_key_in_the_schema_is_ruled_on_or_declared_neutral() -> None:
    keys = {key for _section, key in (dotted.split(".") for dotted in SCHEMA_KEYS)}

    assert sorted(keys - set(cl.DIRECTION) - cl.NEUTRAL) == []


def test_no_rule_names_a_key_the_schema_does_not_have() -> None:
    keys = {dotted.split(".")[1] for dotted in SCHEMA_KEYS}

    assert sorted((set(cl.DIRECTION) | cl.NEUTRAL) - keys) == []


def test_a_neutral_key_has_no_direction() -> None:
    assert cl.NEUTRAL.isdisjoint(cl.DIRECTION)


def test_every_value_in_the_schema_has_a_row_in_the_feature() -> None:
    assert sorted(SCHEMA_KEYS - ROW_KEYS) == []


def test_every_directional_value_has_a_row_in_each_direction() -> None:
    for dotted in sorted(SCHEMA_KEYS - {d for d in SCHEMA_KEYS if d.split(".")[1] in cl.NEUTRAL}):
        rows = re.findall(
            rf"\|\s*{re.escape(dotted)}\s*\|.*\|\s*(is (?:not )?reported)\s*\|", TABLE
        )

        assert sorted(set(rows)) == ["is not reported", "is reported"], dotted


# -- what loosened() reports ----------------------------------------------------------------------


def test_a_raised_limit_is_reported_with_both_values() -> None:
    assert moved(COMPLEXITY, CYCLOMATIC, 15, LOOSE) == [
        cl.Loosened(COMPLEXITY, CYCLOMATIC, 15, LOOSE)
    ]


def test_a_lowered_limit_is_not_reported() -> None:
    assert moved(COMPLEXITY, CYCLOMATIC, 15, TIGHT) == []


def test_an_unchanged_value_is_not_reported() -> None:
    assert cl.loosened(settings(), settings()) == []


def test_each_loosened_value_is_reported_once_in_schema_order() -> None:
    before = settings()
    after = settings(
        complexity__cognitive=LOOSE, complexity__cyclomatic=LOOSE, mutation__enabled=False
    )

    found = [(i.section, i.key) for i in cl.loosened(before, after)]

    assert found == [(MUTATION, ENABLED), (COMPLEXITY, CYCLOMATIC), (COMPLEXITY, "cognitive")]


def test_removing_an_exclusion_is_tightening_and_adding_one_is_loosening() -> None:
    narrower = ["tests/*"]
    wider = ["tests/*", "gen/*"]

    assert moved(PATCH, EXCLUDE, wider, narrower) == []
    assert [i.key for i in moved(PATCH, EXCLUDE, narrower, wider)] == [EXCLUDE]


def test_reordering_a_list_is_not_a_change() -> None:
    assert moved("bdd", "paths", ["a", "b"], ["b", "a"]) == []


def test_a_gate_switched_off_is_reported_and_one_switched_on_is_not() -> None:
    assert [i.key for i in moved(MUTATION, ENABLED, True, False)] == [ENABLED]
    assert moved(MUTATION, ENABLED, False, True) == []


def test_the_reason_for_being_off_judges_nothing() -> None:
    assert moved(MUTATION, "reason", "", "slow suite") == []


# -- reading the config at a commit ---------------------------------------------------------------


def commit_config(repo, body, branch=None):
    if branch:
        repo.branch(branch)
    repo.write(cfg.CONFIG_FILE, body)
    repo.git("add", "-A")
    repo.commit_staged("config")


def test_a_commit_without_config_reads_as_the_defaults(repo) -> None:
    repo.commit("base", mod_py=ONE_LINE)

    assert cl.settings_at(repo.path, "HEAD") == cfg.DEFAULTS


def test_settings_are_read_as_committed_not_as_in_the_working_tree(repo) -> None:
    repo.commit("base", mod_py=ONE_LINE)
    commit_config(repo, f"[{COMPLEXITY}]\n{CYCLOMATIC} = {LOOSE}\n")
    repo.write(cfg.CONFIG_FILE, f"[{COMPLEXITY}]\n{CYCLOMATIC} = {TIGHT}\n")

    assert cl.settings_at(repo.path, "HEAD")[COMPLEXITY][CYCLOMATIC] == LOOSE


def test_pyproject_at_a_commit_is_read_when_there_is_no_standalone_file(repo) -> None:
    repo.commit("base", mod_py=ONE_LINE)
    repo.write("pyproject.toml", f"[tool.craft-gate.{COMPLEXITY}]\n{CYCLOMATIC} = {LOOSE}\n")
    repo.git("add", "-A")
    repo.commit_staged("pyproject")

    assert cl.settings_at(repo.path, "HEAD")[COMPLEXITY][CYCLOMATIC] == LOOSE


def test_the_comparison_starts_at_the_merge_base_not_at_the_tip_of_base(repo) -> None:
    repo.commit("base", mod_py=ONE_LINE)
    repo.branch(FEATURE_BRANCH)
    repo.git("checkout", "-q", MAIN)
    commit_config(repo, f"[{COMPLEXITY}]\n{CYCLOMATIC} = {LOOSE}\n")  # main loosened after the fork
    repo.git("checkout", "-q", FEATURE_BRANCH)
    repo.commit("work", mod_py="x = 2\n")

    assert cl.review_config(repo.path, MAIN) == []


def test_an_unreadable_config_at_head_is_a_config_error(repo) -> None:
    repo.commit("base", mod_py=ONE_LINE)
    commit_config(repo, f"[{COMPLEXITY}]\n{CYCLOMATIC} = 0\n", branch=FEATURE_BRANCH)

    with pytest.raises(cfg.ConfigError, match=CYCLOMATIC):
        cl.review_config(repo.path, MAIN)


# -- how it is shown ------------------------------------------------------------------------------


def test_nothing_loosened_renders_nothing() -> None:
    assert cl.render_loosened([]) == ""


def test_a_loosened_value_renders_as_a_row_of_setting_before_and_after() -> None:
    text = cl.render_loosened([cl.Loosened(COMPLEXITY, CYCLOMATIC, 15, LOOSE)])

    assert text.startswith("**Thresholds loosened**")
    assert "| `complexity.cyclomatic` | `15` | `40` |" in text


def test_the_command_line_prints_the_section_and_exits_zero(repo, run_main, capsys) -> None:
    repo.commit("base", mod_py=ONE_LINE)
    commit_config(repo, f"[{COMPLEXITY}]\n{CYCLOMATIC} = {LOOSE}\n", branch=FEATURE_BRANCH)

    code = run_main(cl, "--base", MAIN, "--path", str(repo.path))

    assert code == 0
    assert "`complexity.cyclomatic` | `15` | `40`" in capsys.readouterr().out


def test_the_command_line_names_a_bad_config_and_exits_two(repo, run_main, capsys) -> None:
    repo.commit("base", mod_py=ONE_LINE)
    commit_config(repo, f"[{COMPLEXITY}]\n{CYCLOMATIC} = 0\n", branch=FEATURE_BRANCH)

    code = run_main(cl, "--base", MAIN, "--path", str(repo.path))

    assert code == BAD_CONFIG
    assert CYCLOMATIC in capsys.readouterr().err
