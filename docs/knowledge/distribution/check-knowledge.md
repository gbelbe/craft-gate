---
type: Tool
title: Check Knowledge
description: 'Keeps the documents in `docs/knowledge/` faithful to the repository: the frontmatter is
  valid, every code anchor exists, every file has an owner, every link resolves, every typed relation
  is true, and no page still carries the stub''s placeholder description.'
code:
- tools/check_knowledge.py
---
# Check Knowledge

Keeps the documents in `docs/knowledge/` faithful to the repository: the frontmatter is valid YAML, every code anchor exists, every file has an owner, every link resolves, every typed relation is true (an `imports` relation is a real `import`, an `installs` relation is listed in `bootstrap.sh`), and no page still carries the placeholder description that `sync_knowledge.py` writes into a stub. It reads and reports; it never writes.
