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
LAYERS = ["adapters", "application", "domain"]
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
    world.declaration = {"root_package": "shop", "layers": LAYERS}


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
    world.declaration["layers"] = ["interfaces", *LAYERS]
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
