"""Does the repo run the architecture ratchet anywhere?

`check_architecture_ratchet.py` is only a rule once something runs it. craft-gate ships the
script, but the job that calls it is pasted into the repo's own workflow by hand
(`templates/architecture.yml`), so a repo that took the script in an update and never pasted the
job has a list of known violations that nothing makes shrink.

`render_architecture.py --check` already runs in every repo that declares an `architecture.yaml`,
so it asks `unwired` and fails until a workflow or a pre-commit hook runs the ratchet. Copied into
consuming repos next to `render_architecture.py`, which imports it.
"""

from __future__ import annotations

from pathlib import Path

RATCHET = "check_architecture_ratchet.py"
WORKFLOWS = ".github/workflows"
WORKFLOW_GLOBS = ("*.yml", "*.yaml")
HOOK_FILES = (".pre-commit-config.yaml", ".pre-commit-config.yml")
TEMPLATE = "templates/architecture.yml"


def _wiring_files(root: Path) -> list[Path]:
    """The workflows and hook files the repo has."""
    workflows = [p for pattern in WORKFLOW_GLOBS for p in sorted((root / WORKFLOWS).glob(pattern))]
    return [p for p in [*workflows, *(root / name for name in HOOK_FILES)] if p.is_file()]


def _runs_the_ratchet(text: str) -> bool:
    """A line that names the script and is not a comment."""
    return any(RATCHET in line for line in text.splitlines() if not line.lstrip().startswith("#"))


def unwired(root: Path) -> str | None:
    """Why nothing in *root* runs the ratchet, or None when a workflow or a hook does."""
    if any(_runs_the_ratchet(p.read_text()) for p in _wiring_files(root)):
        return None
    return (
        f"no workflow under {WORKFLOWS} and no pre-commit hook runs scripts/{RATCHET}, "
        "so nothing makes the known violations in architecture.yaml shrink; "
        f"add the job from craft-gate's {TEMPLATE}"
    )
