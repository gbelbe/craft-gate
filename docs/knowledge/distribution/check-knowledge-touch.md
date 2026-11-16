---
type: Tool
title: Check Knowledge Touch
description: Fails (or warns) when a change modifies a file that a page in `docs/knowledge/` describes
  without touching that page; a `Docs-Exempt:` trailer waives it.
code:
- tools/check_knowledge_touch.py
relations:
  imports:
  - /distribution/check-knowledge.md
---
# Check Knowledge Touch

When a change modifies a file that a concept owns (its `code`), the concept's page must be in the same change, or the commit range carries a `Docs-Exempt:` trailer saying why nothing needs saying. It is a prompt to read the page against the diff, not proof that the text is true: the independent reviewer judges that. Files added or removed are already caught by the checker's coverage and anchor rules, so only modified files count. `--warn-only` reports without failing.

Imports: [Check Knowledge](check-knowledge.md).
