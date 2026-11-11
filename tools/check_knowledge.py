#!/usr/bin/env python3
"""Keep the DOT-LD knowledge documents faithful to the repository (a spike).

`docs/knowledge/*.md` describe the project in DOT-LD, a markdown extension: `::config` blocks give
each entity a type and, here, the code it stands for (`path=a.py;dir`); `[[Name]]` mentions an
entity in prose; `::rel A -> B [label] ::` is an edge. Documents link by name, so a name must mean
one thing.

Rules, each a way for the documents to drift from the code:

  anchor    every `path=` exists
  coverage  every file under the covered roots belongs to some entity's path
  links     every `[[Name]]` and every edge end is defined, in exactly one document; every entity
            is mentioned somewhere (an orphan is documentation nobody reaches)
  imports   an edge labelled `imports` is a real `import` between the two entities' Python files
  installs  an edge labelled `installs` names something bootstrap.sh really lists

Usage:
    python3 tools/check_knowledge.py [--path .]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

DOCS = "docs/knowledge"
COVERED = ("scripts", "tools", "templates", "agents", "skills")
INSTALLER = "bootstrap.sh"
IMPORTS, INSTALLS = "imports", "installs"
NAME = r"[A-Za-z][\w-]*"
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
CONFIG = re.compile(r"^::config\s*\n(.*?)^::\s*$", re.S | re.M)
REL = re.compile(rf"^::rel\s+({NAME})\s+(->|<-|<->)\s+({NAME})\s+\[([^\]]*)\]\s*::\s*$", re.M)
REF = re.compile(rf"\[\[({NAME})\]\]")
ASSIGNMENT = re.compile(rf"^({NAME}):\s*(.+)$")
SEPARATOR = ";"


class Entity(NamedTuple):
    name: str
    document: str
    paths: tuple[str, ...]


class Edge(NamedTuple):
    source: str
    target: str
    label: str
    document: str


class Parsed(NamedTuple):
    entities: list[Entity]
    edges: list[Edge]
    mentions: set[str]


def _assignment(line: str, document: str) -> Entity | None:
    found = ASSIGNMENT.match(line.strip())
    if not found or "type=" not in found.group(2):
        return None  # a type definition, a comment or a blank line
    pairs = (part.split("=", 1) for part in found.group(2).split(",") if "=" in part)
    props = {key.strip(): value.strip() for key, value in pairs}
    paths = tuple(p for p in props.get("path", "").split(SEPARATOR) if p)
    return Entity(found.group(1), document, paths)


def _edge(match: re.Match[str], document: str) -> Edge:
    left, arrow, right, label = match.groups()
    source, target = (right, left) if arrow == "<-" else (left, right)
    return Edge(source, target, label.strip(), document)


def parse(text: str, document: str) -> Parsed:
    """Entities, edges and mentions of one document; fenced examples of the syntax are skipped."""
    body = FENCE.sub("", text)
    lines = (line for block in CONFIG.findall(body) for line in block.splitlines())
    entities = [e for e in (_assignment(line, document) for line in lines) if e]
    edges = [_edge(m, document) for m in REL.finditer(body)]
    prose = REL.sub("", CONFIG.sub("", body))
    return Parsed(entities, edges, set(REF.findall(prose)))


def load(root: Path) -> Parsed:
    parts = [parse(p.read_text(), p.name) for p in sorted((root / DOCS).glob("*.md"))]
    return Parsed(
        [e for part in parts for e in part.entities],
        [e for part in parts for e in part.edges],
        set().union(*(part.mentions for part in parts)),
    )


def anchor_problems(entities: list[Entity], root: Path) -> list[str]:
    return [
        f"anchor: {e.name} ({e.document}) points at {path}, which does not exist"
        for e in entities
        for path in e.paths
        if not (root / path).exists()
    ]


def _owned(path: str, entities: list[Entity]) -> bool:
    return any(path == p or path.startswith(p + "/") for e in entities for p in e.paths)


def covered_files(root: Path) -> list[str]:
    files = (p for top in COVERED for p in sorted((root / top).rglob("*")) if p.is_file())
    return [str(p.relative_to(root)) for p in files if "__pycache__" not in p.parts]


def coverage_problems(entities: list[Entity], root: Path) -> list[str]:
    return [
        f"coverage: {path} belongs to no entity"
        for path in covered_files(root)
        if not _owned(path, entities)
    ]


def _link(text: str) -> str:
    return f"links: {text}"


def link_problems(parsed: Parsed) -> list[str]:
    homes: dict[str, list[str]] = defaultdict(list)  # name -> the document of each definition
    for entity in parsed.entities:
        homes[entity.name].append(entity.document)
    ends = {end for edge in parsed.edges for end in (edge.source, edge.target)}
    used, defined = ends | parsed.mentions, set(homes)
    return [
        *(
            _link(f"{name} is defined {len(docs)} times ({', '.join(sorted(docs))})")
            for name, docs in homes.items()
            if len(docs) > 1
        ),
        *(_link(f"{name} is used but defined nowhere") for name in sorted(used - defined)),
        *(_link(f"{name} is defined but never mentioned") for name in sorted(defined - used)),
    ]


def _python_file(entity: Entity | None) -> str | None:
    only = [p for p in entity.paths if p.endswith(".py")] if entity else []
    return only[0] if only else None


def _imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
    return found


def imports_problems(parsed: Parsed, root: Path) -> list[str]:
    by_name = {e.name: e for e in parsed.entities}
    problems = []
    for edge in (e for e in parsed.edges if e.label == IMPORTS):
        source, target = (_python_file(by_name.get(n)) for n in (edge.source, edge.target))
        if source and target and Path(target).stem not in _imported_modules(root / source):
            problems.append(
                f"imports: {edge.source} does not import {edge.target} ({edge.document})"
            )
    return problems


def installs_problems(parsed: Parsed, root: Path) -> list[str]:
    installer = (root / INSTALLER).read_text()
    by_name = {e.name: e for e in parsed.entities}
    problems = []
    for edge in (e for e in parsed.edges if e.label == INSTALLS):
        target = by_name.get(edge.target)
        if target and target.paths and not any(p in installer for p in target.paths):
            problems.append(f"installs: {INSTALLER} does not list {edge.target} ({edge.document})")
    return problems


def problems_in(root: Path) -> list[str]:
    parsed = load(root)
    return [
        *anchor_problems(parsed.entities, root),
        *coverage_problems(parsed.entities, root),
        *link_problems(parsed),
        *imports_problems(parsed, root),
        *installs_problems(parsed, root),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    problems = problems_in(Path(parser.parse_args(argv).path))
    for problem in problems:
        print(f"✗ {problem}", file=sys.stderr)
    if not problems:
        print("✓ knowledge documents match the repository")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
