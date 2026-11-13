---
type: Agent
title: Craft Review Skill
description: Hands the diff to the reviewer subagent and runs the design-review prompts.
code:
- skills/craft-review
relations:
  calls:
  - /distribution/craft-reviewer.md
  runs:
  - /tooling/design-review.md
---
# Craft Review Skill

Hands the diff to the reviewer subagent and runs the design-review prompts.

Calls: [Craft Reviewer](/distribution/craft-reviewer.md).

Runs: [Design Review](/tooling/design-review.md).
