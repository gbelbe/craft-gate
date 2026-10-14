"""templates/update-check.yml turns a bootstrap run into a PR, and must carry all of it."""

from __future__ import annotations

import subprocess

import yaml
from conftest import ROOT
from test_bootstrap import SHIPPED, bootstrap

WORKFLOW = yaml.safe_load((ROOT / "templates" / "update-check.yml").read_text())
PR_STEP = next(
    s["run"] for s in WORKFLOW["jobs"]["check"]["steps"] if "Open or update" in s.get("name", "")
)


def script_line(fragment: str) -> str:
    """The one line of the PR step containing *fragment*, comments cut off."""
    lines = [ln.split("  #")[0].strip() for ln in PR_STEP.splitlines() if fragment in ln]
    assert len(lines) == 1, lines
    return lines[0]


def run(repo, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", command], cwd=repo.path, capture_output=True, text=True, check=False
    )


def test_what_the_step_stages_is_every_file_bootstrap_wrote(repo) -> None:
    repo.commit("base", readme_md="x\n")
    bootstrap(repo.path)

    run(repo, script_line("git add"))

    staged = set(repo.git("diff", "--cached", "--name-only").splitlines())
    assert set(SHIPPED) <= staged
    assert any(path.startswith("scripts/craftcov_core/") for path in staged)


def test_a_release_that_only_adds_untracked_files_still_counts_as_a_change(repo) -> None:
    repo.commit("base", readme_md="x\n")
    repo.write("scripts/new_script.py", "x = 1\n")
    condition = script_line("git status --porcelain").removeprefix("if ").removesuffix("; then")

    assert (
        run(repo, f"if {condition}; then echo empty; else echo changed; fi").stdout == "changed\n"
    )


def test_a_clean_tree_is_not_a_change(repo) -> None:
    repo.commit("base", readme_md="x\n")
    condition = script_line("git status --porcelain").removeprefix("if ").removesuffix("; then")

    assert run(repo, f"if {condition}; then echo empty; else echo changed; fi").stdout == "empty\n"


def test_the_header_warns_that_a_token_opened_pr_gets_no_checks() -> None:
    text = (ROOT / "templates" / "update-check.yml").read_text()

    assert "does not start workflows for PRs that token opens" in text
