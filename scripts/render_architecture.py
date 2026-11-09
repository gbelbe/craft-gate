"""Render the import-linter contracts from `architecture.yaml`, the declared hexagon.

`architecture.yaml` is the one file a person edits to say how the application is layered:

    root_package: shop
    layers:                                   # outermost first; each imports only what follows
      - {name: adapters, modules: [cli, api]} # a layer may own several modules or packages
      - application                           # a bare name is the module of that name
      - domain
    shared: [utils]                           # optional: modules outside the layering
    independent: [shop.adapters.web, shop.adapters.db]   # optional: may not import each other
    known_violations:                         # optional baseline: imports that break it today
      - shop.domain.pricing -> shop.adapters.db
    purposes: {domain: "business rules, no I/O"}   # optional: one line per layer, shown in the docs
    docs: docs/architecture                   # optional: also generate the diagrams here
    source_root: src                          # optional: where root_package lives (default .)

From it this writes `.architecture.importlinter`, which `lint-imports --config` (import-linter)
enforces. It is a file of its own because import-linter reads one configuration only, and a
`.importlinter` would silently replace the contracts a repo keeps in `pyproject.toml` or
`setup.cfg`; run both. A layers contract makes the direction of imports the architecture's rule;
`exhaustive` makes a module that belongs to no layer an error, so the declaration cannot fall
behind the code. `known_violations` lets the rule be adopted on code that breaks it: anything new
fails, and a baseline line that no longer matches an import fails too (import-linter's own check),
so the list can only shrink.

Usage:
    python scripts/render_architecture.py [--path .]            # write the generated files
    python scripts/render_architecture.py [--path .] --check    # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
from architecture_docs import (  # noqa: E402
    LAYERS_KEY,
    ROOT_KEY,
    layer_modules,
    layer_names,
    render_docs,
)

SOURCE = "architecture.yaml"
TARGET = ".architecture.importlinter"
HEADER = (
    f"# Generated from {SOURCE} by scripts/render_architecture.py; edit that file, not this one.\n"
)
ERROR_EXIT = 2


class ArchitectureError(Exception):
    """architecture.yaml is missing or does not describe a usable set of layers."""


def _names(data: dict, key: str) -> list[str]:
    values = data.get(key) or []
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ArchitectureError(f"'{key}' must be a list of names")
    return values


def _check_layers(data: dict) -> None:
    entries = data.get(LAYERS_KEY)
    if not isinstance(entries, list) or not entries:
        raise ArchitectureError(f"'{LAYERS_KEY}' must name at least one layer")
    for entry in entries:
        _check_layer_entry(entry)
    names = [e if isinstance(e, str) else e["name"] for e in entries]
    if len(set(names)) != len(names):
        raise ArchitectureError(f"'{LAYERS_KEY}' lists a layer twice")
    owned = [m for modules in layer_modules(data).values() for m in modules]
    twice = sorted({m for m in owned if owned.count(m) > 1})
    if twice:
        raise ArchitectureError(f"'{LAYERS_KEY}' gives {twice} to more than one layer")


def _check_layer_entry(entry: object) -> None:
    if isinstance(entry, str):
        return
    modules = entry.get("modules") if isinstance(entry, dict) else None
    if not (isinstance(entry, dict) and isinstance(entry.get("name"), str)):
        raise ArchitectureError(f"'{LAYERS_KEY}' entries are a name or {{name, modules}}")
    if not (isinstance(modules, list) and modules and all(isinstance(m, str) for m in modules)):
        raise ArchitectureError(f"layer '{entry['name']}' needs a list of 'modules'")


def validate(data: dict) -> None:
    """Raise ArchitectureError unless *data* declares a root package and distinct layers."""
    if not isinstance(data.get(ROOT_KEY), str):
        raise ArchitectureError(f"'{ROOT_KEY}' is required")
    _check_layers(data)
    root = data[ROOT_KEY]
    for module in _names(data, "independent"):
        if not module.startswith(root + "."):
            raise ArchitectureError(f"'independent' module '{module}' is not under '{root}'")
    _names(data, "shared")
    _names(data, "known_violations")
    _check_purposes(data)


def _check_purposes(data: dict) -> None:
    purposes = data.get("purposes") or {}
    unknown = sorted(set(purposes) - set(layer_names(data)))
    if not isinstance(purposes, dict) or unknown:
        raise ArchitectureError(f"'purposes' must describe declared layers, not {unknown}")


def _lines(key: str, values: list[str]) -> list[str]:
    """An import-linter multi-line option: ``key =`` then one indented value per line."""
    return [f"{key} =", *(f"    {value}" for value in values)] if values else []


def _layers_contract(data: dict) -> list[str]:
    return [
        "[importlinter:contract:layers]",
        "name = Hexagonal layers: imports point inward",
        "type = layers",
        f"containers = {data[ROOT_KEY]}",
        *_lines(LAYERS_KEY, [" : ".join(m) for m in layer_modules(data).values()]),
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


def outputs(root: Path) -> dict[Path, str]:
    """Every file the declaration determines: the contracts, and the docs when `docs` is set."""
    data = load(root / SOURCE)
    files = {root / TARGET: render(data)}
    if data.get("docs"):
        files |= {root / rel: text for rel, text in render_docs(data, root.resolve()).items()}
    return files


def stale(files: dict[Path, str]) -> list[Path]:
    return [p for p, text in files.items() if not p.is_file() or p.read_text() != text]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    parser.add_argument("--check", action="store_true", help="fail if a generated file is stale")
    args = parser.parse_args(argv)
    root = Path(args.path)
    try:
        files = outputs(root)
    except ArchitectureError as error:
        print(f"✗ {error}", file=sys.stderr)
        return ERROR_EXIT
    if args.check:
        return report_stale(stale(files), root)
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    print("✓ wrote " + ", ".join(p.relative_to(root).as_posix() for p in files))
    return 0


def report_stale(paths: list[Path], root: Path) -> int:
    for path in paths:
        name = path.relative_to(root).as_posix()
        print(f"✗ {name} is out of date; run scripts/render_architecture.py")
    if not paths:
        print(f"✓ generated files match {SOURCE}")
    return 1 if paths else 0


if __name__ == "__main__":
    sys.exit(main())
