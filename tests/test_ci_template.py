"""templates/ci-job.yml wires each test gate through gate_config.py, and parses."""

from __future__ import annotations

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
