"""The guidance an agent reads covers every gate and the config that sets them.

AGENTS.md is this repo's; the snippet is what consumers paste into theirs; the skill is what
Claude Code loads. If a gate or a rule is added and one of them is not updated, an agent follows
stale instructions, so each must name all of them.
"""

from __future__ import annotations

import pytest
from conftest import ROOT

GUIDANCE = {
    "AGENTS.md": ROOT / "AGENTS.md",
    "snippet": ROOT / "templates" / "AGENTS.md.snippet.md",
}
GATES = ["refactor-first", "complexity", "patch-coverage", "mutation-ratchet", "behaviour-coverage"]
RULES = {
    "the config file": "craft-gate.toml",
    "the exemption trailer": "Tidy-Exempt:",
    "new code is never exempt": "new code is never exempt",
    "never loosen to pass": "never loosen a value",
    "test gates are on by default": "on by default",
    "scenarios cover changed lines": "scenario",
    "design review": "design_review.py",
    "the independent reviewer": "craft-review",
    "the PR checklist": "PULL_REQUEST_TEMPLATE.md",
    "a looser value is listed": "lists every value the change loosens",
}


@pytest.mark.parametrize("name", sorted(GUIDANCE))
@pytest.mark.parametrize("gate", GATES)
def test_each_gate_is_named(name, gate) -> None:
    assert gate in GUIDANCE[name].read_text()


@pytest.mark.parametrize("name", sorted(GUIDANCE))
@pytest.mark.parametrize("rule", sorted(RULES))
def test_each_rule_is_stated(name, rule) -> None:
    assert RULES[rule] in GUIDANCE[name].read_text(), rule


def test_the_skill_points_at_the_config_and_the_rule_against_loosening() -> None:
    skill = (ROOT / "skills" / "tidy-first" / "SKILL.md").read_text()

    assert "craft-gate.toml" in skill
    assert "never loosen" in skill
