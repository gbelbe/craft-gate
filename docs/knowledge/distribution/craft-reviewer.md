---
type: Agent
title: Craft Reviewer
description: A subagent that reads the diff with no knowledge of how the code was written, and checks
  that the `docs/knowledge/` page of each modified file still tells the truth.
code:
- agents/craft-reviewer.md
---
# Craft Reviewer

A subagent that reads the diff with no knowledge of how the code was written. Besides design, it reads the `docs/knowledge/` page of every file the change modifies and reports a sentence the change made untrue (cited `DOC`). The mechanical gates only prove a page was touched and that its generated relations match the code; this is the one check that judges the prose.
