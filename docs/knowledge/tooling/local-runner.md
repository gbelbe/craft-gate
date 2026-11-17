---
type: Tool
title: Local Runner
description: Runs the gates before a push; the architecture and knowledge checks only when the repo has
  them.
code:
- scripts/local-craft-gate.sh
---
# Local Runner

Runs the same gates before a push.

The architecture gate and the knowledge-bundle checks (`check_knowledge.py`, `sync_knowledge.py --check` and the warning-only `check_knowledge_touch.py`) are opt-in: they run only when the repo has an `architecture.yaml` or a `docs/knowledge/` folder. The runner does not build the documentation site; CI's `knowledge-site` job does.
