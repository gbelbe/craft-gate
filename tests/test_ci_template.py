"""templates/ci-job.yml wires each test gate through gate_config.py, and parses."""

from __future__ import annotations

import os
import subprocess

import pytest
import yaml
from conftest import ROOT

JOBS = yaml.safe_load("jobs:\n" + (ROOT / "templates" / "ci-job.yml").read_text())["jobs"]
TEST_GATES = {
    "patch-coverage": "patch-coverage",
    "mutation-ratchet": "mutation",
    "behaviour-coverage": "bdd",
}
TOOLS = "uv run --no-project --with-requirements scripts/gate-requirements.txt"
STATUS_RUN = "steps.gate.outputs.status == 'run'"


@pytest.mark.parametrize(("job", "gate"), sorted(TEST_GATES.items()))
def test_each_test_gate_asks_gate_config_first(job, gate) -> None:
    steps = JOBS[job]["steps"]
    asked = [s for s in steps if s.get("id") == "gate"]

    assert len(asked) == 1
    assert asked[0]["run"] == f"{TOOLS} python3 scripts/gate_config.py {gate}"
    assert steps.index(asked[0]) < min(
        steps.index(s) for s in steps if "if" in s and STATUS_RUN in s["if"]
    )


@pytest.mark.parametrize("job", sorted(TEST_GATES))
def test_every_step_after_the_decision_is_conditional_on_it(job) -> None:
    steps = JOBS[job]["steps"]
    decided = next(i for i, s in enumerate(steps) if s.get("id") == "gate")

    unguarded = [
        s.get("name", s.get("uses"))
        for s in steps[decided + 1 :]
        if STATUS_RUN not in s.get("if", "")
    ]

    assert unguarded == []


def test_thresholds_come_from_the_config_not_the_workflow() -> None:
    text = (ROOT / "templates" / "ci-job.yml").read_text()

    assert "--fail-under 90" not in text
    assert "--threshold 80" not in text
    assert "steps.gate.outputs.threshold" in text


@pytest.mark.parametrize("job", ["patch-coverage", "behaviour-coverage"])
def test_the_coverage_jobs_leave_test_files_out_of_the_measurement(job) -> None:
    diff_cover = next(s for s in JOBS[job]["steps"] if "diff-cover" in s.get("run", ""))

    assert "steps.gate.outputs.exclude" in diff_cover["run"]
    assert "set -f" in diff_cover["run"]  # the globs are diff-cover's, not the shell's


TEST_IMPACT = yaml.safe_load("jobs:\n" + (ROOT / "templates" / "test-impact.yml").read_text())[
    "jobs"
]


def _impact_steps() -> dict[str, dict]:
    return {s["name"]: s for s in TEST_IMPACT["tests"]["steps"] if "name" in s}


def test_the_test_impact_template_runs_everything_outside_a_pull_request() -> None:
    pick = _impact_steps()["Choose the test files this change can affect"]["run"]

    assert 'if [ "${{ github.event_name }}" != "pull_request" ]' in pick
    assert 'echo "targets=tests"' in pick  # the merge queue and the main branch run the whole suite


def test_the_test_impact_template_runs_everything_when_the_selection_cannot_narrow() -> None:
    pick = _impact_steps()["Choose the test files this change can affect"]["run"]

    assert 'if [ "$picked" = "ALL" ]' in pick
    assert "scripts/test_impact.py select" in pick


def test_the_test_impact_template_records_the_map_on_each_full_run() -> None:
    steps = _impact_steps()
    full_run = "github.event_name != 'pull_request' && steps.tested.outputs.queued != 'true'"

    assert steps["Record which test ran which line"]["if"] == full_run
    assert steps["Keep the map for the pull requests that follow"]["if"] == full_run
    assert "--cov-context=test" in steps["Run the tests"]["run"]


def test_the_test_impact_template_names_the_map_after_its_tree() -> None:
    steps = _impact_steps()
    keep = steps["Keep the map for the pull requests that follow"]["with"]

    assert keep["name"] == "test-impact-map-${{ steps.tree.outputs.tree }}"
    assert keep["path"] == ".test-impact.json"
    assert keep["include-hidden-files"] is True  # upload-artifact skips dot files otherwise


def _run_skip_step(tmp_path, gh_script: str) -> str:
    """Run the push-skip step's script with a stub `gh`; what it wrote to its outputs file."""
    stub = tmp_path / "gh"
    stub.write_text("#!/bin/bash\n" + gh_script)
    stub.chmod(0o755)
    outputs = tmp_path / "outputs"
    outputs.touch()
    script = _impact_steps()["Skip a push whose content the merge queue already tested"]["run"]
    subprocess.run(
        ["bash", "-e", "-c", script],
        check=True,
        env={
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(outputs),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
            "TREE": "abc123",
            "GITHUB_REPOSITORY": "o/r",
        },
    )
    return outputs.read_text()


def test_a_push_skips_the_suite_when_an_artifact_names_its_tree(tmp_path) -> None:
    assert _run_skip_step(tmp_path, "echo 1") == "queued=true\n"


def test_a_push_runs_the_suite_when_no_artifact_names_its_tree(tmp_path) -> None:
    assert _run_skip_step(tmp_path, "echo 0") == ""


def test_a_push_runs_the_suite_when_the_artifact_lookup_fails(tmp_path) -> None:
    assert _run_skip_step(tmp_path, "exit 1") == ""


def test_the_test_impact_template_runs_the_suite_unless_the_queue_already_did() -> None:
    steps = _impact_steps()

    expected = "steps.pick.outputs.targets != '' && steps.tested.outputs.queued != 'true'"
    assert steps["Run the tests"]["if"] == expected
    assert steps["Skip a push whose content the merge queue already tested"]["if"] == (
        "github.event_name == 'push'"
    )


def test_the_test_impact_template_restores_the_newest_map_for_a_pull_request() -> None:
    find = _impact_steps()["Find the map of the last full run"]

    assert find["if"] == "github.event_name == 'pull_request'"
    assert 'startswith("test-impact-map-")' in find["run"]
    assert "gh run download" in find["run"]


def test_the_test_impact_template_names_the_merge_queue() -> None:
    text = (ROOT / "templates" / "test-impact.yml").read_text()

    assert "merge_group:" in text
    assert "fetch-depth: 0" in text
