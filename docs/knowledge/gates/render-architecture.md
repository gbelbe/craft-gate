---
type: Tool
title: Render Architecture
description: Turns `architecture.yaml` into import-linter contracts and, through Architecture Docs, into
  the generated overview. `--check` fails when either is stale.
code:
- scripts/render_architecture.py
relations:
  imports:
  - /gates/architecture-docs.md
---
# Render Architecture

Turns `architecture.yaml` into import-linter contracts and, through Architecture Docs, into the generated overview. `--check` fails when either is stale.

Imports: [Architecture Docs](architecture-docs.md).
