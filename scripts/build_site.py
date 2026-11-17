#!/usr/bin/env python3
"""Turn the OKF knowledge bundle into the source of a browsable site (MkDocs).

`docs/knowledge/` stays the single place a person edits. This writes an enriched copy of it, to a
folder that is never committed, and everything it adds is computed from the bundle and the code, so
there is nothing to keep up to date by hand:

    relations   a "Depends on" / "Used by" table, from the `relations` frontmatter
    graph       the page and its neighbours as a Mermaid diagram; a page with many targets of one
                kind collapses them by folder
    usage       the `--help` of the page's Python script, when it has an argparse interface
    behaviour   the Gherkin scenarios of every feature whose steps import that script
    system      graph.md: one box per folder, one arrow per relation kind and count

Usage:
    python3 scripts/build_site.py [--path .] [--out build/knowledge]
    mkdocs build --strict        # or: mkdocs serve
"""

from __future__ import annotations

import argparse
import ast
import posixpath
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # siblings by bare name, also when imported as scripts.<name>
import check_knowledge as ck  # noqa: E402
from check_knowledge import DOCS, FRONT, INDEX, Doc, parse, read_bundle  # noqa: E402

FEATURE_SUFFIX = ".feature"
SCENARIOS = re.compile(r'scenarios\("([^"]+)"\)')
RELATION_LINE = re.compile(r"^(Imports|Installs|Writes|Calls|Runs): .*\n?", re.M)
TITLE = re.compile(r"# .*\n")
HEADING_MARK = re.compile(r"^#+\s*")
CAP = 6  # targets of one kind a page shows one by one before they collapse by folder
HELP_TIMEOUT = 30
FOCUS_STYLE = "fill:#c5cae9,stroke:#3f51b5,stroke-width:3px"
OVERVIEW = "/graph.md"


class Edge(NamedTuple):
    kind: str
    source: str
    target: str


class Page(NamedTuple):
    doc: Doc
    body: str


class Bundle(NamedTuple):
    pages: dict[str, Page]
    edges: list[Edge]

    def title(self, path: str) -> str:
        page = self.pages.get(path)
        return (page.doc.meta.get("title") if page else None) or Path(path).stem

    def link(self, source: str, target: str) -> str:
        return f"[{self.title(target)}]({posixpath.relpath(target, posixpath.dirname(source))})"

    def around(self, path: str) -> list[Edge]:
        return [e for e in self.edges if path in (e.source, e.target)]

    def users_of(self, path: str) -> dict[str, list[str]]:
        users: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.target == path:
                users[edge.kind].append(edge.source)
        return users


def load_bundle(root: Path) -> Bundle:
    pages = {}
    for path, text in read_bundle(root).items():
        found = FRONT.match(text)
        pages[path] = Page(parse(text, path), found.group(2) if found else text)
    edges = [
        Edge(kind, path, target)
        for path, page in pages.items()
        for kind, targets in page.doc.relations.items()
        for target in targets
    ]
    return Bundle(pages, edges)


def folder_of(path: str) -> str:
    return path.strip("/").split("/")[0]


def node_id(path: str) -> str:
    return re.sub(r"\W", "_", path.strip("/"))


class Arrow(NamedTuple):
    node: str
    label: str
    line: str


def group_node(source: str, kind: str, folder: str) -> str:
    return f"{node_id(source)}_{kind}_{folder}"


def arrows(bundle: Bundle, source: str, kind: str, targets: list[str]) -> list[Arrow]:
    """The arrows out of *source* for one relation kind; many targets collapse by folder."""
    origin = node_id(source)
    if len(targets) <= CAP:
        return [
            Arrow(node_id(t), bundle.title(t), edge_line(origin, kind, node_id(t))) for t in targets
        ]
    by_folder: dict[str, list[str]] = defaultdict(list)
    for target in targets:
        by_folder[folder_of(target)].append(target)
    collapsed = []
    for name, group in sorted(by_folder.items()):
        node = group_node(source, kind, name)
        collapsed.append(Arrow(node, f"{len(group)} {name} pages", edge_line(origin, kind, node)))
    return collapsed


def mermaid(bundle: Bundle, edges: list[Edge], focus: str | None = None) -> str:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for edge in edges:
        grouped[(edge.source, edge.kind)].append(edge.target)
    nodes = {}
    lines = []
    for (source, kind), targets in sorted(grouped.items()):
        nodes[node_id(source)] = bundle.title(source)
        for found in arrows(bundle, source, kind, targets):
            nodes[found.node] = found.label
            lines.append(found.line)
    declared = [f'  {ident}["{label}"]' for ident, label in nodes.items()]
    if focus:
        declared.append(f"  style {node_id(focus)} {FOCUS_STYLE}")
    return fenced("mermaid", "\n".join(["graph LR", *declared, *lines]))


def edge_line(source: str, label: str, target: str) -> str:
    return f"  {source} -->|{label}| {target}"


def fenced(language: str, text: str) -> str:
    return f"```{language}\n{text}\n```\n"


def relation_table(bundle: Bundle, heading: str, rows: dict, source: str) -> str:
    if not rows:
        return ""
    lines = (
        f"| {kind} | {', '.join(bundle.link(source, t) for t in sorted(targets))} |"
        for kind, targets in rows.items()
    )
    return f"\n## {heading}\n\n| Relation | Pages |\n|---|---|\n" + "\n".join(lines) + "\n"


def argparse_script(root: Path, code: tuple[str, ...]) -> str | None:
    """The page's first Python file that has an argparse interface."""
    return next((c for c in code if c.endswith(".py") and "argparse" in _text(root / c)), None)


def help_of(root: Path, script: str) -> str | None:
    """What `python3 <script> --help` prints, or None when it fails or hangs (and says so)."""
    try:
        run = subprocess.run(
            [sys.executable, str(root / script), "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=HELP_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        run = None
    if run is None or run.returncode:
        print(f"⚠ build_site: '{script} --help' failed; its usage is left out", file=sys.stderr)
        return None
    return run.stdout.rstrip()


def usage_of(root: Path, code: tuple[str, ...]) -> str:
    """The Usage section of a page, or nothing when its script has no `--help` to show."""
    script = argparse_script(root, code)
    shown = help_of(root, script) if script else None
    if shown is None:
        return ""
    return "\n## Usage\n\n" + fenced("text", f"$ python3 {script} --help\n{shown}")


def _text(path: Path) -> str:
    return path.read_text() if path.is_file() else ""


class Site(NamedTuple):
    """Everything a page is rendered against."""

    bundle: Bundle
    root: Path
    steps: dict[str, frozenset[str]]  # feature -> the names its step file imports
    units: dict[str, ck.Unit]
    features: str  # the folder of the features, from the layout


def steps_by_feature(root: Path, features: str) -> dict[str, frozenset[str]]:
    """Each feature -> the dotted names its step files import."""
    found: dict[str, set[str]] = defaultdict(set)
    for steps in sorted((root / features).glob("test_*.py")):
        text = steps.read_text()
        names = ck.imported_names(ast.parse(text), "")
        for feature in SCENARIOS.findall(text):
            found[feature.removesuffix(FEATURE_SUFFIX)] |= names
    return {feature: frozenset(names) for feature, names in found.items()}


def scenarios_of(site: Site, path: str) -> str:
    """The Gherkin of every feature whose step file imports a module the page's code defines."""
    defined = site.units[path].defines
    exercising = sorted(f for f, names in site.steps.items() if names & defined)
    existing = [
        f for f in exercising if (site.root / site.features / (f + FEATURE_SUFFIX)).is_file()
    ]
    if not existing:
        return ""
    blocks = [
        fenced("gherkin", (site.root / site.features / (f + FEATURE_SUFFIX)).read_text().rstrip())
        + f"\n*Source: `{site.features}/{f}{FEATURE_SUFFIX}`, run by the behaviour-coverage gate.*"
        for f in existing
    ]
    return "\n## How it behaves\n\n" + "\n\n".join(blocks) + "\n"


def with_header(page: Page) -> str:
    """The page's text without the relation lines the tables replace, plus its type and code."""
    body = RELATION_LINE.sub("", page.body)
    code = ", ".join(f"`{c}`" for c in page.doc.code)
    if not code:
        return body
    header = f"> **{page.doc.meta.get('type', '')}** · code: {code}\n\n"
    title = TITLE.match(body)
    return body[: title.end()] + "\n" + header + body[title.end() :] if title else header + body


def render_page(site: Site, path: str) -> str:
    bundle, root = site.bundle, site.root
    page = bundle.pages[path]
    if not page.doc.is_concept:
        return page.body
    near = bundle.around(path)
    around = "\n## Around this page\n\n" + mermaid(bundle, near, focus=path) if near else ""
    return (
        with_header(page).rstrip()
        + "\n"
        + scenarios_of(site, path)
        + usage_of(root, page.doc.code)
        + around
        + relation_table(bundle, "Depends on", page.doc.relations, path)
        + relation_table(bundle, "Used by", bundle.users_of(path), path)
    )


def folders(bundle: Bundle) -> dict[str, str]:
    """Each folder that holds pages -> the title of its hub."""
    names = {folder_of(p) for p in bundle.pages if p.count("/") > 1}
    return {f: hub_title(bundle, f) for f in names}


def hub_title(bundle: Bundle, folder: str) -> str:
    """The first line of the folder's index.md without its heading marker, else the folder name."""
    hub = bundle.pages.get(f"/{folder}/{INDEX}")
    lines = hub.body.splitlines() if hub else []
    return HEADING_MARK.sub("", lines[0]) if lines else folder


def folder_pages(bundle: Bundle, name: str) -> list[str]:
    return [
        p
        for p in sorted(bundle.pages)
        if folder_of(p) == name and bundle.pages[p].doc.is_concept and p.count("/") > 1
    ]


def folder_counts(bundle: Bundle) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for edge in bundle.edges:
        counts[(folder_of(edge.source), edge.kind, folder_of(edge.target))] += 1
    return counts


def folder_boxes(names: dict[str, str], pages: dict[str, list[str]], counts: dict) -> list[str]:
    inside = {f: sum(n for (a, _, b), n in counts.items() if a == b == f) for f in names}
    return [
        f'  {f}["{names[f]}<br/>{len(pages[f])} pages<br/>{inside[f]} inside"]'
        for f in sorted(names)
    ]


def folder_arrows(counts: dict) -> list[str]:
    return [edge_line(a, f"{kind} {n}", b) for (a, kind, b), n in sorted(counts.items()) if a != b]


def folder_table(bundle: Bundle, names: dict[str, str], pages: dict[str, list[str]]) -> str:
    rows = [
        f"| [{names[f]}]({f}/{INDEX}) | {len(pages[f])} | "
        + ", ".join(bundle.link(OVERVIEW, p) for p in pages[f])
        + " |"
        for f in sorted(names)
    ]
    return "| Folder | Pages | Which |\n|---|---|---|\n" + "\n".join(rows) + "\n"


def overview(bundle: Bundle) -> str:
    names = folders(bundle)
    pages = {f: folder_pages(bundle, f) for f in names}
    counts = folder_counts(bundle)
    diagram = ["graph LR", *folder_boxes(names, pages, counts), *folder_arrows(counts)]
    return (
        "# The system at folder level\n\n"
        "One box per folder; each arrow is a relation kind with the number of page-level "
        "relations behind it. Relations inside one folder are counted in its box.\n\n"
        + fenced("mermaid", "\n".join(diagram))
        + "\n"
        + folder_table(bundle, names, pages)
    )


def build(root: Path, out: Path) -> int:
    """Write the site source under *out*; the number of pages written."""
    bundle = load_bundle(root)
    docs = [page.doc for page in bundle.pages.values()]
    layout = ck.load_layout(root)
    units = ck.units_of(docs, root, layout)
    site = Site(bundle, root, steps_by_feature(root, layout.features), units, layout.features)
    shutil.rmtree(out, ignore_errors=True)
    for path in bundle.pages:
        target = out / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_page(site, path))
    (out / OVERVIEW.lstrip("/")).write_text(overview(bundle))
    return len(bundle.pages) + 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    parser.add_argument(
        "--out", default=f"build/{Path(DOCS).name}", help="where to write the site source"
    )
    args = parser.parse_args(argv)
    written = build(Path(args.path), Path(args.out))
    print(f"✓ wrote {written} pages to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
