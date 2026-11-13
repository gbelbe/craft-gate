---
type: Gate
title: Mutation Ratchet
description: 'Judges the mutants on changed lines: a touched function must reach the kill threshold (80%
  by default). No `Tidy-Exempt:` bypass.'
code:
- scripts/check_mutation_ratchet.py
relations:
  imports:
  - /tooling/ast-funcs.md
  - /tooling/git-diff.md
---
# Mutation Ratchet

Judges the mutants on changed lines: a touched function must reach the kill threshold (80% by default). No `Tidy-Exempt:` bypass.

Imports: [Ast Funcs](/tooling/ast-funcs.md), [Git Diff](/tooling/git-diff.md).
