"""bootstrap.sh: what it installs, that a re-run is a no-op, and what it prunes."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT

CATALOG = "catalog.yaml"
SCRIPTS = "scripts"
CORE = "craftcov_core"
SHIPPED = [
    "CRAFTSMANSHIP.md",
    CATALOG,
    "scripts/check_tidy_ratchet.sh",
    "scripts/report_tidy_history.sh",
    "scripts/craftcov.py",
    "scripts/check_refactor_first.py",
    "scripts/check_complexity_ratchet.py",
    "scripts/craftcov_pr_comment.py",
    "scripts/check_mutation_ratchet.py",
    "scripts/local-craft-gate.sh",
    ".claude/skills/tidy-first/SKILL.md",
]
EXECUTABLE = [p for p in SHIPPED if p.startswith(f"{SCRIPTS}/")]
NOT_A_REPO = 1


def bootstrap(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ROOT / "bootstrap.sh"), str(target)], capture_output=True, text=True
    )


def tree(target: Path) -> dict[str, bytes]:
    return {
        p.relative_to(target).as_posix(): p.read_bytes()
        for p in sorted(target.rglob("*"))
        if p.is_file() and ".git/" not in p.as_posix()
    }


@pytest.fixture
def target(repo) -> Path:
    return repo.path


def test_every_shipped_file_lands_in_the_target(target) -> None:
    result = bootstrap(target)

    assert result.returncode == 0, result.stderr
    for rel in SHIPPED:
        assert (target / rel).read_bytes() == (ROOT / _source(rel)).read_bytes(), rel


def _source(rel: str) -> str:
    return {
        ".claude/skills/tidy-first/SKILL.md": "skills/tidy-first/SKILL.md",
        "scripts/local-craft-gate.sh": "templates/local-craft-gate.sh",
    }.get(rel, rel)


def test_the_craftcov_package_is_shipped_whole(target) -> None:
    bootstrap(target)

    shipped = sorted(p.name for p in (ROOT / SCRIPTS / CORE).glob("*.py"))
    assert sorted(p.name for p in (target / SCRIPTS / CORE).glob("*.py")) == shipped


def test_scripts_are_executable(target) -> None:
    bootstrap(target)

    for rel in EXECUTABLE:
        assert os.access(target / rel, os.X_OK), rel


def test_the_version_marker_records_where_it_came_from(target) -> None:
    bootstrap(target)

    assert (target / ".craft-gate-version").read_text().strip() != ""


def test_a_second_run_changes_nothing(target) -> None:
    bootstrap(target)
    before = tree(target)

    result = bootstrap(target)

    assert result.returncode == 0
    assert tree(target) == before


def test_a_module_an_earlier_release_shipped_is_pruned(target) -> None:
    bootstrap(target)
    stale = target / SCRIPTS / CORE / "gone_in_this_release.py"
    stale.write_text("x = 1\n")

    bootstrap(target)

    assert not stale.exists()


def test_an_edited_copy_is_overwritten_by_an_update(target) -> None:
    bootstrap(target)
    (target / CATALOG).write_text("local edit\n")

    bootstrap(target)

    assert (target / CATALOG).read_bytes() == (ROOT / CATALOG).read_bytes()


def test_files_the_repo_owns_are_never_touched(target) -> None:
    for rel in ("AGENTS.md", ".pre-commit-config.yaml", ".github/workflows/ci.yml"):
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_text("mine\n")

    bootstrap(target)

    for rel in ("AGENTS.md", ".pre-commit-config.yaml", ".github/workflows/ci.yml"):
        assert (target / rel).read_text() == "mine\n", rel


def test_it_refuses_a_directory_that_is_not_a_git_repo(tmp_path) -> None:
    result = bootstrap(tmp_path)

    assert result.returncode == NOT_A_REPO
    assert "doesn't look like a git repo root" in result.stderr


def test_the_output_lists_the_manual_steps(target) -> None:
    out = bootstrap(target).stdout

    assert "Manual steps left" in out
    assert "templates/ci-job.yml" in out
    assert "templates/pre-commit-hook.yaml" in out
    assert "templates/AGENTS.md.snippet.md" in out
