---
type: Gate
title: Tidy Ratchet
description: 'Reads only commit messages: a range needs a `tidy(...)` commit, a `test(characterize):`
  commit or a `Tidy-Exempt:` trailer. It cannot judge whether the right tidying was picked.'
code:
- scripts/check_tidy_ratchet.sh
---
# Tidy Ratchet

Reads only commit messages: a range needs a `tidy(...)` commit, a `test(characterize):` commit or a `Tidy-Exempt:` trailer. It cannot judge whether the right tidying was picked.
