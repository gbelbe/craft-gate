"""The gate tools are pinned in one shipped file, and the jobs take them from it."""

from __future__ import annotations

import re

import pytest
import tomllib
import yaml
from conftest import ROOT
from packaging.requirements import Requirement

REQUIREMENTS = ROOT / "scripts" / "gate-requirements.txt"
PINS = [
    Requirement(line)
    for line in REQUIREMENTS.read_text().splitlines()
    if line and not line.startswith("#")
]
LOCKED = {p["name"]: p["version"] for p in tomllib.loads((ROOT / "uv.lock").read_text())["package"]}
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
DECLARED = [
    Requirement(spec)
    for extra in ("craftcov", "complexity", "mutation", "dev")
    for spec in PYPROJECT["project"]["optional-dependencies"][extra]
    if not spec.startswith(("pytest>", "pytest-bdd"))
]
WITH_FILE = "--with-requirements scripts/gate-requirements.txt"
CI = (ROOT / "templates" / "ci-job.yml").read_text()
LOCAL = (ROOT / "templates" / "local-craft-gate.sh").read_text()
STEPS = [
    step
    for job in yaml.safe_load("jobs:\n" + CI)["jobs"].values()
    for step in job["steps"]
    if "uv" in step.get("run", "")
]


@pytest.mark.parametrize("pin", PINS, ids=lambda r: r.name)
def test_every_tool_is_pinned_to_one_exact_version(pin) -> None:
    assert [s.operator for s in pin.specifier] == ["=="]


@pytest.mark.parametrize("pin", PINS, ids=lambda r: r.name)
def test_the_pin_is_the_version_this_repo_locks_and_tests_against(pin) -> None:
    (spec,) = pin.specifier

    assert LOCKED[pin.name] == spec.version


@pytest.mark.parametrize("declared", DECLARED, ids=lambda r: r.name)
def test_the_pin_satisfies_what_pyproject_declares_for_the_tool(declared) -> None:
    (pin,) = [p for p in PINS if p.name == declared.name]
    (spec,) = pin.specifier

    assert declared.specifier.contains(spec.version)


def test_a_repo_needs_no_extras_of_its_own_for_the_craft_gate_tools() -> None:
    assert not re.search(r"--extra (craftcov|complexity|mutation|dev)\b", CI + LOCAL)


def test_every_job_that_runs_uv_takes_the_tools_from_the_pinned_file() -> None:
    assert STEPS
    for step in STEPS:
        for line in step["run"].splitlines():
            if "uv run" in line:
                assert WITH_FILE in line, line


def test_the_local_runner_takes_the_tools_from_the_pinned_file_too() -> None:
    lines = [line for line in LOCAL.splitlines() if "uv run" in line]

    assert lines
    assert all(WITH_FILE in line for line in lines), lines


def test_the_mutation_cache_is_dropped_when_the_pinned_tools_change() -> None:
    assert "scripts/gate-requirements.txt'" in CI.split("mutmut-${{ runner.os }}-${{ hashFiles(")[1]
