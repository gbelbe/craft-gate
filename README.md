# craft-gate

[![CI](https://github.com/gbelbe/craft-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/gbelbe/craft-gate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Catalog entries](https://img.shields.io/badge/catalog-31_entries-blue)](CRAFTSMANSHIP.md)
[![Sources](https://img.shields.io/badge/sources-Beck·Fowler·Martin·Feathers·Metz-lightgrey)](CRAFTSMANSHIP.md)

A small, dependency-light toolkit that turns software-craftsmanship
literature — Kent Beck's *Tidy First?*, Fowler's *Refactoring*, Martin's
*Clean Code*, Feathers' *Working Effectively with Legacy Code* — into
something a team (human or AI-assisted) actually follows: a named catalog,
a lightweight CI gate, and a step-by-step method for the code that has no
tests yet.

It answers two separate questions, on purpose:

- **Writing new code today** — what's the bar, and where does it come from?
- **Changing code that's already there** — how do you improve it without a
  behavior-change diff hiding inside a refactor, or vice versa?

## What it actually does

1. **A named, attributed catalog** (`CRAFTSMANSHIP.md` / `catalog.yaml`) —
   31 entries: 15 structural tidyings (Beck), 9 smell-and-fix pairs
   (Fowler), 6 new-code design principles (Martin, Beck), and the
   legacy-code method (Feathers). Every entry cites its source — "Feature
   Envy (Fowler, *Refactoring*)" is a specific, checkable claim; "this could
   be cleaner" is not.
2. **A commit convention** that keeps structural and behavioral changes in
   separate, labeled commits — `tidy(<type>): ...` with a `Tidy-Source:`
   trailer naming the book, `test(characterize): ...` for the legacy-code
   prerequisite, `Tidy-Exempt: <reason>` when nothing applied.
3. **A ratchet, not a gate** — `scripts/check_tidy_ratchet.sh` is a
   commit-message check (no test run, no build) that fails a push/PR with
   none of the above in range. Costs milliseconds. It cannot judge whether
   the *right* tidying was picked — that's a judgment call for the author
   and reviewer, which is exactly why the convention requires citing a
   source rather than just a commit type.
4. **A Claude Code skill** that's a thin wrapper — the catalog and procedure
   are plain markdown any tool or human can read; the skill only adds "how
   to run this procedure's confirmation step in Claude Code specifically."
5. **A bootstrap script**, not a package dependency — `bootstrap.sh` copies
   the files this tool owns into your repo and tells you exactly what to
   wire up by hand (a pre-commit hook, a CI job, a CLAUDE.md section). It
   never silently merges into files that vary per project.

## Requirements

**The ratchet itself needs nothing beyond `bash`, `git`, and standard POSIX
text tools** (`grep`, `sed`, `sort`, `uniq`, `wc`) — every dev machine and
every GitHub Actions `ubuntu-latest` runner already has all of this. Neither
script parses `catalog.yaml` or `CRAFTSMANSHIP.md` at runtime, so those stay
plain files to read, not a load-bearing dependency. Nothing to `pip install`
or `npm install`, and the CI job template needs no setup step.

Two things are **optional**, only if you use that specific piece:

- The pre-push hook template needs [`prek`](https://prek.j178.dev) or
  [`pre-commit`](https://pre-commit.com) installed — craft-gate doesn't ship
  or install either. No pre-commit framework in your repo yet? Skip this and
  rely on the CI job alone; the two enforcement points are independent.
- Consuming `catalog.yaml` programmatically (building your own tooling on
  top, not just running the ratchet) needs a YAML parser, e.g. `PyYAML`.

## Quickstart

```bash
# clone a tagged release rather than piping this over the network
git clone --branch v0.1.0 --depth 1 https://github.com/gbelbe/craft-gate /tmp/craft-gate
bash /tmp/craft-gate/bootstrap.sh ~/code/my-project
```

This copies `CRAFTSMANSHIP.md`, `catalog.yaml`, the two scripts, and the
Claude Code skill into your repo, then prints the three manual steps (all
templates provided) to wire the ratchet into your pre-commit hooks, your CI,
and your `CLAUDE.md`. Re-run it any time to pull an update — it only touches
the files it owns.

## Example

```
tidy(extract-class): split OrderValidator's audit-log concern into its own class

Tidy-Type: extract-class
Tidy-Source: Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
Tidy-Scope: OrderValidator
```

```bash
scripts/report_tidy_history.sh
# ── Tidy First discipline ──────────────────────────────
# tidy(...) commits:           14
# test(characterize) commits:  3
# Tidy-Exempt: commits:        2
# exemption rate:              11%
#
# ── Tidyings by type ────────────────────────────────────
#    5 extract-helper
#    3 guard-clauses
#    ...
#
# ── Cited sources (Tidy-Source: trailer) ────────────────
#    9 Kent Beck, Tidy First? (2023)
#    5 Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
```

## Repo layout

```
CRAFTSMANSHIP.md         the actual content — catalog, procedure, commit
                          convention, legacy-code method. Tool-agnostic.
catalog.yaml              machine-readable mirror of the catalog table
scripts/
  check_tidy_ratchet.sh   the CI/pre-push ratchet
  report_tidy_history.sh  the periodic exemption-ratio / sources report
skills/tidy-first/
  SKILL.md                thin Claude Code wrapper around CRAFTSMANSHIP.md
templates/
  CLAUDE.md.snippet.md    section to paste into your CLAUDE.md
  pre-commit-hook.yaml    hook entry for .pre-commit-config.yaml
  ci-job.yml              job fragment for .github/workflows/ci.yml
bootstrap.sh              installer/updater
```

## Design choices worth knowing about

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
- **Any diff-aware skip heuristic you build on top of this (e.g. a CI job
  that skips a slow test tier for unrelated changes) should follow the same
  rule as everything else here: widen what it trusts from evidence, never a
  hunch, and keep an unconditional full run on a schedule as backstop.** A
  heuristic that quietly gets more permissive over time is the same failure
  mode as a rubber-stamped exemption — just automated.

## Further reading (the actual sources)

- Kent Beck, *Tidy First?* (2023)
- Martin Fowler (with Kent Beck), *Refactoring*, 2nd ed. (2018)
- Robert C. Martin, *Clean Code* (2008) and *Agile Software Development,
  Principles, Patterns, and Practices* (2002)
- Kent Beck, *Extreme Programming Explained* (1999/2004)
- Michael Feathers, *Working Effectively with Legacy Code* (2004)
- Sandi Metz's rules (widely cited, originally a conference-talk heuristic)

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, strip out what your team
doesn't want.
