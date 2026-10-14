"""gate_config.py: which of the test gates run, are skipped on purpose, or are misconfigured."""

from __future__ import annotations

import gate_config as cfg
import pytest

PYTEST_FILE = "def test_x():\n    assert True\n"
MUTMUT = "[tool.mutmut]\nsource_paths = ['src']\n"
PATH_FLAG, GH_OUTPUT, TESTS = "--path", "GITHUB_OUTPUT", "tests"
NO_SCENARIOS = "no scenarios yet"
DEFAULT_PATCH, DEFAULT_MUTATION, DEFAULT_BDD, OVERRIDE = 90, 80, 80, 75
FEATURE = "Feature: x\n  Scenario: y\n    Given z\n"


def project(tmp_path, pyproject: str = "", tests: bool = True, features: bool = True):
    (tmp_path / "pyproject.toml").write_text(pyproject)
    if tests:
        (tmp_path / TESTS).mkdir(exist_ok=True)
        (tmp_path / TESTS / "test_x.py").write_text(PYTEST_FILE)
    if features:
        (tmp_path / TESTS / "features").mkdir(parents=True, exist_ok=True)
        (tmp_path / TESTS / "features" / "x.feature").write_text(FEATURE)
    return tmp_path


def off(gate: str, reason: str = "because") -> str:
    return f'[tool.craft-gate.{gate}]\nenabled = false\nreason = "{reason}"\n'


# -- on by default ------------------------------------------------------------------


def test_every_gate_runs_by_default_when_the_repo_is_set_up_for_it(tmp_path) -> None:
    root = project(tmp_path, MUTMUT)

    assert {g: cfg.decide(root, g).status for g in cfg.GATES} == dict.fromkeys(cfg.GATES, cfg.RUN)


def test_the_documented_defaults_are_returned_with_a_running_gate(tmp_path) -> None:
    root = project(tmp_path, MUTMUT)

    assert cfg.decide(root, cfg.PATCH).settings[cfg.THRESHOLD] == DEFAULT_PATCH
    assert cfg.decide(root, cfg.MUTATION).settings[cfg.THRESHOLD] == DEFAULT_MUTATION
    assert cfg.decide(root, cfg.BDD).settings[cfg.THRESHOLD] == DEFAULT_BDD
    assert cfg.decide(root, cfg.BDD).settings[cfg.PATHS] == ["tests/features"]


def test_a_missing_pyproject_means_defaults_not_a_crash(tmp_path) -> None:
    (tmp_path / TESTS).mkdir()
    (tmp_path / TESTS / "test_x.py").write_text(PYTEST_FILE)

    assert cfg.decide(tmp_path, "patch-coverage").status == cfg.RUN


def test_settings_override_the_defaults(tmp_path) -> None:
    root = project(tmp_path, "[tool.craft-gate.patch-coverage]\nthreshold = 75\n")

    assert cfg.decide(root, cfg.PATCH).settings[cfg.THRESHOLD] == OVERRIDE


# -- opting out is explicit ---------------------------------------------------------


def test_a_gate_switched_off_with_a_reason_is_skipped_and_says_why(tmp_path) -> None:
    root = project(tmp_path, off(cfg.MUTATION, "too slow for this repo"))

    decision = cfg.decide(root, cfg.MUTATION)

    assert (decision.status, decision.reason) == (cfg.SKIP, "too slow for this repo")


def test_switching_a_gate_off_without_a_reason_is_an_error(tmp_path) -> None:
    root = project(tmp_path, "[tool.craft-gate.bdd]\nenabled = false\n")

    decision = cfg.decide(root, cfg.BDD)

    assert decision.status == cfg.ERROR
    assert "reason" in decision.reason


def test_a_blank_reason_does_not_count(tmp_path) -> None:
    root = project(tmp_path, off(cfg.BDD, "   "))

    assert cfg.decide(root, cfg.BDD).status == cfg.ERROR


# -- a gate that cannot work says so instead of passing silently ---------------------


def test_no_test_suite_fails_patch_coverage_unless_declared(tmp_path) -> None:
    root = project(tmp_path, "", tests=False, features=False)

    decision = cfg.decide(root, cfg.PATCH)

    assert decision.status == cfg.ERROR
    assert "no pytest suite" in decision.reason
    assert "enabled = false" in decision.reason


def test_no_test_suite_is_fine_when_patch_coverage_is_off_on_purpose(tmp_path) -> None:
    root = project(tmp_path, off(cfg.PATCH, "scripts only"), tests=False, features=False)

    assert cfg.decide(root, cfg.PATCH).status == cfg.SKIP


def test_mutation_and_bdd_follow_patch_coverage_when_it_is_off(tmp_path) -> None:
    root = project(tmp_path, off(cfg.PATCH, "no tests yet"))

    for gate in ("mutation", "bdd"):
        decision = cfg.decide(root, gate)
        assert decision.status == cfg.SKIP, gate
        assert "patch-coverage is off" in decision.reason
        assert "no tests yet" in decision.reason


def test_mutation_needs_a_mutmut_section(tmp_path) -> None:
    root = project(tmp_path, "")

    decision = cfg.decide(root, cfg.MUTATION)

    assert decision.status == cfg.ERROR
    assert "[tool.mutmut]" in decision.reason


def test_bdd_needs_feature_files_under_its_paths(tmp_path) -> None:
    root = project(tmp_path, "", features=False)

    decision = cfg.decide(root, cfg.BDD)

    assert decision.status == cfg.ERROR
    assert "tests/features" in decision.reason


def test_bdd_paths_can_point_elsewhere(tmp_path) -> None:
    root = project(tmp_path, '[tool.craft-gate.bdd]\npaths = ["spec"]\n', features=False)
    (root / "spec").mkdir()
    (root / "spec" / "a.feature").write_text(FEATURE)

    decision = cfg.decide(root, cfg.BDD)

    assert (decision.status, decision.settings[cfg.PATHS]) == (cfg.RUN, ["spec"])


def test_tests_inside_a_virtualenv_do_not_count_as_a_suite(tmp_path) -> None:
    root = project(tmp_path, "", tests=False, features=False)
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "test_vendored.py").write_text(PYTEST_FILE)

    assert cfg.decide(root, cfg.PATCH).status == cfg.ERROR


# -- a typo in the config is reported, not ignored -----------------------------------


@pytest.mark.parametrize(
    ("toml", "needle"),
    [
        ("[tool.craft-gate.patch-covrage]\nenabled = false\n", "patch-covrage"),
        ("[tool.craft-gate.mutation]\nthreshhold = 70\n", "threshhold"),
        ("[tool.craft-gate.mutation]\nthreshold = 150\n", "threshold"),
        ('[tool.craft-gate.mutation]\nenabled = "no"\n', "enabled"),
        ('[tool.craft-gate.bdd]\npaths = "tests"\n', "paths"),
    ],
)
def test_bad_config_is_an_error_that_names_the_problem(tmp_path, toml, needle) -> None:
    root = project(tmp_path, MUTMUT + toml)

    decisions = [cfg.decide(root, g) for g in cfg.GATES]

    assert any(d.status == cfg.ERROR and needle in d.reason for d in decisions)


def test_unparseable_toml_is_an_error(tmp_path) -> None:
    root = project(tmp_path, "[tool.craft-gate\n")

    assert cfg.decide(root, cfg.PATCH).status == cfg.ERROR


# -- reporting skips -----------------------------------------------------------------


def test_skipped_gates_lists_only_deliberate_opt_outs(tmp_path) -> None:
    root = project(tmp_path, MUTMUT + off(cfg.BDD, NO_SCENARIOS))

    assert cfg.skipped_gates(root) == [("bdd", NO_SCENARIOS)]


def test_skipped_gates_is_empty_when_everything_runs(tmp_path) -> None:
    assert cfg.skipped_gates(project(tmp_path, MUTMUT)) == []


def test_skipped_markdown_names_each_gate_and_reason() -> None:
    text = cfg.render_skipped([("bdd", NO_SCENARIOS), ("mutation", "too slow")])

    assert "| `bdd` | no scenarios yet |" in text
    assert "| `mutation` | too slow |" in text
    assert cfg.render_skipped([]) == ""


# -- the command line, as the CI template uses it ------------------------------------


def test_cli_writes_github_outputs_for_a_running_gate(tmp_path, monkeypatch, capsys) -> None:
    root = project(tmp_path, MUTMUT)
    out = tmp_path / "gh_output"
    monkeypatch.setenv(GH_OUTPUT, str(out))

    code = cfg.main([cfg.BDD, PATH_FLAG, str(root)])

    assert code == 0
    lines = out.read_text().splitlines()
    assert "status=run" in lines
    assert "threshold=80" in lines
    assert "paths=tests/features" in lines


def test_cli_reports_a_skip_with_exit_zero(tmp_path, monkeypatch, capsys) -> None:
    root = project(tmp_path, off(cfg.MUTATION, "too slow"))
    monkeypatch.delenv(GH_OUTPUT, raising=False)

    code = cfg.main([cfg.MUTATION, PATH_FLAG, str(root)])

    assert code == 0
    assert "skipped on purpose: too slow" in capsys.readouterr().out


def test_cli_exits_nonzero_on_misconfiguration(tmp_path, monkeypatch, capsys) -> None:
    root = project(tmp_path, "", tests=False, features=False)
    monkeypatch.delenv(GH_OUTPUT, raising=False)

    code = cfg.main([cfg.PATCH, PATH_FLAG, str(root)])

    assert code == 1
    assert "no pytest suite" in capsys.readouterr().err


# -- test files do not pad the measurement ---------------------------------------------------


def test_patch_and_behaviour_coverage_exclude_test_files_by_default(tmp_path) -> None:
    root = project(tmp_path, MUTMUT)

    for gate in (cfg.PATCH, cfg.BDD):
        excluded = cfg.decide(root, gate).settings[cfg.EXCLUDE]
        assert "tests/*" in excluded, gate
        assert "conftest.py" in excluded, gate


def test_exclude_can_be_replaced(tmp_path) -> None:
    root = project(tmp_path, '[tool.craft-gate.patch-coverage]\nexclude = ["gen/*"]\n')

    assert cfg.decide(root, cfg.PATCH).settings[cfg.EXCLUDE] == ["gen/*"]


def test_exclude_can_be_emptied(tmp_path) -> None:
    root = project(tmp_path, "[tool.craft-gate.patch-coverage]\nexclude = []\n")

    assert cfg.decide(root, cfg.PATCH).settings[cfg.EXCLUDE] == []


def test_a_decision_does_not_share_its_exclude_list_with_the_defaults(tmp_path) -> None:
    root = project(tmp_path, MUTMUT)

    cfg.decide(root, cfg.PATCH).settings[cfg.EXCLUDE].append("x")

    assert "x" not in cfg.decide(root, cfg.PATCH).settings[cfg.EXCLUDE]
    assert "x" not in cfg.TEST_FILES


def test_exclude_is_published_space_separated_for_the_workflow(tmp_path, monkeypatch) -> None:
    root = project(tmp_path, MUTMUT)
    out = tmp_path / "gh_output"
    monkeypatch.setenv(GH_OUTPUT, str(out))

    cfg.main([cfg.PATCH, PATH_FLAG, str(root)])

    assert (
        "exclude=tests/* */tests/* test_*.py *_test.py conftest.py" in out.read_text().splitlines()
    )
