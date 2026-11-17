"""Steps for knowledge_site.feature: the real build, on a throwaway repository."""

from __future__ import annotations

from types import SimpleNamespace

import build_site as site
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("knowledge_site.feature")

ALPHA, BETA = "/gates/alpha.md", "/gates/beta.md"
GATES_HUB = "/gates/index.md"
ALPHA_CODE = "scripts/alpha.py"
ALPHA_SCRIPT = (
    '"""alpha."""\nimport argparse\n\n'
    "argparse.ArgumentParser(description='Run alpha.').parse_args()\n"
)
FEATURE_TEXT = "Feature: alpha runs\n  Scenario: it runs\n    Given a thing\n"
STEPS = 'import alpha\nscenarios("alpha.feature")\n'


@pytest.fixture
def world(tmp_path):
    return SimpleNamespace(root=tmp_path, relations={}, out=tmp_path / "out", before={})


def page(kind: str, title: str, code: str | None = None, relations: dict | None = None) -> str:
    lines = ["---", f"type: {kind}", f"title: {title}"]
    if code:
        lines += ["code:", f"- {code}"]
    for name, targets in (relations or {}).items():
        lines += ["relations:", f"  {name}:", *(f"  - {t}" for t in targets)]
    return "\n".join([*lines, "---", f"# {title}", "", f"About {title}.", ""])


def put(world, relative: str, text: str) -> None:
    path = world.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_bundle(world) -> None:
    docs = "docs/knowledge"
    put(world, f"{docs}/bundle.yaml", "import-roots: [scripts]\n")
    put(world, f"{docs}/index.md", "# Home\n")
    put(world, f"{docs}{GATES_HUB}", "# Gates\n")
    put(world, f"{docs}/tooling/index.md", "# Tooling\n")
    put(world, f"{docs}{BETA}", page("Tool", "Beta"))
    for n in range(7):
        put(world, f"{docs}/tooling/t{n}.md", page("Tool", f"T{n}"))
    put(world, f"{docs}{ALPHA}", page("Tool", "Alpha", ALPHA_CODE, world.relations))
    put(world, ALPHA_CODE, ALPHA_SCRIPT)
    put(world, "tests/features/alpha.feature", FEATURE_TEXT)
    put(world, "tests/features/test_alpha.py", STEPS)


@given("a repository whose knowledge bundle has a gates folder and a tooling folder")
def _repo(world) -> None:
    world.relations = {}


@given("the page for alpha imports beta")
def _imports(world) -> None:
    world.relations["imports"] = [BETA]


@given(parsers.parse("alpha calls {count:d} pages of the tooling folder"))
def _calls(world, count: int) -> None:
    world.relations["calls"] = [f"/tooling/t{n}.md" for n in range(count)]


@when("the site source is built")
def _build(world) -> None:
    write_bundle(world)
    world.before = {p: p.read_text() for p in (world.root / "docs").rglob("*.md")}
    site.build(world.root, world.out)


def built(world, path: str) -> str:
    return (world.out / path.lstrip("/")).read_text()


@then(parsers.parse('the alpha page has a "{heading}" table naming {name}'))
def _alpha_table(world, heading: str, name: str) -> None:
    assert f"## {heading}" in built(world, ALPHA)
    assert f"[{name}]" in built(world, ALPHA).split(f"## {heading}")[1]


@then(parsers.parse('the beta page has a "{heading}" table naming {name}'))
def _beta_table(world, heading: str, name: str) -> None:
    assert f"[{name}]" in built(world, BETA).split(f"## {heading}")[1]


@then(parsers.parse('the alpha page has a diagram with the arrow "{kind}" to {name}'))
def _arrow(world, kind: str, name: str) -> None:
    text = built(world, ALPHA)
    assert "```mermaid" in text
    assert f"-->|{kind}| gates_beta_md" in text
    assert f'["{name}"]' in text


@then(parsers.parse('the alpha diagram shows "{label}" instead of the {count:d} pages'))
def _collapsed(world, label: str, count: int) -> None:
    diagram = built(world, ALPHA).split("```mermaid")[1].split("```")[0]
    assert f'["{label}"]' in diagram
    assert not any(f'["T{n}"]' in diagram for n in range(count))


@then(parsers.parse('the alpha page shows the help of "{script}"'))
def _help(world, script: str) -> None:
    text = built(world, ALPHA)
    assert f"$ python3 {script} --help" in text
    assert "Run alpha." in text


@then(parsers.parse('the alpha page shows the feature "{name}"'))
def _feature(world, name: str) -> None:
    text = built(world, ALPHA)
    assert "Scenario: it runs" in text
    assert f"tests/features/{name}.feature" in text


@then("the gates hub is unchanged")
def _hub(world) -> None:
    assert built(world, GATES_HUB) == "# Gates\n"


@then(parsers.parse('the overview names the folders "{first}" and "{second}"'))
def _overview(world, first: str, second: str) -> None:
    text = built(world, site.OVERVIEW)
    assert f'["{first}<br/>' in text
    assert f'["{second}<br/>' in text


@then("no page of docs/knowledge changed")
def _untouched(world) -> None:
    assert world.before
    assert {p: p.read_text() for p in world.before} == world.before
