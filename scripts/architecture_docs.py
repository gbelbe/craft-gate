"""The architecture documentation, generated from `architecture.yaml` and the real imports.

Two pictures, so the document cannot flatter the code:

    Declared  — the layers as `architecture.yaml` says they are stacked (intent)
    Actual    — how many imports really run between layers, read by grimp from the code;
                one that points outward is drawn dashed and counted as a violation (reality)

Because the second picture is derived from the imports, the document goes stale the moment
the code drifts, and `render_architecture.py --check` fails until it is regenerated: the
documentation cannot be out of date without CI saying so.

Copied into consuming repos next to render_architecture.py, which imports it.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import NamedTuple

import grimp

OVERVIEW = "overview.md"
HEADER = (
    "<!-- Generated from architecture.yaml and the code's imports by "
    "scripts/render_architecture.py; edit architecture.yaml, not this file. -->\n"
)
NO_PURPOSE = "-"
ROOT_KEY = "root_package"
LAYERS_KEY = "layers"


def layer_modules(data: dict) -> dict[str, list[str]]:
    """Each layer's modules, relative to the root package. A layer written as a bare name is
    the one module of that name; one written as ``{name, modules}`` owns several."""
    layers: dict[str, list[str]] = {}
    for entry in data[LAYERS_KEY]:
        name, modules = (
            (entry, [entry]) if isinstance(entry, str) else (entry["name"], entry["modules"])
        )
        layers[name] = list(modules)
    return layers


def layer_names(data: dict) -> list[str]:
    return list(layer_modules(data))


def layer_of(module: str, data: dict) -> str | None:
    """The layer (or shared module) a dotted module name sits in, if any."""
    root = data[ROOT_KEY]
    owners = {**layer_modules(data), **{name: [name] for name in data.get("shared") or []}}
    for name, modules in owners.items():
        for relative in modules:
            prefix = f"{root}.{relative}"
            if module == prefix or module.startswith(prefix + "."):
                return name
    return None


class CrossImport(NamedTuple):
    """One import that runs from a module of one layer to a module of another."""

    module: str
    imported: str
    source: str
    target: str


def cross_layer_imports(graph, data: dict) -> list[CrossImport]:
    found: list[CrossImport] = []
    for module in sorted(graph.modules):
        source = layer_of(module, data)
        for imported in sorted(graph.find_modules_directly_imported_by(module)):
            target = layer_of(imported, data)
            if source and target and source != target:
                found.append(CrossImport(module, imported, source, target))
    return found


def layer_edges(imports: list[CrossImport]) -> dict[tuple[str, str], int]:
    """How many imports run from one layer to another, per (from, to) pair."""
    edges: dict[tuple[str, str], int] = {}
    for found in imports:
        pair = (found.source, found.target)
        edges[pair] = edges.get(pair, 0) + 1
    return edges


def points_outward(source: str, target: str, layers: list[str]) -> bool:
    """True when *source* imports a layer stacked above it (shared modules are never outward)."""
    return source in layers and target in layers and layers.index(target) < layers.index(source)


def _declared_diagram(layers: list[str]) -> str:
    chain = " --> ".join(layers)
    return f"```mermaid\nflowchart TB\n    {chain}\n```"


def _edge_line(pair: tuple[str, str], count: int, layers: list[str]) -> str:
    source, target = pair
    if points_outward(source, target, layers):
        return f"    {source} -.->|{count} against the rule| {target}"
    return f"    {source} -->|{count}| {target}"


def _actual_diagram(edges: dict[tuple[str, str], int], layers: list[str]) -> str:
    lines = [_edge_line(pair, count, layers) for pair, count in sorted(edges.items())]
    return "\n".join(
        ["```mermaid", "flowchart TB", *(lines or ["    none[no imports between layers]"]), "```"]
    )


def _table(data: dict) -> str:
    layers, purposes, root = layer_modules(data), data.get("purposes") or {}, data[ROOT_KEY]
    names = list(layers)
    rows = ["| Layer | Purpose | Modules | May import |", "|---|---|---|---|"]
    for position, name in enumerate(names):
        modules = ", ".join(f"`{root}.{m}`" for m in layers[name])
        inward = ", ".join(f"`{inner}`" for inner in names[position + 1 :]) or "nothing"
        rows.append(f"| **{name}** | {purposes.get(name, NO_PURPOSE)} | {modules} | {inward} |")
    return "\n".join(rows)


def _breaches(imports: list[CrossImport], layers: list[str]) -> str:
    outward = [i for i in imports if points_outward(i.source, i.target, layers)]
    if not outward:
        return "None: every import between layers points inward."
    lines = [f"- `{i.module}` ({i.source}) imports `{i.imported}` ({i.target})" for i in outward]
    return "\n".join(lines)


def render_overview(data: dict, imports: list[CrossImport]) -> str:
    layers = layer_names(data)
    edges = layer_edges(imports)
    return "\n".join(
        [
            HEADER,
            "# Architecture",
            "",
            f"Root package `{data[ROOT_KEY]}`. Imports point inward: a layer may import "
            "only the layers listed after it in the table below.",
            "",
            "## Layers, as declared",
            "",
            _declared_diagram(layers),
            "",
            _table(data),
            "",
            "## Imports between layers, as they are in the code",
            "",
            "A dashed arrow is an import that breaks the rule.",
            "",
            _actual_diagram(edges, layers),
            "",
            "## Imports that break the rule",
            "",
            _breaches(imports, layers),
            "",
        ]
    )


def build_graph(data: dict, project: Path):
    """grimp's graph of the root package, found under the declared source root."""
    sys.path.insert(0, str(project / data.get("source_root", ".")))
    importlib.invalidate_caches()  # the code may have changed since the interpreter last looked
    try:
        return grimp.build_graph(data[ROOT_KEY], cache_dir=None)  # no cache in your repo
    finally:
        sys.path.pop(0)


def render_docs(data: dict, project: Path) -> dict[str, str]:
    """Each generated document, keyed by its path relative to the repository root."""
    imports = cross_layer_imports(build_graph(data, project), data)
    return {f"{data['docs']}/{OVERVIEW}": render_overview(data, imports)}
