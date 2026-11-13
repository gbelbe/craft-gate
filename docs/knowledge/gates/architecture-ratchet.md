---
type: Gate
title: Architecture Ratchet
description: 'Makes the list of known violations in `architecture.yaml` shrink: a touched module that
  is the importer of some must lose at least one.'
code:
- scripts/check_architecture_ratchet.py
relations:
  imports:
  - /tooling/gate-config.md
  - /tooling/git-diff.md
---
# Architecture Ratchet

Makes the list of known violations in `architecture.yaml` shrink: a touched module that is the importer of some must lose at least one.

Imports: [Gate Config](/tooling/gate-config.md), [Git Diff](/tooling/git-diff.md).
