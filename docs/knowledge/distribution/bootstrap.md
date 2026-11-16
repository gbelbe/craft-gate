---
type: Tool
title: Bootstrap
description: Copies the scripts a repo needs and leaves per-project files to the adopter, who pastes the
  templates into their own CI and `AGENTS.md`.
code:
- bootstrap.sh
relations:
  installs:
  - /gates/architecture-ratchet.md
  - /distribution/catalog.md
  - /gates/complexity-ratchet.md
  - /tooling/craft-cov.md
  - /tooling/gate-config.md
  - /tooling/git-diff.md
  - /gates/mutation-ratchet.md
  - /gates/refactor-first.md
  - /gates/render-architecture.md
---
# Bootstrap

Copies the scripts a repo needs and leaves per-project files to the adopter, who pastes the templates into their own CI and `AGENTS.md`.

Installs: [Architecture Ratchet](../gates/architecture-ratchet.md), [Catalog](catalog.md), [Complexity Ratchet](../gates/complexity-ratchet.md), [Craft Cov](../tooling/craft-cov.md), [Gate Config](../tooling/gate-config.md), [Git Diff](../tooling/git-diff.md), [Mutation Ratchet](../gates/mutation-ratchet.md), [Refactor First](../gates/refactor-first.md), [Render Architecture](../gates/render-architecture.md).
