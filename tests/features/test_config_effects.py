"""Step definitions for config_effects.feature: move one value, watch the verdict move."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("config_effects.feature")

CALM = "def calm(x):\n    return x + 1\n\n\nprint(calm(1))\n"
SMELLY = "def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n\n\nprint(f(1))\n"
FEATURE = "Feature: x\n  Scenario: y\n    Given z\n"
MOD = "mod.py"
ADDED = "added"
PATH_FLAG = "--path"
MAIN = "main"
EXEMPT = "\n\nTidy-Exempt: a spike"


def branches(name: str, count: int) -> str:
    body = "".join(f"    if x == {i}:\n        r += {i}\n" for i in range(count))
    return f"def {name}(x):\n    r = 0\n{body}    return r\n"


def nested(name: str, depth: int) -> str:
    lines = [f"def {name}(x):"]
    for level in range(depth):
        lines.append("    " * (level + 1) + "if x:")
    lines.append("    " * (depth + 1) + "return x")
    lines.append("    return 0")
    return "\n".join(lines) + "\n"


def lines_long(name: str, count: int) -> str:
    body = "".join(f"    x{i} = {i}\n" for i in range(count - 2))
    return f"def {name}():\n{body}    return x0\n"


def parameters(name: str, count: int) -> str:
    names = ", ".join(f"p{i}" for i in range(count))
    return f"def {name}({names}):\n    return p0\n"


@pytest.fixture
def world(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(repo=repo, config={}, added="", message="feat: change", exempt=False)


def toml_value(literal: str) -> str:
    return literal  # the scenario text is already TOML: 75, "mypkg", ["a", "b"], true


def write_config(world) -> None:
    sections: dict[str, list[str]] = {}
    for dotted, literal in world.config.items():
        section, key = dotted.split(".", 1)
        sections.setdefault(section, []).append(f"{key} = {toml_value(literal)}")
    text = "".join(f"[{s}]\n" + "\n".join(lines) + "\n\n" for s, lines in sections.items())
    (world.repo.path / "craft-gate.toml").write_text(text)
    if world.mutmut:  # mutmut's own section lives in pyproject.toml, not in craft-gate.toml
        (world.repo.path / "pyproject.toml").write_text("[tool.mutmut]\nsource_paths = ['src']\n")


def commit_change(world) -> None:
    write_config(world)
    code = (world.repo.path / MOD).read_text() + world.added
    message = world.message + (EXEMPT if world.exempt else "")
    world.repo.branch("feature")
    world.repo.commit(message, mod_py=code)


# -- givens -------------------------------------------------------------------------------------


@given("a repo whose base commit has one calm module")
def _calm_base(world) -> None:
    world.mutmut = False
    world.repo.commit("base", mod_py=CALM, tests__test_mod_py="def test_x():\n    assert True\n")


@given("the base commit already has a smelly module")
def _smelly_base(world) -> None:
    world.repo.commit("smelly", mod_py=SMELLY)


@given(parsers.parse("the config sets {dotted} to {literal}"))
def _config(world, dotted, literal) -> None:
    world.config[dotted] = literal


@given("a [tool.mutmut] section exists")
def _mutmut(world) -> None:
    world.mutmut = True


@given(parsers.parse("the repo has scenarios under {folder}"))
def _scenarios(world, folder) -> None:
    world.repo.write(f"{folder}/a.feature", FEATURE)


@given(parsers.parse("the change adds a function with {n:d} flat branches"))
def _branches(world, n) -> None:
    world.added = "\n\n" + branches(ADDED, n)


@given(parsers.parse("the change adds a function nested {n:d} levels deep"))
def _nested(world, n) -> None:
    world.added = "\n\n" + nested(ADDED, n)


@given(parsers.parse("the change adds a function with {n:d} parameters"))
def _parameters(world, n) -> None:
    world.added = "\n\n" + parameters(ADDED, n)


@given(parsers.parse("the change adds a function {n:d} lines long"))
def _long(world, n) -> None:
    world.added = "\n\n" + lines_long(ADDED, n)


@given(parsers.parse("the change repeats a {n:d}-character literal {times:d} times"))
def _literal(world, n, times) -> None:
    literal = "x" * n
    world.added = "\n\n" + "".join(f'v{i} = "{literal}"\n' for i in range(times))


@given("the change only edits a comment in the smelly module")
def _comment(world) -> None:
    world.added = "# a comment\n"


@given("the commit carries a Tidy-Exempt trailer")
def _exempt(world) -> None:
    world.exempt = True


# -- whens ----------------------------------------------------------------------------------------


@when("the complexity ratchet runs")
def _run_complexity(world, run_main) -> None:
    import check_complexity_ratchet as ratchet

    commit_change(world)
    world.exit = run_main(ratchet, "--base", MAIN, PATH_FLAG, ".")


@when("Refactor First runs")
def _run_refactor_first(world, run_main) -> None:
    import check_refactor_first as gate

    commit_change(world)
    world.exit = run_main(gate, "--base", MAIN, PATH_FLAG, str(world.repo.path))


@when("the design review runs")
def _run_design_review(world) -> None:
    import design_review as review

    commit_change(world)
    world.notes = review.review_diff(world.repo.path, MAIN)


@when(parsers.parse("the workflow asks for the {gate} gate"))
def _ask_gate(world, gate, monkeypatch) -> None:
    import gate_config

    write_config(world)
    out = world.repo.path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    world.exit = gate_config.main([gate, PATH_FLAG, str(world.repo.path)])
    world.published = out.read_text().splitlines() if out.exists() else []


# -- thens ----------------------------------------------------------------------------------------


@then(parsers.re(r"(the complexity ratchet|Refactor First) (?P<verdict>passes|fails)"))
def _verdict(world, verdict) -> None:
    assert (world.exit == 0) == (verdict == "passes"), f"exit code {world.exit}"


@then(parsers.parse('the design review {outcome} a prompt about "{word}"'))
def _prompt(world, outcome, word) -> None:
    mentioned = any(word in note.message for note in world.notes)

    assert mentioned == (outcome == "has")


@then(parsers.parse("the workflow is told {line}"))
def _published(world, line) -> None:
    assert world.exit == 0
    assert line in world.published, world.published
