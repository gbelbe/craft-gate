---
type: Tool
title: Render Architecture
description: Turns `architecture.yaml` into import-linter contracts and, through Architecture Docs, into
  the generated overview. `--check` fails when either is stale, or when nothing runs the architecture
  ratchet.
code:
- scripts/render_architecture.py
relations:
  imports:
  - /gates/architecture-docs.md
  - /gates/architecture-wiring.md
---
# Render Architecture

Turns `architecture.yaml` into import-linter contracts and, through Architecture Docs, into the generated overview. `--check` fails when either is stale, or when nothing runs the architecture ratchet.

Imports: [Architecture Docs](architecture-docs.md), [Architecture Wiring](architecture-wiring.md).
