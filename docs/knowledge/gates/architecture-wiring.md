---
type: Tool
title: Architecture Wiring
description: Says whether any workflow or pre-commit hook of the repo runs the architecture ratchet, so
  `render_architecture.py --check` can fail until one does.
code:
- scripts/architecture_wiring.py
---
# Architecture Wiring

Says whether any workflow or pre-commit hook of the repo runs the architecture ratchet, so `render_architecture.py --check` can fail until one does.

craft-gate ships the ratchet script, but the job that calls it is pasted into the repo's own workflow by hand (`templates/architecture.yml`). A repo that took the script in an update and never pasted the job would hold a list of known violations that nothing makes shrink. The check reads `.github/workflows/*.yml`, `.github/workflows/*.yaml` and the pre-commit config for a line that names the script; a comment does not count.
