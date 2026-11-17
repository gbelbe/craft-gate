"""architecture_wiring.py: the ratchet only counts once a workflow or a hook runs it."""

from __future__ import annotations

import architecture_wiring as wiring
import pytest

RUNS = "run: python3 scripts/check_architecture_ratchet.py --base origin/main\n"
OTHER_STEPS = "run: python3 scripts/render_architecture.py --check\nrun: lint-imports\n"
WORKFLOW = ".github/workflows/ci.yml"
HOOKS = ".pre-commit-config.yaml"


def write(root, path: str, text: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text)


def test_a_workflow_that_runs_the_ratchet_wires_it(tmp_path) -> None:
    write(tmp_path, WORKFLOW, RUNS)

    assert wiring.unwired(tmp_path) is None


@pytest.mark.parametrize("name", [".github/workflows/ci.yaml", HOOKS, ".pre-commit-config.yml"])
def test_any_workflow_extension_and_either_hook_file_wires_it(tmp_path, name) -> None:
    write(tmp_path, name, RUNS)

    assert wiring.unwired(tmp_path) is None


def test_a_repo_with_no_workflow_and_no_hook_file_is_unwired(tmp_path) -> None:
    assert wiring.unwired(tmp_path) is not None


def test_the_other_architecture_steps_do_not_wire_the_ratchet(tmp_path) -> None:
    write(tmp_path, WORKFLOW, OTHER_STEPS)

    assert wiring.unwired(tmp_path) is not None


def test_a_comment_that_names_the_script_does_not_wire_it(tmp_path) -> None:
    write(tmp_path, WORKFLOW, f"  # {RUNS}")

    assert wiring.unwired(tmp_path) is not None


def test_one_file_of_several_is_enough(tmp_path) -> None:
    write(tmp_path, ".github/workflows/lint.yml", OTHER_STEPS)
    write(tmp_path, WORKFLOW, RUNS)

    assert wiring.unwired(tmp_path) is None


def test_the_reason_says_where_the_job_to_add_comes_from(tmp_path) -> None:
    reason = wiring.unwired(tmp_path)

    assert reason is not None
    assert "scripts/check_architecture_ratchet.py" in reason
    assert "templates/architecture.yml" in reason
