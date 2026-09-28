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
6. **craftCov**, a coverage-report-style scan (`scripts/craftcov.py`) for
   the subset of the catalog that has a real mechanical proxy — see
   **craftCov** below for exactly which 6 of 31 that is, and why the rest
   deliberately aren't automated.

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
- `scripts/craftcov.py` (see **craftCov** below) is the one script here that
  isn't plain bash: it needs `ruff` on PATH and PyYAML importable. Both are
  already present in a typical Python project; craftCov doesn't add them,
  it just isn't usable without them the way the ratchet is.

## How to install in an existing repo

**1. Run the installer**, from a checkout of a tagged release (not piped
over the network — you're about to run this against your own repo, read it
first):

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/gbelbe/craft-gate /tmp/craft-gate
bash /tmp/craft-gate/bootstrap.sh ~/code/my-project
```

This copies the files craft-gate fully owns — `CRAFTSMANSHIP.md`,
`catalog.yaml`, `scripts/check_tidy_ratchet.sh`,
`scripts/report_tidy_history.sh`, `.claude/skills/tidy-first/SKILL.md`, and
a `.craft-gate-version` marker — into your repo. Nothing else is touched.

**2. Wire up the four manual steps it prints** (each one is a template file
you merge or copy, not something bootstrap.sh guesses at, because these vary
too much per project to auto-merge safely):

| # | What | Template | Goes into |
|---|---|---|---|
| 1 | Pre-push hook | `templates/pre-commit-hook.yaml` | `.pre-commit-config.yaml` |
| 2 | CI gate | `templates/ci-job.yml` | `.github/workflows/ci.yml` |
| 3 | Agent guidance | `templates/CLAUDE.md.snippet.md` | `CLAUDE.md` |
| 4 | Weekly auto-update | `templates/update-check.yml` | `.github/workflows/craft-gate-update.yml` |

Step 4 is the one that matters most in practice — without it, staying
current requires remembering to re-run `bootstrap.sh` by hand. See **Staying
up to date** below for what it actually does.

**3. Confirm it works:**

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main   # your default branch
```

That's the whole install. No package manager, no lockfile entry — see
**Requirements** above for exactly what has to already be on the machine
(short version: `bash` and `git`, nothing else, unless you opt into the
pre-commit-hook step).

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
CRAFTSMANSHIP.md         procedure, commit convention, legacy-code method
                          (hand-written) + the two catalog tables
                          (generated — see catalog.yaml). Tool-agnostic.
catalog.yaml              the actual catalog data — edit this, not the
                          tables in CRAFTSMANSHIP.md directly
scripts/
  check_tidy_ratchet.sh   the CI/pre-push ratchet
  report_tidy_history.sh  the periodic exemption-ratio / sources report
  render_catalog.py       catalog.yaml -> CRAFTSMANSHIP.md's tables (--check in CI)
  craftcov.py             coverage-style scan for the detectable heuristics
  next_version.py         Conventional-Commits -> semver, used by release.yml
skills/tidy-first/
  SKILL.md                thin Claude Code wrapper around CRAFTSMANSHIP.md
templates/
  CLAUDE.md.snippet.md    section to paste into your CLAUDE.md
  pre-commit-hook.yaml    hook entry for .pre-commit-config.yaml
  ci-job.yml              job fragment for .github/workflows/ci.yml
  update-check.yml        weekly drift-check + auto-PR (see "Staying up to date")
bootstrap.sh              installer/updater

CLAUDE.md, .pre-commit-config.yaml, .claude/skills/tidy-first/SKILL.md
                          this repo applies its own tooling to itself —
                          produced by `bash bootstrap.sh .`, not hand-written
```

## Versioning

Every push to `main` runs `scripts/next_version.py` against the commits
since the last tag: a Conventional Commits `feat:` bumps minor, `fix:` /
`perf:` / `refactor:` / `build:` / `revert:` bump patch, a `!` or
`BREAKING CHANGE:` footer bumps major (while the major is still `0`, a
breaking change bumps minor instead — no accidental `1.0` from a stray
`feat!:`), and anything else (`docs:`, `chore:`, `test:`, `ci:`, `style:`)
releases nothing. If a release is due, `.github/workflows/release.yml` tags
it and creates a GitHub Release with auto-generated notes — no version
number to remember to bump by hand, no separate publish step to run.

Pin a specific version with `git clone --branch vX.Y.Z` (see Quickstart);
`main` always has the latest, possibly-unreleased state.

## Staying up to date

`bootstrap.sh` alone requires someone to remember to re-run it, which
defeats the point. Add `templates/update-check.yml` as
`.github/workflows/craft-gate-update.yml` in the consuming repo and it stops
being a thing to remember: a weekly job compares the repo's
`.craft-gate-version` against craft-gate's latest release, and if they
differ, runs `bootstrap.sh` and opens a PR with whatever changed. Re-running
it just force-pushes the same branch and updates the existing PR rather than
piling up duplicates. Nothing auto-merges — review it like any other
dependency bump. No new credentials: it uses the repo's own default
`GITHUB_TOKEN`, and craft-gate is only ever read from, never written to.

## How to add a new heuristic / rule

For the common case — a named smell with a fix (the `tidying` and
`smell-fix` tables), which is most of the catalog — this is a one-file edit:

**1. Add an entry to `catalog.yaml`:**

```yaml
- id: your-fix-name          # kebab-case, names the FIX, not the smell —
                              # this becomes the tidy(your-fix-name): commit type
  name: The Smell's Name     # what a reader recognizes ("Feature Envy")
  kind: smell-fix            # tidying | smell-fix | principle | workflow — see below
  source: "Author, Title (year)"   # exact citation — this is what makes a
                                    # tidy(...) commit a checkable claim later
  smell: What you'd notice that makes you reach for this
  action: What the fix actually does
```

**2. Regenerate `CRAFTSMANSHIP.md` from it:**

```bash
python3 scripts/render_catalog.py
```

This rewrites the two generated tables (between the `<!-- BEGIN GENERATED -->`
/ `<!-- END GENERATED -->` markers) to match `catalog.yaml`, and touches
nothing else in the file — the procedure, the principles, the legacy-code
workflow all stay hand-written. CI's `validate` job runs the same script
with `--check` and fails the PR if you edited `catalog.yaml` and forgot to
regenerate, so this can't silently drift.

**3. Open a PR.** That's it for the common case — two files change
(`catalog.yaml` and the regenerated `CRAFTSMANSHIP.md`), CI either passes or
tells you exactly what to run.

**The `kind` field** decides which section an entry lands in and whether
it's auto-generated:

| `kind` | What it means | Generated? |
|---|---|---|
| `tidying` | Structural-only move (Beck's *Tidy First?* sense) — a commit's tests must be identical before/after | Yes — table |
| `smell-fix` | A named design smell and its standard fix (Fowler's sense) — broader than structural-only | Yes — table |
| `principle` | A new-code design rule, not a retrospective commit type (Clean Code, XP's simple design, Metz) | No — prose |
| `workflow` | A named procedure, not a single fix (Feathers' characterization-test method) | No — prose |

`principle` and `workflow` entries don't reduce to one table row without
losing the nuance that makes them useful — adding one means writing a short
prose section in `CRAFTSMANSHIP.md` by hand (near the existing "New-code
principles" or "Working with legacy code" sections) *and* adding the
`catalog.yaml` entry, so the structured record still exists for tooling that
wants it. `render_catalog.py` won't touch or validate that prose — it only
owns the two tables.

**Naming the `id`:** name it after the *fix*, not the smell — `extract-class`
reads correctly in a commit (`tidy(extract-class): ...`) for "Large Class",
"God Class," and "Divergent Change" alike, since they share one fix. Check
whether an existing `id` already covers your fix before adding a new one; a
new smell that shares a known remedy is a one-line addition to an existing
row's `name` field, not a new entry.

## craftCov

A coverage-report-style scan — like `coverage.py`'s report, but for the
catalog's mechanically-checkable heuristics instead of executed lines.

```bash
python3 scripts/craftcov.py                  # scan, text report
python3 scripts/craftcov.py --format json     # machine-readable
python3 scripts/craftcov.py --verbose         # + every finding, file:line
python3 scripts/craftcov.py --list-detectors  # which heuristics are detectable, and how
```

```
craftCov — craftsmanship heuristic scan
Scanned 668 files (0 changed, 668 from cache) in 0.03s

By heuristic
CODE    ID                                      COUNT  SOURCE
CG009   explaining-constant                       382  Kent Beck, Tidy First? (2023)
CG018   introduce-parameter-object                  65  Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
CG001   guard-clauses                                1  Kent Beck, Tidy First? (2023)
CG012   extract-helper                               1  Kent Beck, Tidy First? (2023)
        TOTAL                                      449

By file (top 15)
By class (top 15, module-level findings excluded)
By library (top-level directory)

6/31 heuristics have an automatic detector (19%) — the rest need the
procedure in CRAFTSMANSHIP.md (ask the developer), not a scan.
```

**Honest about its limits, on purpose.** Real semantic smell detection
(Feature Envy, Data Clumps *precisely* — not just "too many params," the
*same group* repeating — Message Chains, Primitive Obsession, Refused
Bequest) needs judgment a regex or AST check can't safely fake; a detector
confident enough to report those would cry wolf more than it'd help. So
craftCov doesn't try. It reuses [`ruff`](https://astral.sh/ruff) (Rust, a
dependency your project almost certainly already has, with its own fast
internal cache) as the detection engine for the entries where a specific
lint rule is a decent proxy — currently 6 of 31: `guard-clauses`,
`dead-code`, `explaining-constant`, `extract-helper`,
`introduce-parameter-object`, `replace-conditional-with-polymorphism`. Every
other entry shows `0` findings not because your code is clean by that
measure, but because craftCov has nothing to say about it — see
`--list-detectors` for exactly which is which, and `catalog.yaml`'s
`detector` field to add more as ruff (or another tool) gains a rule that's
a genuinely good proxy for something currently undetected.

**Findings, aggregated four ways**: by heuristic (code, count, source — so
you can see *which book* your codebase disagrees with most), by file, by
enclosing class (via a lightweight `ast` walk — module-level findings are
excluded from this view rather than miscounted against "no class"), and by
"library" (the top-level directory a file lives under — `ster`, `tests`,
`scripts`, whatever your repo's layout is).

**Caching, two layers.** ruff's own `.ruff_cache/` already skips re-linting
unchanged files internally. On top of that, craftCov keeps
`.craftcov_cache.json`, keyed by each file's content hash (not mtime — a
`touch` or a clean checkout with different timestamps doesn't cause a
rescan) and by a path *relative* to the scan root (so the cache survives
the repo moving to a different absolute path, e.g. a fresh clone in CI). Its
cache also stores the class/function attribution ruff doesn't know about,
so a warm re-run skips re-parsing ASTs for unchanged files too, not just
skips re-linting them. A cold run over kai-ster's ~670 files took 0.52s; a
warm one with nothing changed took 0.03s.

**Not a gate.** Unlike `check_tidy_ratchet.sh`, craftCov doesn't fail CI —
it's a report, meant for a human to look at and decide what's worth a
`tidy(...)` commit, the same "ask the developer, don't decide silently"
principle as the rest of this catalog. Wiring it into CI as a hard gate
(e.g. "fail if total > N") is a reasonable thing to add in a fork or a
future version, deliberately not the default here.

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
