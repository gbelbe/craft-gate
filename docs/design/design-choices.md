# Design choices worth knowing about

- **The ratchet checks discipline, not correctness.** It can tell you a
  `tidy(...)` commit exists; it cannot tell you the tidying was the right
  one, or that it actually preserved behavior. That's still a human (or
  agent-plus-human) judgment call — the tool's job is only to make sure the
  judgment call was *recorded*, not skipped under pressure.
- **`Tidy-Exempt:` is load-bearing, not a loophole to remove.** Without an
  honest way to say "nothing applied here," the ratchet would pressure
  people into manufacturing fake tidyings just to pass a gate — a textbook
  Goodhart's Law failure. The trade-off is that the exemption rate needs
  periodic review (`report_tidy_history.sh`) rather than blind trust.
- **Legacy code gets a named first step, not an exception.** Feathers'
  definition — *legacy code is code without tests* — means "tidy first"
  doesn't work on it as-is; there's nothing to confirm unchanged. A
  `test(characterize):` commit is the prerequisite move, and it satisfies
  the ratchet exactly like a tidying does, because it *is* the tidying-first
  move for untested code.
- **Any diff-aware skip heuristic you build on top of this should follow
  the same rule as everything else here: widen what it trusts from
  evidence, never a hunch, and keep an unconditional full run on a
  schedule as backstop.** A heuristic that quietly gets more permissive
  over time is the same failure mode as a rubber-stamped exemption — just
  automated.
- **The three gates skip bot-authored PRs** (`if: ... &&
  !endsWith(github.actor, '[bot]')` — see `templates/ci-job.yml`). This is
  a narrower exemption than it looks: it only fires for an *automated PR
  author* like dependabot or renovate, which can't write a `tidy(<type>)`
  commit or a `Tidy-Exempt:` trailer and whose diffs (dependency-file
  bumps) rarely have a craftsmanship heuristic to apply anyway. It does
  not exempt a human pushing to their own branch, and a skipped job still
  reports a passing check, so it doesn't create a required-check gap for
  anyone else's PR.

## Further reading (the actual sources)

- Kent Beck, *Tidy First?* (2023)
- Martin Fowler (with Kent Beck), *Refactoring*, 2nd ed. (2018)
- Robert C. Martin, *Clean Code* (2008) and *Agile Software Development,
  Principles, Patterns, and Practices* (2002)
- Kent Beck, *Extreme Programming Explained* (1999/2004)
- Michael Feathers, *Working Effectively with Legacy Code* (2004)
- Sandi Metz's rules (widely cited, originally a conference-talk heuristic)
- Thomas J. McCabe, "A Complexity Measure", IEEE TSE (1976)
- G. Ann Campbell, "Cognitive Complexity", SonarSource whitepaper (2018)
