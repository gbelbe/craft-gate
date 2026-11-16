---
type: Tool
title: Sync Knowledge
description: Writes what the code already says into the bundle (imports and installs relations, and a
  placeholder page for every file no concept owns).
code:
- tools/sync_knowledge.py
relations:
  imports:
  - /distribution/check-knowledge.md
---
# Sync Knowledge

Writes what the code already says into the bundle: the `imports` and `installs` relations (in the frontmatter and in the text) and a placeholder page in `unsorted/` for every file no concept owns. It never touches prose or the hand-written relations, and `--check` writes nothing and fails when a page is out of step.

Imports: [Check Knowledge](check-knowledge.md).
