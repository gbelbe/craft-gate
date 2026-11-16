#!/usr/bin/env python3
"""Keep the OKF knowledge bundle faithful to the repository (a spike).

`docs/knowledge/` is an Open Knowledge Format bundle: one markdown file per concept, YAML
frontmatter for what a machine reads, prose and ordinary links for what a person reads. Beyond
OKF's own `type`, a concept here carries:

    code:       the files or folders it stands for
    relations:  typed edges to other concepts, a mapping of relation -> list of links

A link in the text is an ordinary relative one, `[Title](../folder/concept.md)` (OKF's
visualizer draws no edge for any other kind); `relations` name their targets rooted at the bundle,
`/folder/concept.md`.
`index.md` files are hubs: they link but are not concepts.

Rules, each a way for the documents to drift from the code:

  format     the frontmatter is valid YAML; a concept has a `type`; `relations` maps a known
             relation to a list
  todo       no concept still has the placeholder description `tools/sync_knowledge.py` writes
  anchor     every `code` path exists
  coverage   every file under the covered roots belongs to some concept's `code`
  links      every link and relation target exists; every concept is linked from somewhere
  prose      every relation target is also linked in the concept's text, so the two cannot diverge
  imports    an `imports` relation is a real `import` between the concepts' Python files
  installs   an `installs` relation names something bootstrap.sh really lists

Usage:
    python3 tools/check_knowledge.py [--path .]
"""

from __future__ import annotations

import argparse
import ast
import posixpath
import re
import sys
from pathlib import Path
from typing import NamedTuple

import yaml

DOCS = "docs/knowledge"
COVERED = ("scripts", "tools", "templates", "agents", "skills")
INSTALLER = "bootstrap.sh"
INDEX = "index.md"
IMPORTS, INSTALLS = "imports", "installs"
FORMAT, LINKS = "format", "links"
PLACEHOLDER = "TODO: say what this does."
DESCRIPTION_KEY = "description"
RELATIONS = (IMPORTS, INSTALLS, "writes", "calls", "runs")
TYPE_KEY, CODE_KEY, RELATIONS_KEY = "type", "code", "relations"
FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
LINK = re.compile(r"\]\(([^)\s#:]+\.md)\)")  # no scheme: not an external link


class Doc(NamedTuple):
    path: str  # rooted at the bundle: /gates/refactor-first.md
    meta: dict
    links: frozenset[str]  # what the text links to
    invalid: bool = False  # the frontmatter is not valid YAML

    @property
    def is_concept(self) -> bool:
        return not self.path.endswith("/" + INDEX)

    @property
    def code(self) -> tuple[str, ...]:
        return _strings(self.meta.get(CODE_KEY))

    @property
    def relations(self) -> dict[str, tuple[str, ...]]:
        raw = self.meta.get(RELATIONS_KEY)
        return (
            {str(kind): _strings(to) for kind, to in raw.items()} if isinstance(raw, dict) else {}
        )

    @property
    def targets(self) -> set[str]:
        return set(self.links).union(*self.relations.values())


def _strings(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def _rooted(target: str, path: str) -> str:
    """A link target as the bundle-rooted path it points at, from the file at *path*."""
    return posixpath.normpath(posixpath.join(posixpath.dirname(path), target))


def parse(text: str, path: str) -> Doc:
    """One file: its frontmatter, and the links in its text (fenced examples are skipped)."""
    found = FRONT.match(text)
    body = found.group(2) if found else text
    links = frozenset(_rooted(target, path) for target in LINK.findall(FENCE.sub("", body)))
    try:
        meta = yaml.safe_load(found.group(1)) if found else None
    except yaml.YAMLError:
        return Doc(path, {}, links, invalid=True)
    return Doc(path, meta if isinstance(meta, dict) else {}, links)


def read_bundle(root: Path) -> dict[str, str]:
    """Every markdown file of the bundle, by its bundle-rooted path."""
    base = root / DOCS
    return {"/" + p.relative_to(base).as_posix(): p.read_text() for p in sorted(base.rglob("*.md"))}


def load(root: Path) -> list[Doc]:
    return [parse(text, path) for path, text in read_bundle(root).items()]


def format_problems(docs: list[Doc]) -> list[str]:
    problems = []
    for doc in (d for d in docs if d.is_concept and d.invalid):
        problems.append(f"{FORMAT}: {doc.path} has frontmatter that is not valid YAML")
    for doc in (d for d in docs if d.is_concept and not d.invalid):
        if not doc.meta.get(TYPE_KEY):
            problems.append(f"{FORMAT}: {doc.path} has no {TYPE_KEY}")
        if doc.meta.get(RELATIONS_KEY) is not None and not isinstance(
            doc.meta[RELATIONS_KEY], dict
        ):
            problems.append(f"{FORMAT}: {doc.path} {RELATIONS_KEY} must map a relation to a list")
        problems += [
            f"{FORMAT}: {doc.path} uses the unknown relation '{kind}'"
            for kind in doc.relations
            if kind not in RELATIONS
        ]
    return problems


def todo_problems(docs: list[Doc]) -> list[str]:
    return [
        f"todo: {doc.path} still has the placeholder description"
        for doc in docs
        if doc.is_concept and doc.meta.get(DESCRIPTION_KEY) == PLACEHOLDER
    ]


def anchor_problems(docs: list[Doc], root: Path) -> list[str]:
    return [
        f"anchor: {doc.path} points at {path}, which does not exist"
        for doc in docs
        for path in doc.code
        if not (root / path).exists()
    ]


def owned(path: str, docs: list[Doc]) -> bool:
    return any(path == p or path.startswith(p + "/") for d in docs for p in d.code)


def covered_files(root: Path) -> list[str]:
    files = (p for top in COVERED for p in sorted((root / top).rglob("*")) if p.is_file())
    return [str(p.relative_to(root)) for p in files if "__pycache__" not in p.parts]


def coverage_problems(docs: list[Doc], root: Path) -> list[str]:
    return [
        f"coverage: {path} belongs to no concept"
        for path in covered_files(root)
        if not owned(path, docs)
    ]


def link_problems(docs: list[Doc]) -> list[str]:
    known = {d.path for d in docs}
    missing = [
        f"{LINKS}: {doc.path} links to {target}, which does not exist"
        for doc in docs
        for target in sorted(doc.targets - known)
    ]
    reached = {t for d in docs for t in d.targets if t != d.path}
    orphans = [
        f"{LINKS}: {d.path} is linked from nowhere"
        for d in docs
        if d.is_concept and d.path not in reached
    ]
    return missing + orphans


def prose_problems(docs: list[Doc]) -> list[str]:
    return [
        f"prose: {doc.path} declares {kind} {target} but its text never links to it"
        for doc in docs
        for kind, targets in doc.relations.items()
        for target in targets
        if target not in doc.links
    ]


def python_file(doc: Doc | None) -> str | None:
    only = [p for p in doc.code if p.endswith(".py")] if doc else []
    return only[0] if only else None


def imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
    return found


def _relations_of(docs: list[Doc], kind: str) -> list[tuple[Doc, Doc | None]]:
    by_path = {d.path: d for d in docs}
    return [(d, by_path.get(t)) for d in docs for t in d.relations.get(kind, ())]


def imports_problems(docs: list[Doc], root: Path) -> list[str]:
    problems = []
    for source, target in _relations_of(docs, IMPORTS):
        origin, wanted = python_file(source), python_file(target)
        if origin and wanted and Path(wanted).stem not in imported_modules(root / origin):
            problems.append(f"{IMPORTS}: {source.path} does not import {target.path}")
    return problems


def installs_problems(docs: list[Doc], root: Path) -> list[str]:
    installer = (root / INSTALLER).read_text()
    return [
        f"installs: {INSTALLER} does not list {target.path} (from {source.path})"
        for source, target in _relations_of(docs, INSTALLS)
        if target and target.code and not any(p in installer for p in target.code)
    ]


def problems_in(root: Path) -> list[str]:
    docs = load(root)
    return [
        *format_problems(docs),
        *todo_problems(docs),
        *anchor_problems(docs, root),
        *coverage_problems(docs, root),
        *link_problems(docs),
        *prose_problems(docs),
        *imports_problems(docs, root),
        *installs_problems(docs, root),
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
        print("✓ knowledge bundle matches the repository")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
