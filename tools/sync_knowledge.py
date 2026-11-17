#!/usr/bin/env python3
"""Bring docs/knowledge/ up to date with what the code already says.

`check_knowledge.py` finds drift; this writes the part of the fix that needs no judgement:

  relations  `imports` (read from each Python file with `ast`) and `installs` (the files
             bootstrap.sh lists) are rewritten in the frontmatter and in the `Imports:` /
             `Installs:` line of the text. Any other relation, and all other prose, is left alone.
  stubs      a file under the covered roots that no concept owns gets a page in `unsorted/`
             with a placeholder description, which `check_knowledge.py` refuses until a person
             (or an agent) writes the sentence and moves the page where it belongs.

Usage:
    python3 tools/sync_knowledge.py [--path .] [--check]

`--check` writes nothing and exits 1 when a file would change.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path
from typing import NamedTuple

import check_knowledge as ck
import yaml

DERIVED = (ck.IMPORTS, ck.INSTALLS)
UNSORTED = "unsorted"
UNSORTED_INDEX = f"/{UNSORTED}/{ck.INDEX}"
UNSORTED_HEADER = "# Unsorted\n\nFiles waiting for a description and a home.\n"
SCRIPT_SUFFIXES = (".py", ".sh")
LIST_ITEM = "- ["
YAML_WIDTH = 100


def _frontmatter(meta: dict) -> str:
    return yaml.safe_dump(meta, sort_keys=False, width=YAML_WIDTH, allow_unicode=True)


def _listed(path: str, installer: str) -> bool:
    """True when *path* appears in the installer as a whole word, not inside a longer name."""
    return re.search(rf"(?<![\w./-]){re.escape(path)}(?![\w./-])", installer) is not None


def _imports_of(doc: ck.Doc, units: dict[str, ck.Unit]) -> list[str]:
    """The concepts whose Python modules this concept's Python files import."""
    mine = units[doc.path]
    return [path for path, unit in units.items() if path != doc.path and mine.imports_from(unit)]


class Context(NamedTuple):
    """What every page's derived relations are read against."""

    docs: list[ck.Doc]
    root: Path
    layout: ck.Layout
    units: dict[str, ck.Unit]


def _installs_of(doc: ck.Doc, context: Context) -> list[str]:
    layout, root = context.layout, context.root
    if layout.installer is None or layout.installer not in doc.code:
        return []
    installer = (root / layout.installer).read_text()
    files = {
        d.path: [p for p in d.code if (root / p).is_file()] for d in context.docs if d is not doc
    }
    return [path for path, owned in files.items() if any(_listed(p, installer) for p in owned)]


def derived(doc: ck.Doc, context: Context) -> dict[str, list[str]]:
    """What the code says about *doc*: relation -> sorted target pages, for each non-empty one."""
    found = {ck.IMPORTS: _imports_of(doc, context.units), ck.INSTALLS: _installs_of(doc, context)}
    return {kind: sorted(targets) for kind, targets in found.items() if targets}


def _text_line(kind: str, targets: list[str], page: str, titles: dict[str, str]) -> str:
    links = (f"[{titles[t]}]({posixpath.relpath(t, posixpath.dirname(page))})" for t in targets)
    return f"{kind.capitalize()}: {', '.join(links)}."


def _with_line(body: str, kind: str, line: str | None) -> str:
    """*body* with its `Kind:` line replaced by *line*, added at the end, or dropped if None."""
    existing = re.compile(rf"^{kind.capitalize()}: .*$", re.M)
    if existing.search(body):
        return (
            existing.sub(line, body, count=1) if line else existing.sub("", body).strip("\n") + "\n"
        )
    return f"{body.rstrip(chr(10))}\n\n{line}\n" if line else body


def rewritten(text: str, doc: ck.Doc, found: dict[str, list[str]], titles: dict[str, str]) -> str:
    """*text* with its derived relations, in the frontmatter and in the text, matching *found*."""
    parts = ck.FRONT.match(text)
    if not parts:
        return text
    meta, body = yaml.safe_load(parts.group(1)) or {}, parts.group(2)
    kept = {k: v for k, v in (meta.get(ck.RELATIONS_KEY) or {}).items() if k not in DERIVED}
    relations = dict(sorted({**kept, **found}.items()))
    meta = {k: v for k, v in meta.items() if k != ck.RELATIONS_KEY}
    meta.update({ck.RELATIONS_KEY: relations} if relations else {})
    for kind in DERIVED:
        line = _text_line(kind, found[kind], doc.path, titles) if kind in found else None
        body = _with_line(body, kind, line)
    return f"---\n{_frontmatter(meta)}---\n{body}"


def _stub(path: str) -> tuple[str, str]:
    """(page, text) of a placeholder concept for the unowned file *path*."""
    name = Path(path)
    slug = re.sub(r"[^a-z0-9]+", "-", name.name.lower()).strip("-")
    kind = "Tool" if path.endswith(SCRIPT_SUFFIXES) else "Asset"
    meta = {
        ck.TYPE_KEY: kind,
        "title": name.stem,
        ck.DESCRIPTION_KEY: ck.PLACEHOLDER,
        ck.CODE_KEY: [path],
    }
    return (
        f"/{UNSORTED}/{slug}.md",
        f"---\n{_frontmatter(meta)}---\n# {name.stem}\n\n{ck.PLACEHOLDER}\n",
    )


def _listed_in(index: str, pages: dict[str, str]) -> str:
    """*index* with a list item for each page of *pages* that it does not link yet."""
    added = [f"- [{Path(p).stem}]({posixpath.basename(p)})" for p in pages]
    new = [item for item in added if item not in index]
    gap = "\n" if LIST_ITEM in index else "\n\n"
    return index.rstrip("\n") + gap + "\n".join(new) + "\n" if new else index


def stubs(texts: dict[str, str], root: Path) -> dict[str, str]:
    """The pages to add so every unowned file has one, and the unsorted index that lists them."""
    docs = [ck.parse(text, path) for path, text in texts.items()]
    pages = dict(
        _stub(p) for p in ck.covered_files(root, ck.load_layout(root)) if not ck.owned(p, docs)
    )
    pages = {path: text for path, text in pages.items() if path not in texts}
    if not pages:
        return {}
    return {**pages, UNSORTED_INDEX: _listed_in(texts.get(UNSORTED_INDEX, UNSORTED_HEADER), pages)}


def sync(root: Path, write: bool = True) -> list[str]:
    """Bring the bundle up to date; the pages that changed, or would change when not writing."""
    before = ck.read_bundle(root)
    after = {**before, **stubs(before, root)}
    docs = [ck.parse(text, path) for path, text in after.items()]
    titles = {d.path: str(d.meta.get("title") or Path(d.path).stem) for d in docs}
    layout = ck.load_layout(root)
    context = Context(docs, root, layout, ck.units_of(docs, root, layout))
    for doc in (d for d in docs if d.is_concept):
        after[doc.path] = rewritten(after[doc.path], doc, derived(doc, context), titles)
    changed = {path: text for path, text in after.items() if text != before.get(path)}
    for path, text in changed.items() if write else ():
        page = root / ck.DOCS / path.lstrip("/")
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text)
    return sorted(changed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", default=".", help="repository root (default: .)")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 on a change")
    args = parser.parse_args(argv)
    changed = sync(Path(args.path), write=not args.check)
    verb = "would change" if args.check else "wrote"
    for path in changed:
        print(f"{verb} {ck.DOCS}{path}")
    if not changed:
        print("✓ knowledge bundle already in sync with the code")
    elif args.check:
        print("run: python3 tools/sync_knowledge.py", file=sys.stderr)
    return 1 if changed and args.check else 0


if __name__ == "__main__":
    sys.exit(main())
