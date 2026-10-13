#!/usr/bin/env python3
"""Which of the test gates run in this repo: patch coverage, mutation, behaviour (Gherkin) coverage.

All three are on by default. A repo turns one off in pyproject.toml, with a reason:

    [tool.craft-gate.mutation]
    enabled = false
    reason = "suite takes 40 minutes; revisit when it is split"

A gate that cannot work (no pytest suite, no [tool.mutmut], no .feature files) is an error that
says what to add or how to opt out, rather than a job that passes because it found nothing to
check. Mutation and behaviour coverage both need the suite patch coverage measures, so they are
skipped, with that as the reason, when patch coverage is off.

Usage (as the CI template calls it):
    python scripts/gate_config.py <gate> [--path .]

Prints the decision, appends it to $GITHUB_OUTPUT when set (status=run|skip plus the gate's
settings) and exits 1 only on misconfiguration.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

RUN, SKIP, ERROR = "run", "skip", "error"
PATCH, MUTATION, BDD = "patch-coverage", "mutation", "bdd"
GATES = (PATCH, MUTATION, BDD)
ENABLED, REASON, THRESHOLD, PATHS = "enabled", "reason", "threshold", "paths"
TABLE = "craft-gate"

DEFAULTS: dict[str, dict[str, Any]] = {
    PATCH: {ENABLED: True, REASON: "", THRESHOLD: 90, "source": ""},
    MUTATION: {ENABLED: True, REASON: "", THRESHOLD: 80, "improvement": 20},
    BDD: {ENABLED: True, REASON: "", THRESHOLD: 80, PATHS: ["tests/features"]},
}
NEEDS_COVERAGE = (MUTATION, BDD)
_PRUNED_DIRS = {".git", ".venv", "venv", "node_modules", "site-packages", "build", "dist", ".tox"}
_PERCENT_MAX = 100


def _where(gate: str | None = None) -> str:
    """How a section is spelled in pyproject.toml, for messages."""
    return f"[tool.{TABLE}.{gate}]" if gate else f"[tool.{TABLE}]"


class ConfigError(Exception):
    """pyproject.toml's [tool.craft-gate] table is unusable."""


@dataclass(frozen=True)
class Decision:
    gate: str
    status: str
    reason: str = ""
    settings: dict[str, Any] = field(default_factory=dict)


def _read_tool_table(root: Path) -> dict[str, Any]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text()).get("tool", {})
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"pyproject.toml does not parse: {exc}") from exc


def _check_value(gate: str, key: str, value: Any) -> None:
    default = DEFAULTS[gate][key]
    ok = isinstance(value, type(default))
    if key in (THRESHOLD, "improvement"):
        ok = isinstance(value, int) and 0 <= value <= _PERCENT_MAX
    elif key == PATHS:
        ok = isinstance(value, list) and all(isinstance(p, str) for p in value)
    if not ok:
        raise ConfigError(f"{_where(gate)} {key} is not valid: {value!r}")


def _gate_settings(table: dict[str, Any], gate: str) -> dict[str, Any]:
    given = table.get(gate, {})
    unknown = sorted(set(given) - set(DEFAULTS[gate]))
    if unknown:
        raise ConfigError(f"{_where(gate)} has unknown key(s): {', '.join(unknown)}")
    for key, value in given.items():
        _check_value(gate, key, value)
    return {**DEFAULTS[gate], **given}


def _load(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """(settings per gate, the whole [tool] table), validated."""
    tool = _read_tool_table(root)
    table = tool.get(TABLE, {})
    unknown = sorted(set(table) - set(GATES))
    if unknown:
        raise ConfigError(f"{_where()} has unknown gate(s): {', '.join(unknown)}")
    return {gate: _gate_settings(table, gate) for gate in GATES}, tool


def _off_reason(settings: dict[str, Any], gate: str) -> str | None:
    """Why this gate is switched off, None when it is on. A switch with no reason is an error."""
    if settings[ENABLED]:
        return None
    reason = settings[REASON].strip()
    if not reason:
        raise ConfigError(f"{_where(gate)} enabled = false needs a non-empty reason")
    return reason


def _has_pytest_suite(root: Path) -> bool:
    for _dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _PRUNED_DIRS]
        if any(
            f.startswith("test_") and f.endswith(".py") or f.endswith("_test.py") for f in files
        ):
            return True
    return False


def _has_features(root: Path, paths: list[str]) -> bool:
    return any(next((root / p).rglob("*.feature"), None) for p in paths if (root / p).is_dir())


def _missing(gate: str, root: Path, settings: dict[str, Any], tool: dict[str, Any]) -> str | None:
    """What the gate needs and the repo lacks, as an instruction; None when it has it."""
    optout = f"or set [tool.{TABLE}.{gate}] enabled = false with a reason"
    if gate == PATCH and not _has_pytest_suite(root):
        return f"no pytest suite found; add tests, {optout}"
    if gate == MUTATION and "mutmut" not in tool:
        return f"[tool.mutmut] is missing from pyproject.toml; configure mutmut, {optout}"
    if gate == BDD and not _has_features(root, settings[PATHS]):
        return f"no .feature files under {', '.join(settings['paths'])}; add scenarios, {optout}"
    return None


def decide(root: Path, gate: str) -> Decision:
    try:
        settings, tool = _load(root)
        own = settings[gate]
        reason = _off_reason(own, gate)
        if reason is None and gate in NEEDS_COVERAGE:
            upstream = _off_reason(settings[PATCH], PATCH)
            reason = None if upstream is None else f"patch-coverage is off ({upstream})"
    except ConfigError as exc:
        return Decision(gate, ERROR, str(exc))
    if reason is not None:
        return Decision(gate, SKIP, reason)
    missing = _missing(gate, root, own, tool)
    if missing is not None:
        return Decision(gate, ERROR, missing)
    return Decision(gate, RUN, settings=own)


def skipped_gates(root: Path) -> list[tuple[str, str]]:
    decisions = (decide(root, gate) for gate in GATES)
    return [(d.gate, d.reason) for d in decisions if d.status == SKIP]


def render_skipped(skipped: list[tuple[str, str]]) -> str:
    """The PR-comment section naming each gate this repo has switched off, and why."""
    if not skipped:
        return ""
    rows = [f"| `{gate}` | {reason} |" for gate, reason in skipped]
    return "\n".join(
        ["**Gates switched off in this repo**", "", "| Gate | Reason |", "|---|---|", *rows]
    )


def _output_lines(decision: Decision) -> list[str]:
    lines = [f"status={decision.status}", f"reason={decision.reason}"]
    for key, value in decision.settings.items():
        text = " ".join(value) if isinstance(value, list) else str(value)
        lines.append(f"{key}={text}")
    return lines


def _publish(decision: Decision) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as handle:
            handle.write("\n".join(_output_lines(decision)) + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and decision.status == SKIP:
        with open(summary, "a") as handle:
            handle.write(f"Skipped `{decision.gate}`: {decision.reason}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=GATES)
    parser.add_argument("--path", default=".", help="repo root (default: current directory)")
    args = parser.parse_args(argv)

    decision = decide(Path(args.path).resolve(), args.gate)
    if decision.status == ERROR:
        print(f"✗ {decision.gate}: {decision.reason}", file=sys.stderr)
        return 1
    _publish(decision)
    if decision.status == SKIP:
        print(f"{decision.gate}: skipped on purpose: {decision.reason}")
    else:
        print(f"{decision.gate}: running")
    return 0


if __name__ == "__main__":
    sys.exit(main())
