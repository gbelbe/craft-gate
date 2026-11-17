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
  todo       no concept still has the placeholder description `scripts/sync_knowledge.py` writes
  anchor     every `code` path exists
  coverage   every file under the covered roots belongs to some concept's `code`
  links      every link and relation target exists; every concept is linked from somewhere
  prose      every relation target is also linked in the concept's text, so the two cannot diverge
  imports    an `imports` relation is a real `import` between the concepts' Python modules
  installs   an `installs` relation names something the repo's installer really lists

The layout is the bundle's own: `docs/knowledge/bundle.yaml` (optional) says what the rules cover.

    covered:       roots whose every file must belong to a concept (default: none)
    installer:     a file that lists what is shipped, for `installs` (default: none)
    import-roots:  directories Python imports are rooted at, to name modules (default: ".")
    relations:     relation kinds allowed besides the built-in ones, described but not verified
    features:      where the Gherkin features and their step files live, for the site's scenarios
                   (default: tests/features)
    pages:         what `sync_knowledge.py` stubs a page for: each `file` (default), or each `child`
                   (a file or folder directly under a covered root)

Usage:
    python3 scripts/check_knowledge.py [--path .]
"""

from __future__ import annotations

import argparse
import ast
import posixpath
import re
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import yaml

DOCS = "docs/knowledge"
CONFIG = "bundle.yaml"
INDEX = "index.md"
IMPORTS, INSTALLS = "imports", "installs"
FORMAT, LINKS = "format", "links"
PLACEHOLDER = "TODO: say what this does."
DESCRIPTION_KEY = "description"
RELATIONS = (IMPORTS, INSTALLS, "writes", "calls", "runs")
COVERED_KEY, INSTALLER_KEY, ROOTS_KEY = "covered", "installer", "import-roots"
FEATURES_KEY, FEATURES_DIR = "features", "tests/features"
PAGES_KEY, PAGES_FILE, PAGES_CHILD = "pages", "file", "child"
CONFIG_KEYS = (COVERED_KEY, INSTALLER_KEY, ROOTS_KEY, "relations", FEATURES_KEY, PAGES_KEY)
ROOT_DIR = "."
TYPE_KEY, CODE_KEY, RELATIONS_KEY = "type", "code", "relations"
FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
LINK = re.compile(r"\]\(([^)\s#:]+\.md)\)")  # no scheme: not an external link


class Layout(NamedTuple):
    covered: tuple[str, ...] = ()
    installer: str | None = None
    import_roots: tuple[str, ...] = (ROOT_DIR,)
    relations: tuple[str, ...] = ()
    features: str = FEATURES_DIR
    pages: str = PAGES_FILE

    @property
    def known_relations(self) -> tuple[str, ...]:
        return RELATIONS + self.relations


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


def _directory(value: object) -> str:
    return value if isinstance(value, str) and value else FEATURES_DIR


def read_config(root: Path) -> tuple[dict, bool]:
    """(what `bundle.yaml` maps, whether it parsed); an absent file is ({}, True)."""
    path = root / DOCS / CONFIG
    if not path.is_file():
        return {}, True
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return {}, False
    return (raw if isinstance(raw, dict) else {}), True


def load_layout(root: Path) -> Layout:
    """The layout `bundle.yaml` declares; the defaults when the file is missing or unreadable."""
    given, _ = read_config(root)
    installer = given.get(INSTALLER_KEY)
    return Layout(
        covered=_strings(given.get(COVERED_KEY)),
        installer=installer if isinstance(installer, str) and installer else None,
        import_roots=_strings(given.get(ROOTS_KEY)) or (ROOT_DIR,),
        relations=_strings(given.get(RELATIONS_KEY)),
        features=_directory(given.get(FEATURES_KEY)),
        pages=PAGES_CHILD if given.get(PAGES_KEY) == PAGES_CHILD else PAGES_FILE,
    )


def config_problems(root: Path) -> list[str]:
    """What is wrong with `bundle.yaml` itself: invalid YAML, or a key no rule reads."""
    given, parsed = read_config(root)
    if not parsed:
        return [f"{FORMAT}: {CONFIG} is not valid YAML"]
    return [
        f"{FORMAT}: {CONFIG} has the unknown key '{key}'" for key in given if key not in CONFIG_KEYS
    ]


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


def format_problems(docs: list[Doc], layout: Layout) -> list[str]:
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
            if kind not in layout.known_relations
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


def covered_files(root: Path, layout: Layout) -> list[str]:
    files = (p for top in layout.covered for p in sorted((root / top).rglob("*")) if p.is_file())
    return [str(p.relative_to(root)) for p in files if "__pycache__" not in p.parts]


def coverage_problems(docs: list[Doc], root: Path, layout: Layout) -> list[str]:
    return [
        f"coverage: {path} belongs to no concept"
        for path in covered_files(root, layout)
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


def _relations_of(docs: list[Doc], kind: str) -> list[tuple[Doc, Doc | None]]:
    by_path = {d.path: d for d in docs}
    return [(d, by_path.get(t)) for d in docs for t in d.relations.get(kind, ())]


class Unit(NamedTuple):
    """What the Python files of one concept define (module names) and import (names)."""

    files: int
    defines: frozenset[str]
    imports: frozenset[str]

    def imports_from(self, other: Unit) -> bool:
        return bool(self.imports & other.defines)


def python_files(root: Path, doc: Doc) -> list[str]:
    """Repo-relative paths of the `.py` files a concept owns, directly or under a folder it owns."""
    found = []
    for anchor in doc.code:
        path = root / anchor
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        found += [f for f in files if f.suffix == ".py" and f.is_file()]
    return [f.relative_to(root).as_posix() for f in found if "__pycache__" not in f.parts]


def module_name(path: str, import_roots: tuple[str, ...]) -> str | None:
    """The dotted name code imports *path* by, under the first import root that holds it."""
    for base in import_roots:
        try:
            relative = (
                PurePosixPath(path) if base == ROOT_DIR else PurePosixPath(path).relative_to(base)
            )
        except ValueError:
            continue
        parts = list(relative.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts) or None
    return None


def _absolute(node: ast.ImportFrom, package: str) -> str | None:
    """The module a `from ... import` names, with its leading dots resolved against *package*."""
    if not node.level:
        return node.module or ""
    parts = package.split(".") if package else []
    keep = len(parts) - (node.level - 1)
    if keep < 0:
        return None
    return ".".join(filter(None, [".".join(parts[:keep]), node.module]))


def _join(base: str, name: str) -> str:
    return f"{base}.{name}" if base else name


def _from_names(node: ast.ImportFrom, package: str) -> set[str]:
    base = _absolute(node, package)
    if base is None:
        return set()
    members = {_join(base, alias.name) for alias in node.names}
    return members | {base} if base else members


def imported_names(tree: ast.AST, package: str) -> set[str]:
    """Every dotted name an `import` in *tree* may be reaching.

    `from a import b` names both `a` and `a.b`, though `b` may be a member and not a module. The
    over-match is deliberate: a name only counts when some concept defines a module of that name.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found |= _from_names(node, package)
    return found


def package_of(path: str, module: str | None) -> str:
    """The package relative imports in the file at *path* are resolved against."""
    name = module or ""
    return name if path.endswith("__init__.py") else name.rpartition(".")[0]


def unit_of(root: Path, doc: Doc, layout: Layout) -> Unit:
    files = python_files(root, doc)
    defines, imports = set(), set()
    for path in files:
        module = module_name(path, layout.import_roots)
        imports |= imported_names(ast.parse((root / path).read_text()), package_of(path, module))
        defines.update([module] if module else [])
    return Unit(len(files), frozenset(defines), frozenset(imports))


def units_of(docs: list[Doc], root: Path, layout: Layout) -> dict[str, Unit]:
    """The Python unit of every concept, read once."""
    return {d.path: unit_of(root, d, layout) for d in docs if d.is_concept}


def imports_problems(docs: list[Doc], units: dict[str, Unit]) -> list[str]:
    problems = []
    for source, target in _relations_of(docs, IMPORTS):
        origin, wanted = units[source.path], units.get(target.path) if target else None
        if wanted and origin.files and wanted.files and not origin.imports_from(wanted):
            problems.append(f"{IMPORTS}: {source.path} does not import {target.path}")
    return problems


def installs_problems(docs: list[Doc], root: Path, layout: Layout) -> list[str]:
    if layout.installer is None:
        return []
    installer = (root / layout.installer).read_text()
    return [
        f"installs: {layout.installer} does not list {target.path} (from {source.path})"
        for source, target in _relations_of(docs, INSTALLS)
        if target and target.code and not any(p in installer for p in target.code)
    ]


def problems_in(root: Path) -> list[str]:
    docs, layout = load(root), load_layout(root)
    return [
        *config_problems(root),
        *format_problems(docs, layout),
        *todo_problems(docs),
        *anchor_problems(docs, root),
        *coverage_problems(docs, root, layout),
        *link_problems(docs),
        *prose_problems(docs),
        *imports_problems(docs, units_of(docs, root, layout)),
        *installs_problems(docs, root, layout),
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
