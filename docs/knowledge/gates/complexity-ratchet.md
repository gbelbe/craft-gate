---
type: Gate
title: Complexity Ratchet
description: Holds touched functions to the cyclomatic and cognitive limits. A function the diff reaches
  that is over the limit must come out lower; a new over-limit function, invariant return or repeated
  literal always fails.
code:
- scripts/check_complexity_ratchet.py
relations:
  imports:
  - /tooling/ast-funcs.md
  - /tooling/gate-config.md
  - /tooling/git-diff.md
---
# Complexity Ratchet

Holds touched functions to the cyclomatic and cognitive limits. A function the diff reaches that is over the limit must come out lower; a new over-limit function, invariant return or repeated literal always fails.

Imports: [Ast Funcs](/tooling/ast-funcs.md), [Gate Config](/tooling/gate-config.md), [Git Diff](/tooling/git-diff.md).
