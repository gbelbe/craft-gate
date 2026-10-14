"""Steps for config_loosening.feature: move a value between two commits, see if it is reported."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("config_loosening.feature")

MAIN = "main"
MOD = "def calm(x):\n    return x + 1\n"
CONFIG_FILE, PYPROJECT = "craft-gate.toml", "pyproject.toml"


@pytest.fixture
def world(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(
        repo=repo, base={}, head={}, base_file=CONFIG_FILE, head_file=CONFIG_FILE
    )


def config_text(values: dict[str, str], file: str) -> str:
    """The values as TOML: [section] in craft-gate.toml, [tool.craft-gate.section] in pyproject."""
    prefix = "tool.craft-gate." if file == PYPROJECT else ""
    sections: dict[str, list[str]] = {}
    for dotted, literal in values.items():
        section, key = dotted.split(".", 1)
        sections.setdefault(section, []).append(f"{key} = {literal}")
    return "".join(f"[{prefix}{s}]\n" + "\n".join(lines) + "\n\n" for s, lines in sections.items())


def commit_both(world) -> None:
    world.repo.commit("base", mod_py=MOD)
    if world.base:
        world.repo.write(world.base_file, config_text(world.base, world.base_file))
        world.repo.git("add", "-A")
        world.repo.commit_staged("base config")
    world.repo.branch("feature")
    if world.base_file != world.head_file:
        (world.repo.path / world.base_file).unlink()
    world.repo.write(world.head_file, config_text(world.head, world.head_file))
    world.repo.git("add", "-A")
    world.repo.commit_staged("head config")


# -- givens -------------------------------------------------------------------------------------


@given(parsers.parse("the base commit sets {dotted} to {literal}"))
def _base(world, dotted, literal) -> None:
    world.base[dotted] = literal


@given(parsers.parse("the head commit sets {dotted} to {literal}"))
def _head(world, dotted, literal) -> None:
    world.head[dotted] = literal


@given("the base commit has no craft-gate.toml")
def _no_base() -> None:
    """Nothing to write: the base is the defaults."""


@given(parsers.parse("the base commit keeps {dotted} at {literal} in pyproject.toml"))
def _base_pyproject(world, dotted, literal) -> None:
    world.base[dotted], world.base_file = literal, PYPROJECT


@given(parsers.parse("the head commit keeps {dotted} at {literal} in craft-gate.toml"))
def _head_standalone(world, dotted, literal) -> None:
    world.head[dotted] = literal


# -- whens ----------------------------------------------------------------------------------------


@when("the loosening check runs")
def _run(world) -> None:
    import config_loosening

    commit_both(world)
    world.found = config_loosening.review_config(world.repo.path, MAIN)


@when("the pull request comment is drafted")
def _comment(world, run_main, capsys) -> None:
    import craftcov_pr_comment

    commit_both(world)
    run_main(craftcov_pr_comment, "--base", MAIN, "--path", str(world.repo.path), "--dry-run")
    world.comment = capsys.readouterr().out


# -- thens ----------------------------------------------------------------------------------------


@then(parsers.re(r"the change to (?P<dotted>\S+) (?P<verdict>is reported|is not reported)"))
def _reported(world, dotted, verdict) -> None:
    names = [f"{item.section}.{item.key}" for item in world.found]

    assert (dotted in names) == (verdict == "is reported"), names


@then("nothing is reported")
def _nothing(world) -> None:
    assert world.found == []


@then(parsers.parse('the comment has a "{title}" section naming {dotted}'))
def _section(world, title, dotted) -> None:
    section = world.comment.split(f"**{title}**", 1)[1]

    assert re.search(rf"`{re.escape(dotted)}`", section)
