---
type: Gate
title: Refactor First
description: Requires every touched file's craftCov total to go down (or stay at 0), and that no finding
  sits on a line the diff added. `Tidy-Exempt:` waives the first, never the second.
code:
- scripts/check_refactor_first.py
relations:
  imports:
  - /tooling/craft-cov.md
  - /tooling/gate-config.md
  - /tooling/git-diff.md
---
# Refactor First

Requires every touched file's craftCov total to go down (or stay at 0), and that no finding sits on a line the diff added. `Tidy-Exempt:` waives the first, never the second.

Imports: [Craft Cov](/tooling/craft-cov.md), [Gate Config](/tooling/gate-config.md), [Git Diff](/tooling/git-diff.md).
