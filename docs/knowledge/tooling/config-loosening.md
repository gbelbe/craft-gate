---
type: Tool
title: Config Loosening
description: Finds the values in `craft-gate.toml` a change makes looser, so a person decides.
code:
- scripts/config_loosening.py
relations:
  imports:
  - /tooling/gate-config.md
  - /tooling/git-diff.md
---
# Config Loosening

Finds the values in `craft-gate.toml` a change makes looser, so a person decides.

Imports: [Gate Config](/tooling/gate-config.md), [Git Diff](/tooling/git-diff.md).
