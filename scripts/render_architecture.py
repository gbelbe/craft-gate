"""Render the import-linter contracts from `architecture.yaml`, the declared hexagon.

`architecture.yaml` is the one file a person edits to say how the application is layered:

    root_package: shop
    layers: [adapters, application, domain]   # outermost first; each imports only what follows
    shared: [utils]                           # optional: modules outside the layering
    independent: [shop.adapters.web, shop.adapters.db]   # optional: may not import each other
    known_violations:                         # optional baseline: imports that break it today
      - shop.domain.pricing -> shop.adapters.db

From it this writes `.importlinter`, which `lint-imports` (import-linter) enforces. A layers
contract makes the direction of imports the architecture's rule; `exhaustive` makes a module that
belongs to no layer an error, so the declaration cannot fall behind the code. `known_violations`
lets the rule be adopted on code that breaks it: anything new fails, and a baseline line that no
longer matches an import fails too (import-linter's own check), so the list can only shrink.

Usage:
    python scripts/render_architecture.py [--path .]            # write .importlinter
    python scripts/render_architecture.py [--path .] --check    # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

SOURCE = "architecture.yaml"
TARGET = ".importlinter"
HEADER = (
    f"# Generated from {SOURCE} by scripts/render_architecture.py; edit that file, not this one.\n"
)
ERROR_EXIT = 2
ROOT_KEY = "root_package"
LAYERS_KEY = "layers"


class ArchitectureError(Exception):
    """architecture.yaml is missing or does not describe a usable set of layers."""


def _names(data: dict, key: str) -> list[str]:
    values = data.get(key) or []
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ArchitectureError(f"'{key}' must be a list of names")
    return values


def validate(data: dict) -> None:
    """Raise ArchitectureError unless *data* declares a root package and distinct layers."""
    if not isinstance(data.get(ROOT_KEY), str):
        raise ArchitectureError(f"'{ROOT_KEY}' is required")
    layers = _names(data, LAYERS_KEY)
    if not layers:
        raise ArchitectureError(f"'{LAYERS_KEY}' must name at least one layer")
    if len(set(layers)) != len(layers):
        raise ArchitectureError(f"'{LAYERS_KEY}' lists a layer twice")
    root = data[ROOT_KEY]
    for module in _names(data, "independent"):
        if not module.startswith(root + "."):
            raise ArchitectureError(f"'independent' module '{module}' is not under '{root}'")
    _names(data, "shared")
    _names(data, "known_violations")


def _lines(key: str, values: list[str]) -> list[str]:
    """An import-linter multi-line option: ``key =`` then one indented value per line."""
    return [f"{key} =", *(f"    {value}" for value in values)] if values else []


def _layers_contract(data: dict) -> list[str]:
    return [
        "[importlinter:contract:layers]",
        "name = Hexagonal layers: imports point inward",
        "type = layers",
        f"containers = {data[ROOT_KEY]}",
        *_lines(LAYERS_KEY, _names(data, LAYERS_KEY)),
        "exhaustive = true",
        *_lines("exhaustive_ignores", _names(data, "shared")),
        *_lines("ignore_imports", _names(data, "known_violations")),
    ]


def _independence_contract(data: dict) -> list[str]:
    modules = _names(data, "independent")
    if not modules:
        return []
    return [
        "",
        "[importlinter:contract:independence]",
        "name = Adapters do not depend on each other",
        "type = independence",
        *_lines("modules", modules),
    ]


def render(data: dict) -> str:
    """The text of `.importlinter` for a declaration."""
    validate(data)
    lines = [
        HEADER,
        "[importlinter]",
        f"root_package = {data[ROOT_KEY]}",
        "",
        *_layers_contract(data),
        *_independence_contract(data),
    ]
    return "\n".join(lines) + "\n"


def load(path: Path) -> dict:
    if not path.is_file():
        raise ArchitectureError(f"{path} not found")
    return yaml.safe_load(path.read_text()) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    parser.add_argument("--check", action="store_true", help="fail if .importlinter is stale")
    args = parser.parse_args(argv)
    root = Path(args.path)
    try:
        wanted = render(load(root / SOURCE))
    except ArchitectureError as error:
        print(f"✗ {error}", file=sys.stderr)
        return ERROR_EXIT
    target = root / TARGET
    current = target.read_text() if target.is_file() else None
    if args.check:
        if current != wanted:
            print(f"✗ {TARGET} is out of date; run scripts/render_architecture.py")
            return 1
        print(f"✓ {TARGET} matches {SOURCE}")
        return 0
    target.write_text(wanted)
    print(f"✓ wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
