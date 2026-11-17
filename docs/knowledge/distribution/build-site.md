---
type: Tool
title: Build Site
description: Writes the source of a browsable site from `docs/knowledge/`, with each page's relation tables,
  a diagram of its neighbours, its script's `--help` and the Gherkin scenarios that exercise it, all computed
  from the bundle and the code, plus a folder-level map of the system.
code:
- scripts/build_site.py
- mkdocs.yml
relations:
  imports:
  - /distribution/check-knowledge.md
---
# Build Site

Writes the source of a browsable site from `docs/knowledge/`, for MkDocs to build (`mkdocs.yml`, theme Material). The pages stay the one place a person edits; the tool writes an enriched copy to `build/knowledge/` (never committed) and everything it adds is computed, so nothing needs updating by hand:

- a "Depends on" and a "Used by" table, from the `relations` frontmatter;
- a diagram of the page and its neighbours; a page with more than six targets of one relation kind collapses them by folder;
- the `--help` of the page's Python script, when it has an argparse interface: the build runs `python3 <script> --help` in the repository, and when that fails or hangs it prints a warning and leaves the section out;
- the Gherkin scenarios of every feature whose step file imports a module the page's code defines (modules named by the layout in `bundle.yaml`, as the checkers do);
- `graph.md`, one box per folder with an arrow per relation kind and count.

It reads the bundle through [Check Knowledge](check-knowledge.md)'s parser, so both agree on what a page is. CI builds the site with `mkdocs build --strict` on every pull request, so a broken link or diagram fails there; it publishes nothing. To browse it: `python3 scripts/build_site.py && mkdocs serve`.

Imports: [Check Knowledge](check-knowledge.md).
