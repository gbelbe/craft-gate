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


def _tiers_of_entries(data: dict) -> list[list]:
    """The declared tiers, outermost first: a plain entry is a tier of one layer, a list of
    entries is a tier of sibling layers that sit at the same depth."""
    return [item if isinstance(item, list) else [item] for item in data[LAYERS_KEY]]


def _name_and_modules(entry: str | dict) -> tuple[str, list[str]]:
    return (entry, [entry]) if isinstance(entry, str) else (entry["name"], list(entry["modules"]))


def layer_modules(data: dict) -> dict[str, list[str]]:
    """Each layer's modules, relative to the root package. A layer written as a bare name is
    the one module of that name; one written as ``{name, modules}`` owns several."""
    pairs = (_name_and_modules(entry) for tier in _tiers_of_entries(data) for entry in tier)
    return dict(pairs)


def layer_tiers(data: dict) -> list[list[str]]:
    """The layer names grouped by tier, outermost first."""
    return [[_name_and_modules(entry)[0] for entry in tier] for tier in _tiers_of_entries(data)]


def layer_names(data: dict) -> list[str]:
    return [name for tier in layer_tiers(data) for name in tier]


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


def points_outward(source: str, target: str, tiers: list[list[str]]) -> bool:
    """True when *source* imports a layer it may not: one in a tier above it, or a sibling in its
    own tier (shared modules are never outward)."""
    depth = {name: position for position, tier in enumerate(tiers) for name in tier}
    if source not in depth or target not in depth:
        return False
    return depth[target] < depth[source] or (depth[target] == depth[source] and source != target)


def _declared_diagram(tiers: list[list[str]]) -> str:
    chain = " --> ".join(" & ".join(tier) for tier in tiers)
    return f"```mermaid\nflowchart TB\n    {chain}\n```"


def _edge_line(pair: tuple[str, str], count: int, tiers: list[list[str]]) -> str:
    source, target = pair
    if points_outward(source, target, tiers):
        return f"    {source} -.->|{count} against the rule| {target}"
    return f"    {source} -->|{count}| {target}"


def _actual_diagram(edges: dict[tuple[str, str], int], tiers: list[list[str]]) -> str:
    lines = [_edge_line(pair, count, tiers) for pair, count in sorted(edges.items())]
    return "\n".join(
        ["```mermaid", "flowchart TB", *(lines or ["    none[no imports between layers]"]), "```"]
    )


def _table(data: dict) -> str:
    layers, purposes, root = layer_modules(data), data.get("purposes") or {}, data[ROOT_KEY]
    tiers = layer_tiers(data)
    rows = ["| Layer | Purpose | Modules | May import |", "|---|---|---|---|"]
    for position, tier in enumerate(tiers):
        inner = [name for deeper in tiers[position + 1 :] for name in deeper]
        inward = ", ".join(f"`{name}`" for name in inner) or "nothing"
        for name in tier:
            modules = ", ".join(f"`{root}.{m}`" for m in layers[name])
            rows.append(f"| **{name}** | {purposes.get(name, NO_PURPOSE)} | {modules} | {inward} |")
    return "\n".join(rows)


def _breaches(imports: list[CrossImport], tiers: list[list[str]]) -> str:
    outward = [i for i in imports if _outward(i, tiers)]
    if not outward:
        return "None: every import between layers follows the rule."
    lines = [f"- `{i.module}` ({i.source}) imports `{i.imported}` ({i.target})" for i in outward]
    return "\n".join(lines)


def breach_lines(imports: list[CrossImport], tiers: list[list[str]]) -> list[str]:
    """Each module-to-module import that points outward, as ``importer -> imported`` (the form
    ``known_violations`` takes), once each."""
    return sorted({f"{i.module} -> {i.imported}" for i in imports if _outward(i, tiers)})


def _outward(found: CrossImport, tiers: list[list[str]]) -> bool:
    return points_outward(found.source, found.target, tiers)


def _shared_line(data: dict) -> str:
    shared = data.get("shared") or []
    if not shared:
        return ""
    modules = ", ".join(f"`{data[ROOT_KEY]}.{name}`" for name in shared)
    return f"Shared by every layer, outside the layering: {modules}.\n"


def render_overview(data: dict, imports: list[CrossImport]) -> str:
    tiers, layers = layer_tiers(data), layer_names(data)
    edges = {
        pair: count
        for pair, count in layer_edges(imports).items()
        if pair[0] in layers and pair[1] in layers
    }
    return "\n".join(
        [
            HEADER,
            "# Architecture",
            "",
            f"Root package `{data[ROOT_KEY]}`. Imports point inward: a layer may import only the "
            "layers in the tiers after its own, never a sibling in its tier. The table below "
            "says which.",
            "",
            "## Layers, as declared",
            "",
            _declared_diagram(tiers),
            "",
            _table(data),
            "",
            _shared_line(data),
            "## Imports between layers, as they are in the code",
            "",
            "A dashed arrow is an import that breaks the rule.",
            "",
            _actual_diagram(edges, tiers),
            "",
            "## Imports that break the rule",
            "",
            _breaches(imports, tiers),
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


def current_breaches(data: dict, project: Path) -> list[str]:
    """The outward imports the code has today, for seeding ``known_violations``."""
    imports = cross_layer_imports(build_graph(data, project), data)
    return breach_lines(imports, layer_tiers(data))


def render_docs(data: dict, project: Path) -> dict[str, str]:
    """Each generated document, keyed by its path relative to the repository root."""
    imports = cross_layer_imports(build_graph(data, project), data)
    return {f"{data['docs']}/{OVERVIEW}": render_overview(data, imports)}
