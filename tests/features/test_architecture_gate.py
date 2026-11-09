"""Steps for architecture_gate.feature: render the contracts, run the real lint-imports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import render_architecture as arch
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("architecture_gate.feature")

LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"
ADAPTERS, LAYERS_KEY = "adapters", "layers"
LAYERS = [ADAPTERS, "application", "domain"]
DOCS = "docs/architecture"
BAD_IMPORT = "shop.domain.bad -> shop.adapters.db"


@pytest.fixture
def world(tmp_path):
    return SimpleNamespace(root=tmp_path, declaration={}, result=None)


def write(world, rel: str, text: str = "") -> None:
    path = world.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def declare(world) -> None:
    (world.root / arch.SOURCE).write_text(yaml.safe_dump(world.declaration))
    arch.main(["--path", str(world.root)])


def lint(world) -> subprocess.CompletedProcess[str]:
    declare(world)
    return subprocess.run(
        [str(LINT_IMPORTS), "--config", str(world.root / arch.TARGET)],
        cwd=world.root,
        env={"PYTHONPATH": str(world.root), "PATH": ""},
        capture_output=True,
        text=True,
    )


@given("an application with adapters, application and domain layers")
def _app(world) -> None:
    for package in ("shop", *(f"shop/{layer}" for layer in LAYERS)):
        write(world, f"{package}/__init__.py")
    write(world, "shop/adapters/db.py")
    write(world, "shop/domain/model.py")
    world.declaration = {"root_package": "shop", LAYERS_KEY: LAYERS}


@when("the application layer imports the domain")
def _inward(world) -> None:
    write(world, "shop/application/svc.py", "from shop.domain import model\n")


@when("the domain imports an adapter")
@given("the domain imports an adapter")
def _outward(world) -> None:
    write(world, "shop/domain/bad.py", "from shop.adapters import db\n")


@given("that import is listed as a known violation")
def _known(world) -> None:
    world.declaration["known_violations"] = [BAD_IMPORT]


@when("a module is added that no layer owns")
def _stray(world) -> None:
    write(world, "shop/stray.py")


@when("that module is declared shared")
def _shared(world) -> None:
    world.declaration["shared"] = ["stray"]


@when("the declaration gains a layer without re-rendering")
def _stale(world) -> None:
    declare(world)
    world.declaration[LAYERS_KEY] = ["interfaces", *LAYERS]
    (world.root / arch.SOURCE).write_text(yaml.safe_dump(world.declaration))


@then("the architecture check passes")
def _passes(world) -> None:
    result = lint(world)
    assert result.returncode == 0, result.stdout + result.stderr


@then("the architecture check fails")
def _fails(world) -> None:
    world.result = lint(world)
    assert world.result.returncode != 0, world.result.stdout


@then(parsers.parse('the report names the import "{edge}"'))
@then(parsers.parse('the report names the module "{edge}"'))
def _named(world, edge: str) -> None:
    assert edge in world.result.stdout


@then("the render check fails")
def _render_fails(world) -> None:
    assert arch.main(["--path", str(world.root), "--check"]) == 1


@given("the architecture documentation is requested")
def _docs_requested(world) -> None:
    world.declaration["docs"] = DOCS


@given("the documentation is generated")
@when("the documentation is generated")
def _generate(world) -> None:
    declare(world)


@then(parsers.parse('the overview contains "{text}"'))
def _overview_has(world, text: str) -> None:
    assert text in (world.root / DOCS / "overview.md").read_text()


@given("the adapters layer owns the cli and api modules")
def _multi(world) -> None:
    write(world, "shop/cli.py")
    write(world, "shop/api.py")
    world.declaration[LAYERS_KEY] = [
        {"name": ADAPTERS, "modules": [ADAPTERS, "cli", "api"]},
        *LAYERS[1:],
    ]


@when("the cli module imports the api module")
def _sibling(world) -> None:
    write(world, "shop/cli.py", "from shop import api\n")


@given("the repository keeps a contract of its own in pyproject.toml")
def _own_contract(world) -> None:
    write(
        world,
        "pyproject.toml",
        '[tool.importlinter]\nroot_packages = ["shop"]\n\n[[tool.importlinter.contracts]]\n'
        'name = "own"\ntype = "forbidden"\nsource_modules = ["shop.application"]\n'
        'forbidden_modules = ["shop.domain"]\n',
    )
    write(world, "shop/application/svc.py", "from shop.domain import model\n")


@then("the repository's own contract is still checked")
def _own_checked(world) -> None:
    result = subprocess.run(
        [str(LINT_IMPORTS)],
        cwd=world.root,
        env={"PYTHONPATH": str(world.root), "PATH": ""},
        capture_output=True,
        text=True,
    )
    assert "own BROKEN" in result.stdout, result.stdout
