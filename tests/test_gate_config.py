"""gate_config.py: which of the test gates run, are skipped on purpose, or are misconfigured."""

from __future__ import annotations

import gate_config as cfg
import pytest

VENV = ".venv"
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
    (root / VENV / "lib").mkdir(parents=True)
    (root / VENV / "lib" / "test_vendored.py").write_text(PYTEST_FILE)

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


def test_a_newline_in_the_config_cannot_add_a_line_to_the_workflow_output(
    tmp_path, monkeypatch
) -> None:
    root = project(tmp_path, '[tool.craft-gate.patch-coverage]\nsource = "x\\nstatus=skip"\n')
    output = tmp_path / "out"
    monkeypatch.setenv(GH_OUTPUT, str(output))

    code = cfg.main(["patch-coverage", PATH_FLAG, str(root)])

    assert code == 1
    assert not output.exists()


def test_a_package_path_is_a_valid_source(tmp_path) -> None:
    root = project(tmp_path, '[tool.craft-gate.patch-coverage]\nsource = "src/my_pkg-2.x"\n')

    assert cfg.decide(root, cfg.PATCH).settings["source"] == "src/my_pkg-2.x"


# -- the mutation selection and the `mutation` marker agree -------------------------------------

UNIT = "tests/unit"
SELECTED = f"{UNIT}/test_a.py"
MARKED = "import pytest\n\n\n@pytest.mark.mutation\ndef test_a():\n    assert True\n"
REGISTERED = "[tool.pytest.ini_options]\nmarkers = ['mutation: focused tests']\n"


def selection(*files: str, marker: bool = True) -> str:
    args = [*files, "-m", cfg.MARKER] if marker else list(files)
    return f"[tool.mutmut]\npytest_add_cli_args_test_selection = {args!r}\n{REGISTERED}"


def unit_test(root, name: str = "test_a.py", text: str = MARKED) -> None:
    (root / UNIT).mkdir(parents=True, exist_ok=True)
    (root / UNIT / name).write_text(text)


def test_a_selection_whose_files_exist_and_carry_the_marker_runs(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED))
    unit_test(root)

    assert cfg.decide(root, cfg.MUTATION).status == cfg.RUN


def test_the_marker_must_be_registered_when_the_selection_uses_it(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED).replace(REGISTERED, ""))
    unit_test(root)

    decision = cfg.decide(root, cfg.MUTATION)

    assert decision.status == cfg.ERROR
    assert "-m mutation is selected but the marker is not registered" in decision.reason


def test_a_marker_registered_in_pytest_ini_counts(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED).replace(REGISTERED, ""))
    unit_test(root)
    (root / "pytest.ini").write_text("[pytest]\nmarkers =\n    mutation: focused tests\n")

    assert cfg.decide(root, cfg.MUTATION).status == cfg.RUN


def test_a_selected_file_that_does_not_exist_is_named(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED, f"{UNIT}/test_gone.py"))
    unit_test(root)

    decision = cfg.decide(root, cfg.MUTATION)

    assert decision.status == cfg.ERROR
    assert "names file(s) that do not exist: tests/unit/test_gone.py" in decision.reason


def test_a_marked_test_file_missing_from_the_selection_is_named(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED))
    unit_test(root)
    unit_test(root, "test_orphan.py")

    decision = cfg.decide(root, cfg.MUTATION)

    assert decision.status == cfg.ERROR
    assert "missing from pytest_add_cli_args_test_selection: " + f"{UNIT}/test_orphan.py" in (
        decision.reason
    )


def test_marked_files_are_not_orphans_when_the_selection_does_not_use_the_marker(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED, marker=False))
    unit_test(root)
    unit_test(root, "test_other.py")

    assert cfg.decide(root, cfg.MUTATION).status == cfg.RUN


def test_a_marker_inside_a_virtualenv_is_not_an_orphan(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED))
    unit_test(root)
    dep = root / VENV / "lib"
    dep.mkdir(parents=True)
    (dep / "test_dep.py").write_text(MARKED)

    assert cfg.decide(root, cfg.MUTATION).status == cfg.RUN


def test_no_selection_at_all_is_left_to_mutmut(tmp_path) -> None:
    assert cfg.decide(project(tmp_path, MUTMUT), cfg.MUTATION).status == cfg.RUN


def test_the_problem_can_be_declared_off_with_a_reason(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED) + off(cfg.MUTATION))

    assert cfg.decide(root, cfg.MUTATION).status == cfg.SKIP


def test_a_script_that_only_mentions_the_marker_is_not_an_orphan(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED))
    unit_test(root)
    (root / "scripts").mkdir()
    (root / "scripts" / "gate_config.py").write_text('MARKER_USE = "pytest.mark.mutation"\n')

    assert cfg.decide(root, cfg.MUTATION).status == cfg.RUN


def test_a_file_named_like_a_test_with_the_suffix_form_is_an_orphan(tmp_path) -> None:
    root = project(tmp_path, selection(SELECTED))
    unit_test(root)
    unit_test(root, "orphan_test.py")

    decision = cfg.decide(root, cfg.MUTATION)

    assert decision.status == cfg.ERROR
    assert f"{UNIT}/orphan_test.py" in decision.reason
