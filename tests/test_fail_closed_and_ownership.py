"""The tidy ratchet fails closed in CI, and CODEOWNERS covers every file that decides a gate."""

from __future__ import annotations

import fnmatch
import os
import subprocess

import pytest
from conftest import ROOT
from test_bootstrap import SHIPPED

RATCHET = ROOT / "scripts" / "check_tidy_ratchet.sh"
MISSING_BASE = ("--base", "origin/never-fetched")
CODEOWNERS = [
    line.split()[0].lstrip("/")
    for line in (ROOT / "templates" / "CODEOWNERS.snippet").read_text().splitlines()
    if line.startswith("/")
]


def ratchet(repo, **env) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k not in ("CI", "GITHUB_ACTIONS")}
    return subprocess.run(
        ["bash", str(RATCHET), *MISSING_BASE],
        cwd=repo.path,
        env={**clean, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def owned(path: str) -> bool:
    return any(
        path.startswith(pattern) if pattern.endswith("/") else fnmatch.fnmatch(path, pattern)
        for pattern in CODEOWNERS
    )


@pytest.mark.parametrize("variable", ["CI", "GITHUB_ACTIONS"])
def test_a_missing_base_fails_in_ci(repo, variable) -> None:
    repo.commit("base", mod_py="x = 1\n")

    result = ratchet(repo, **{variable: "true"})

    assert result.returncode == 1
    assert "fetch-depth: 0" in result.stderr


def test_a_missing_base_only_warns_on_a_developer_machine(repo) -> None:
    repo.commit("base", mod_py="x = 1\n")

    result = ratchet(repo)

    assert result.returncode == 0
    assert "skipping" in result.stderr


@pytest.mark.parametrize("path", [*SHIPPED, "scripts/craftcov_core/scan.py"])
def test_every_shipped_file_has_an_owner_in_the_codeowners_template(path) -> None:
    assert owned(path), path


def test_the_config_files_have_an_owner() -> None:
    assert owned("craft-gate.toml")
    assert owned("pyproject.toml")


def test_the_shipped_local_runner_has_no_other_projects_directory_names_in_it() -> None:
    assert "ster/" not in (ROOT / "templates" / "local-craft-gate.sh").read_text()
    assert "kai-ster" not in (ROOT / "scripts" / "check_complexity_ratchet.py").read_text()
