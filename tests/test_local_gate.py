#!/usr/bin/env python3
"""Regression tests for the files bootstrap installs into consuming repos."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_local_runner_has_all_default_craft_gates() -> None:
    runner = (ROOT / "templates" / "local-craft-gate.sh").read_text()

    for required in (
        "check_complexity_ratchet.py",
        "check_tidy_ratchet.sh",
        "check_refactor_first.py",
        "mutmut run",
        "check_mutation_ratchet.py",
        "craftcov_pr_comment.py",
        "--format sarif",
        "--fresh",
        "rm -rf mutants",
    ):
        assert required in runner, required


def test_local_runner_fast_mode_skips_expensive_gates() -> None:
    runner = (ROOT / "templates" / "local-craft-gate.sh").read_text()

    assert "FAST=0" in runner
    assert "if [[ $FAST -eq 0 ]]" in runner
    assert "--fast" in runner
    assert "--mutation" in runner
    assert "git diff --name-only" in runner
    assert "--improvement 20" in runner


def test_local_runner_documents_focused_mutation_selection() -> None:
    runner = (ROOT / "templates" / "local-craft-gate.sh").read_text()

    assert "pytest_add_cli_args_test_selection" in runner
    assert "ster/**/*.py" in runner
    assert "tests/**/*.py" in runner


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


def test_ci_template_uses_freshness_aware_mutation_cache() -> None:
    template = (ROOT / "templates" / "ci-job.yml").read_text()

    assert "hashFiles('**/*.py', 'pyproject.toml', 'uv.lock')" in template
    assert 'cache_invalidation_files = ["tests/**/*.py", "conftest.py"]' in template
    assert 'on_dependency_change = "rerun"' in template
    assert "pytest_add_cli_args_test_selection" in template


def test_bootstrap_installs_local_runner() -> None:
    bootstrap = (ROOT / "bootstrap.sh").read_text()

    assert "local-craft-gate.sh" in bootstrap
    assert "templates/local-craft-gate.sh" in bootstrap


def test_mutation_ratchet_documents_absolute_or_improvement_rule() -> None:
    source = (ROOT / "scripts" / "check_mutation_ratchet.py").read_text()

    assert "evaluate_results" in source
    assert "improvement" in source
    assert ".mutation-baseline.json" in source


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
    print("local craft-gate template tests passed")
