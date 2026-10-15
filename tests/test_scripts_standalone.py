"""Shipped scripts are copied into other repos and run by path: they must import their siblings
from there, with nothing on sys.path but the directory Python puts there itself."""

from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import ROOT

SCRIPTS = [
    "craftcov.py",
    "check_refactor_first.py",
    "check_complexity_ratchet.py",
    "check_mutation_ratchet.py",
    "craftcov_pr_comment.py",
    "gate_config.py",
    "design_review.py",
    "config_loosening.py",
    "ci_history.py",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_script_runs_by_path_from_any_directory(script, tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
