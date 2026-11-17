---
type: Tool
title: Check Knowledge
description: 'Keeps the documents in `docs/knowledge/` faithful to the repository: the frontmatter is
  valid, every code anchor exists, every file has an owner, every link resolves, every typed relation
  is true, and no page still carries the stub''s placeholder description.'
code:
- scripts/check_knowledge.py
---
# Check Knowledge

Keeps the documents in `docs/knowledge/` faithful to the repository: the frontmatter is valid YAML, every code anchor exists, every file has an owner, every link resolves, every typed relation is true (an `imports` relation is a real `import`, an `installs` relation is listed in `bootstrap.sh`), and no page still carries the placeholder description that `sync_knowledge.py` writes into a stub. It reads and reports; it never writes.

What it covers is the bundle's own business: `docs/knowledge/bundle.yaml` (optional) names the roots whose every file needs a page (`covered`), the file that lists what is shipped (`installer`, for `installs`), the directories Python imports are rooted at (`import-roots`), any further relation kinds a repo wants to write down (`relations`, described but not verified), the folder of its Gherkin features (`features`), and whether a new file gets a page of its own or shares one with its siblings (`pages`: `file`, or `child` for one page per file or folder directly under a covered root). Without it a repo has no coverage rule and no `installs` check, so the tool applies to any repository. An `imports` relation is checked on dotted module names, not file names: a concept that owns a folder imports another when any module below it imports a module below the other, with relative imports resolved against their package.

It ships with `sync_knowledge.py`, `check_knowledge_touch.py` and `build_site.py` (all installed by `bootstrap.sh`), and `templates/knowledge.yml` is the CI job that runs them in a consuming repo.
