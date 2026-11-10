#!/usr/bin/env python3
"""Regression tests for the files bootstrap installs into consuming repos."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_CHECKS = 2  # patch coverage and behaviour coverage
RUNNER = ROOT / "templates" / "local-craft-gate.sh"


def test_local_runner_has_all_default_craft_gates() -> None:
    runner = (RUNNER).read_text()

    for required in (
        "check_complexity_ratchet.py",
        "check_tidy_ratchet.sh",
        "check_refactor_first.py",
        "mutation_run.py",
        "check_mutation_ratchet.py",
        "craftcov_pr_comment.py",
        "--format sarif",
        "--fresh",
        "rm -rf mutants",
    ):
        assert required in runner, required


def test_local_runner_fast_mode_skips_expensive_gates() -> None:
    runner = (RUNNER).read_text()

    assert "FAST=0" in runner
    assert "if [[ $FAST -eq 0 ]]" in runner
    assert "--fast" in runner
    assert "--mutation" in runner
    assert "git diff --name-only" in runner
    assert "--improvement" not in runner


def test_local_runner_documents_focused_mutation_selection() -> None:
    runner = (RUNNER).read_text()

    assert "pytest_add_cli_args_test_selection" in runner
    assert "-- '*.py'" in runner  # any layout: a pathspec '*' crosses directories


def test_ci_template_keeps_all_five_gates_and_two_reports() -> None:
    template = (ROOT / "templates" / "ci-job.yml").read_text()

    for required in (
        "tidy:",
        "refactor-first:",
        "complexity:",
        "patch-coverage:",
        "mutation-ratchet:",
        "craftcov-pr-comment:",
        "craftcov-sarif:",
    ):
        assert required in template, required


def test_ci_template_runs_the_mutants_on_changed_lines_from_a_clean_slate() -> None:
    template = (ROOT / "templates" / "ci-job.yml").read_text()

    assert "mutation_run.py" in template
    assert "mutation_plan" not in template
    assert "Cache mutmut results" not in template
    assert "on_dependency_change" not in template
    assert "pytest_add_cli_args_test_selection" in template


def test_bootstrap_installs_local_runner() -> None:
    bootstrap = (ROOT / "bootstrap.sh").read_text()

    assert "local-craft-gate.sh" in bootstrap
    assert "templates/local-craft-gate.sh" in bootstrap


def test_mutation_ratchet_has_one_bar_and_no_baseline_file() -> None:
    source = (ROOT / "scripts" / "check_mutation_ratchet.py").read_text()

    assert "evaluate_results" in source
    assert ".mutation-baseline.json" not in source


def test_local_runner_asks_gate_config_before_each_test_gate() -> None:
    runner = (RUNNER).read_text()

    for gate in ("patch-coverage", "bdd", "mutation"):
        assert f"gate_runs {gate}" in runner, gate
    assert "scripts/gate_config.py" in runner


def test_local_runner_leaves_test_files_out_of_both_coverage_numbers() -> None:
    runner = RUNNER.read_text()

    assert runner.count("$(exclude_args)") == COVERAGE_CHECKS
    assert "gate_setting exclude" in runner


def test_local_runner_runs_the_architecture_gate_only_when_the_repo_declares_one() -> None:
    runner = RUNNER.read_text()
    block = runner.split("if [[ -f architecture.yaml ]]; then")[1].split("fi\n")[0]

    assert "render_architecture.py --check" in block
    assert "lint-imports --config .architecture.importlinter" in block
