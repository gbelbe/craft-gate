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
   35 entries: 15 structural tidyings (Beck), 13 smell-and-fix pairs
   (Fowler, McCabe, SonarSource), 6 new-code design principles (Martin,
   Beck), and the legacy-code method (Feathers). Every entry cites its
   source — "Feature
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
6. **craftCov**, a coverage-report-style scan (`scripts/craftcov.py`,
   reusing ruff/pylint/vulture, plus a ported duplicate-code detector) for
   the subset of the catalog that has a real mechanical proxy — see
   **craftCov** below for exactly which 8 of 35 that is, and why the rest
   deliberately aren't automated.
7. **Refactor First**, the second default CI gate, built on craftCov
   (`scripts/check_refactor_first.py`) — for those 8 detectable heuristics,
   a touched file's total must go down from where the branch diverged (or
   stay at 0). Unlike the message-pattern ratchet, this checks the
   *outcome*, not just that a commit happened — see **craftCov** below and
   `CRAFTSMANSHIP.md`'s "Refactor First".
8. **The complexity ratchet**, a third default CI gate, independent of
   craftCov (`scripts/check_complexity_ratchet.py`) — cyclomatic/cognitive
   complexity, invariant return, and duplicated string literal (4 more
   catalog entries), diff-aware the same way Refactor First is: a touched
   function/literal must not get worse from where the branch diverged. See
   `CRAFTSMANSHIP.md`'s "The complexity ratchet".

## Requirements

**The message-pattern ratchet itself needs nothing beyond `bash`, `git`, and
standard POSIX text tools** (`grep`, `sed`, `sort`, `uniq`, `wc`) — every dev
machine and every GitHub Actions `ubuntu-latest` runner already has all of
this. Neither script parses `catalog.yaml` or `CRAFTSMANSHIP.md` at runtime,
so those stay plain files to read, not a load-bearing dependency.

**The full default install — both CI gates, message-pattern ratchet and
Refactor First — additionally needs craftCov's toolchain**, since Refactor
First is built on top of it:

- `scripts/craftcov.py` and `scripts/check_refactor_first.py` need PyYAML
  importable, plus whichever of `ruff` / `pylint` / `vulture` the catalog's
  `detectors` actually use — add a `craftcov` extra to your own dependency
  file; see **craftCov** below for the exact block to copy. `uv sync --extra
  craftcov` (this repo has a `pyproject.toml` for exactly this) installs all
  three; a repo that only wants a subset of the detectable heuristics can
  install fewer.

One thing stays genuinely optional, since it's a convenience, not a gate:

- The pre-push hook template needs [`prek`](https://prek.j178.dev) or
  [`pre-commit`](https://pre-commit.com) installed — craft-gate doesn't ship
  or install either. No pre-commit framework in your repo yet? Skip this and
  rely on the CI jobs alone; local and CI enforcement are independent.

Don't want Refactor First at all — the message-pattern ratchet alone is
enough for your repo? It stands on its own with zero dependencies; just
leave the `refactor-first` job and the `craftcov` extra out.

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
`scripts/report_tidy_history.sh`, `scripts/craftcov.py`,
`scripts/check_refactor_first.py`, `scripts/check_complexity_ratchet.py`,
`.claude/skills/tidy-first/SKILL.md`, and a `.craft-gate-version` marker —
into your repo. Nothing else is touched.

**2. Wire up the manual steps it prints** (each one is a template file
you merge or copy, not something bootstrap.sh guesses at, because these vary
too much per project to auto-merge safely):

| # | What | Template | Goes into |
|---|---|---|---|
| 1 | Pre-push hook | `templates/pre-commit-hook.yaml` | `.pre-commit-config.yaml` |
| 2 | CI gates — the ratchet, Refactor First, and the complexity ratchet (the latter two each need their own toolchain — see Requirements) | `templates/ci-job.yml` | `.github/workflows/ci.yml` |
| 3 | Agent guidance | `templates/CLAUDE.md.snippet.md` | `CLAUDE.md` |
| 4 | Weekly auto-update | `templates/update-check.yml` | `.github/workflows/craft-gate-update.yml` |

Step 4 is the one that matters most in practice — without it, staying
current requires remembering to re-run `bootstrap.sh` by hand. See **Staying
up to date** below for what it actually does.

**Optional, not printed by `bootstrap.sh`** (a methodology choice, not a
craftsmanship gate — most repos won't want every one of these defaults):
`templates/tdd-bdd-yagni.snippet.md`, appended to `CLAUDE.md` alongside
step 3, mandates writing a Gherkin `.feature` file and listing every test
case *before* any implementation, with an explicit YAGNI challenge to the
request first. Skip it if your project doesn't use BDD/Gherkin, or doesn't
want test-first mandated for every feature.

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
pyproject.toml            PyYAML (base) + ruff/pylint/vulture (the
                          `craftcov` extra) + radon/cognitive-complexity
                          (the `complexity` extra)
scripts/
  check_tidy_ratchet.sh    the CI/pre-push ratchet
  report_tidy_history.sh   the periodic exemption-ratio / sources report
  render_catalog.py        catalog.yaml -> CRAFTSMANSHIP.md's tables (--check in CI)
  craftcov.py              coverage-style scan for the detectable heuristics
  check_refactor_first.py  CI gate: a touched file's craftCov total must go
                          down (or stay 0) vs. where the branch diverged
  check_complexity_ratchet.py  CI gate: cyclomatic/cognitive complexity,
                          invariant return, duplicated literal (CG032-CG035)
  next_version.py          Conventional-Commits -> semver, used by release.yml
skills/tidy-first/
  SKILL.md                thin Claude Code wrapper around CRAFTSMANSHIP.md
templates/
  CLAUDE.md.snippet.md      section to paste into your CLAUDE.md
  tdd-bdd-yagni.snippet.md  optional companion section (see "How to install")
  pre-commit-hook.yaml      hook entry for .pre-commit-config.yaml
  ci-job.yml                job fragment for .github/workflows/ci.yml
  update-check.yml          weekly drift-check + auto-PR (see "Staying up to date")
bootstrap.sh              installer/updater
tests/
  fixtures/               one small file per detectable heuristic, ground
                          truth for craftCov's detectors (see craftCov below)
  test_fixtures.py         runs craftcov.py against fixtures/, checks each
                          detector fired where it should

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

**A `detectors` field means specifically "craftcov.py's own scan covers
this"** — only add one if you're wiring up ruff/pylint/vulture/dupes (see
**craftCov** below for the schema). A smell with a *different* mechanical
check — your own script, not craftcov.py's four engines — gets no
`detectors` field at all; document the check itself in its own
CRAFTSMANSHIP.md section instead, the way `check_complexity_ratchet.py`
has "The complexity ratchet." Leaving `detectors` off doesn't mean
"unchecked," just "not craftCov's job" — `--list-detectors` will call it
"needs judgment" regardless, since that's genuinely true from craftCov's
own point of view.

## craftCov

A coverage-report-style scan — like `coverage.py`'s report, but for the
catalog's mechanically-checkable heuristics instead of executed lines.

In your own repo's dependency file, this is the `craftcov` extra to add
(exact versions this release expects — see this repo's own `pyproject.toml`
for the copy-paste source of truth):

```toml
craftcov = [
    "pyyaml>=6.0",    # skip if already a dependency
    "ruff>=0.13",
    "pylint>=3.3",
    "vulture>=2.14",
]
```

```bash
uv sync --extra craftcov                      # installs ruff/pylint/vulture into .venv
uv run python3 scripts/craftcov.py                  # scan, text report
uv run python3 scripts/craftcov.py --format json     # machine-readable
uv run python3 scripts/craftcov.py --verbose         # + every finding, file:line
uv run python3 scripts/craftcov.py --list-detectors  # which heuristics are detectable, and how
uv run python3 scripts/craftcov.py --no-diff         # skip the "changes since last run" section
uv run python3 scripts/craftcov.py --file path/to/f.py --class SomeClass  # scope the report (Refactor First)
uv run python3 scripts/check_refactor_first.py --base origin/main         # CI's gate, runnable locally too
```

```
craftCov — craftsmanship heuristic scan
Scanned 669 files (0 changed, 669 from cache) in 1.45s
Duplicate-code pass: 1.10s (always full-corpus — see README)

Changes since last run (2026-09-21T09:03:11Z)
  CG002   dead-code                                1685 -> 1699  (+14)
  CG024   consolidate-duplicate-conditional          432 -> 428   (-4)
  CG012   extract-helper                                0 -> 1    (+1) (NEW)
          TOTAL                                     2563 -> 2579  (+16)

By heuristic
CODE    ID                                      COUNT  SOURCE
CG002   dead-code                                1685  Kent Beck, Tidy First? (2023)
CG024   consolidate-duplicate-conditional         432  Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
CG009   explaining-constant                       378  Kent Beck, Tidy First? (2023)
CG018   introduce-parameter-object                  65  Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
CG016   extract-class                              17  Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
CG001   guard-clauses                                1  Kent Beck, Tidy First? (2023)
CG012   extract-helper                               1  Kent Beck, Tidy First? (2023)
        TOTAL                                    2579

By file (top 15)
By class (top 15, module-level findings excluded)
By library (top-level directory)

8/35 heuristics have an automatic detector (22%) — the rest need the
procedure in CRAFTSMANSHIP.md (ask the developer), not a scan.
```

craftCov's own accounting stops there — it has no awareness of
`scripts/check_complexity_ratchet.py`, a fully separate script. Four more
catalog entries (CG032-CG035: cyclomatic/cognitive complexity, invariant
return, duplicated literal) are mechanically enforced by that ratchet
instead — see "The complexity ratchet" below, not craftCov's own report.

**Changes since last run.** Every run saves its by-heuristic totals to
`.craftcov_last_report.json` (gitignored — it's a local run-to-run diary, not
a checked-in artifact) and, unless `--no-diff` is passed, diffs the new
totals against that file before printing the rest of the report: a per-run
"did this get better or worse" view with no extra scan, no extra tool
invocation, just a comparison of two small JSON files. The first-ever run
says so explicitly rather than printing a misleading all-zero diff. A
heuristic whose old count was 0 is tagged `(NEW)`; one whose new count is 0
is tagged `(RESOLVED)`. `--no-diff` skips *printing* the section (the
snapshot file still gets updated, so a later diff-enabled run stays
accurate) — useful for scripted/cron invocations where you don't want the
extra lines but still want the history to keep advancing. `--format json`
carries the same information under a `"diff"` key (a list of
`{heuristic_id, old, new}`), present whenever `--no-diff` isn't. Point
`--snapshot-file` at a different path to keep separate histories (e.g. one
per branch, or one per CI job vs. local runs) instead of sharing the default.

Each duplicate is counted once *per copy*, not once per pair — a 2-copy
duplicate is 2 findings, one at each location, the same "each flagged line
counts" convention as every other detector here.

**Calibrated against the real PMD CPD, not guessed.** The first version of
this shipped with `min_lines=4` (pylint's own default) and reported 8778
`consolidate-duplicate-conditional` findings on kai-ster — 84% of them were
the minimum 4-5 line matches, and inspecting a sample turned up things like
a bare `subprocess.run(..., capture_output=True, text=True, check=False)`
call flagged as "duplicated" against three unrelated files: real, but not
useful signal. Rather than guess a better number, installed PMD 7.9.0
(needs a JVM — Java 17+; the project's own `min_lines` default doesn't, see
below) and ran its actual CPD against the identical file set (`git
ls-files`, same 669 files) at a few `--minimum-tokens` settings. Result:
both tools **agree on the real duplicates** — PMD independently found the
same 31-41-line duplicate in `ster/git/manager/_sync.py` this tool found —
and PMD's own `--minimum-tokens=50` (common in its own examples; PMD ships
no built-in default, unlike pylint) does *not* flag the bare
`subprocess.run(...)` snippet standalone, only as part of a larger, real
duplicate. Measuring tokens/line directly on this codebase (~5.2) and
testing several `min_lines` values against PMD's cluster counts at a few
`--minimum-tokens` settings, `min_lines=8` landed closest in the same order
of magnitude as PMD@50 — that's the new default (`catalog.yaml`'s comment
on this entry has the full numbers). 8778 → 432, a 20x drop, from fixing
the threshold alone — the algorithm itself needed no changes.

**Only code this repo wrote, not the libraries it imports.** `import`/`from
... import` lines (AST-located, so a multi-line parenthesized import has
every line excluded, not just the first) are stripped before the
duplicate-window scan even starts — two files that both do `import os`,
`import sys`, `from pathlib import Path` the same way share a dependency,
not duplicated logic, and shouldn't count as a `consolidate-duplicate-
conditional` finding. Measured on kai-ster's same 669-file set: 432 → 384,
48 of the post-PMD-calibration findings (~11%) were import-block matches,
not real duplication.

**Honest about its limits, on purpose.** Real semantic smell detection
(Feature Envy, Data Clumps *precisely* — not just "too many params," the
*same group* repeating — Message Chains, Primitive Obsession, Refused
Bequest) needs judgment a regex or AST check can't safely fake, or tooling
that doesn't exist for Python (checked against the academic
design-smell-detection literature, which is Java/C#/C++-tooling-only). So
craftCov doesn't try to fake any of them. It reuses three engines, and
ports one technique, for the entries where each is a decent proxy — 8 of
31:

- [`ruff`](https://astral.sh/ruff) (Rust, a dependency your project almost
  certainly already has, own fast internal cache) — `guard-clauses`,
  `dead-code`, `explaining-constant`, `extract-helper`,
  `introduce-parameter-object`, `replace-conditional-with-polymorphism`.
- `pylint`, scoped to exactly `R0902`/`R0904` (not a full pylint run) —
  `extract-class` / God Class. ruff hasn't ported these two yet (one's
  preview-only there, the other doesn't exist in ruff at all — checked
  against ruff 0.16.9); upstream pylint's originals are stable.
- `vulture` — a second, higher-recall pass for `dead-code` alongside ruff's
  F401/F811/F841, catching unused functions/classes ruff's own-file-scoped
  checks can't see. Verified on a real, framework-heavy codebase while
  building this (kai-ster: pytest-bdd + Textual): vulture's own confidence
  scores cluster hard into unused-*variables* at 100% (redundant with
  ruff's F841) and unused functions/classes/methods at 60% (vulture's own
  "fairly sure but could be wrong" floor — decorator-registered pytest-bdd
  steps and Textual's `on_*` handlers score exactly here without being
  genuinely dead). That 60% tier is also where all of vulture's unique
  value lives, so craftCov reports it unfiltered by default rather than
  quietly discarding it — tune with `--vulture-min-confidence N` once
  you've triaged a first pass and know your codebase's noise floor (its
  effect on the earlier example: `dead-code` 1685 → 36 at `N=80`).
- **`dupes`** — not a subprocess, `scripts/craftcov.py`'s own code:
  `consolidate-duplicate-conditional`, via a from-scratch port of the
  rolling-hash line-window matching technique both PMD CPD (Karp-Rabin
  string matching over a token stream — verified against PMD's own docs)
  and pylint's own `R0801` checker (the same technique, one level coarser —
  verified against pylint's actual source) use internally. Ported instead
  of subprocessing pylint's checker because pylint's own CLI JSON only
  gives ONE of a duplicate pair's two locations in structured form (the
  other is free text embedded in the message), and its internal API
  (`_compute_sims`) is private and churns across versions (this project's
  own `pylint` dependency moved 3.x → 4.x mid-session). Costs nothing new
  to install — stdlib only. Exact-match, like both reference tools'
  default mode (no identifier/literal normalization — PMD's fuzzy Type-2
  matching needs a real per-language tokenizer to do properly, out of
  scope here); doesn't special-case docstrings the way pylint's checker
  does either, so a duplicated docstring block is still reported.

Every other entry shows `0` findings not because your code is clean by that
measure, but because craftCov has nothing to say about it — see
`--list-detectors` for exactly which is which, and `catalog.yaml`'s
`detectors` field (a list — an entry can name more than one tool, as
`dead-code` does) to add more as a rule or tool that's a genuinely good
proxy shows up for something currently undetected.

**Findings, aggregated four ways**: by heuristic (code, count, source — so
you can see *which book* your codebase disagrees with most), by file, by
enclosing class (via a lightweight `ast` walk — module-level findings are
excluded from this view rather than miscounted against "no class"), and by
"library" (the top-level directory a file lives under — `ster`, `tests`,
`scripts`, whatever your repo's layout is).

**Caching, per-file tools only.** ruff's own `.ruff_cache/` already skips
re-linting unchanged files internally (pylint and vulture have no cache of
their own). On top of that, craftCov keeps `.craftcov_cache.json`, keyed by
each file's content hash (not mtime — a `touch` or a clean checkout with
different timestamps doesn't cause a rescan) and by a path *relative* to
the scan root (so the cache survives the repo moving to a different
absolute path, e.g. a fresh clone in CI). Its cache also stores the
class/function attribution none of the three subprocess tools track on
their own, so a warm re-run skips re-parsing ASTs for unchanged files too,
not just re-linting them. A cold run over kai-ster's ~670 files across
ruff/pylint/vulture took 9.1s; warm, 1.45s (mostly just re-hashing 669
files to confirm nothing changed). One caveat: the cache doesn't know
about scan *parameters* — changing `--vulture-min-confidence` between runs
needs `--no-cache` to actually take effect, since the file itself didn't
change.

**`dupes` doesn't participate in that cache, on purpose.** A duplicate only
means anything relative to its *other* copy — if file B changes, file A's
cached "duplicate of B" finding could go stale even though A itself didn't
change, and per-file caching has no way to know that. So the duplicate-code
pass always re-scans every file, every run, independent of the
ruff/pylint/vulture changed/cached split above. In practice this is cheap
enough not to matter: 1.40s over kai-ster's ~670 files / ~130k lines,
whether cold or warm.

**Not a hard whole-repo gate.** A full `craftcov.py` run doesn't fail CI —
it's a report, meant for a human to look at and decide what's worth a
`tidy(...)` commit, the same "ask the developer, don't decide silently"
principle as the rest of this catalog. Failing CI on some absolute total
(e.g. "fail if total > N") is a reasonable thing to add in a fork, but
deliberately not the default here — a repo's *existing* debt shouldn't block
an unrelated PR.

What **does** gate CI is **Refactor First** (see `CRAFTSMANSHIP.md`) — not
an absolute threshold, a relative one: a touched file's total must go down
from where the branch diverged (or, starting from 0, stay there).
`scripts/craftcov.py --file <path> [--class <name>]` scopes a report to one
file (still a full corpus scan underneath — `dupes` needs every file to find
a match's other half, so `--file` only filters what's *reported*, never what
gets scanned) for working through that file's present heuristics one at a
time; `scripts/check_refactor_first.py` is the CI-side enforcement, wired in
as the `refactor-first` job — the second default gate, alongside `tidy`.

**Testing the detectors: `tests/fixtures/`.** One small, hand-authored file
per detectable heuristic — each with a docstring naming exactly what it's
built to trigger and why — plus `clean.py`, a negative control genuinely
free of all eight (its functions are called from an `if __name__ ==
"__main__":` block so vulture doesn't flag them as unused, which would
defeat the point). `tests/test_fixtures.py` runs `craftcov.py` against that
directory and asserts each detector fired on its own fixture; CI runs it on
every push. Checks are presence-based, not exact-match — real code
routinely trips more than one heuristic at once (the
`replace-conditional-with-polymorphism` fixture also legitimately trips
`guard-clauses` and `explaining-constant`; that's the fixture being honest
about how code actually behaves, not test pollution to suppress). Added
after the `min_lines=4` miscalibration above was found and fixed by
comparing against real PMD CPD output — the two are complementary, not
redundant: this fixture corpus catches "did a detector regress or start
misfiring" on every push; the PMD-style comparison is what catches "is the
*threshold* reasonable" in the first place. Neither substitutes for the
other, which is why both exist now.

## The complexity ratchet

A second diff-aware gate, fully independent of craftCov (different script,
different catalog entries, its own dependency extra) — for the 4 catalog
entries it covers (CG032-CG035), a touched function/literal's metric must
not get worse from where the branch diverged, the same "grandfather what's
already there, block what gets worse" rule Refactor First uses:

```toml
complexity = [
    "radon>=6.0",
    "cognitive-complexity>=1.3",
]
```

```bash
uv sync --extra complexity
uv run python3 scripts/check_complexity_ratchet.py --base origin/main
```

```
Complexity ratchet: 2 violation(s):
  - ster/tui/query_screen.py::QueryScreen._render_results: cyclomatic complexity 12 -> 18 (> 15) — refactor to reduce cyclomatic complexity instead of adding to it
  - ster/tui/query_screen.py::QueryScreen._render_results: new function with cognitive complexity 16 (> 15) — keep new functions at or below 15
```

**Four checks, one mechanism:**

- **Cyclomatic complexity** (McCabe, 1976) and **cognitive complexity**
  (SonarQube S3776) — same threshold (15), reported separately because
  they measure different things: cyclomatic counts independent paths,
  cognitive charges for *nesting*, so a function radon calls simple can
  still fail cognitive.
- **Invariant return** (S3516) — every `return` in a function hands back
  the same never-rebound name; two returns of a mutated list read as two
  outcomes but are one.
- **Duplicated string literal** (S1192) — the same literal (5+ chars)
  repeated 3+ times in one file (not per-function — that's the rule's own
  granularity), excluding docstrings.

**Grandfathered, not retroactive.** A function already over threshold that
you don't touch isn't a violation; the same function made *more* complex
is. This is deliberate — the point is "don't make it worse," not "fix
everything that already exists" (that's a separate, much bigger
conversation the ratchet doesn't try to force).

**Diff-aware via a throwaway `git worktree`**, same technique as
`check_refactor_first.py`: one worktree checkout of the base ref computes
all four metrics at once (checking out the base is the slow part; doing it
once per metric would multiply that cost), compared against the current
tree. A file move counts as a change to everything it carries — there's no
rename-awareness, so a function that only moved to a new file is evaluated
like new code, not matched against its old location.

**Ported from a real, load-bearing script, not written from scratch for
this repo.** Originated in a project that hit SonarQube's cognitive-
complexity and duplicated-literal rules often enough to want them caught
locally, before a push, rather than after — the two smells beyond plain
cyclomatic complexity are checked against the *reference implementation*
(the `cognitive-complexity` package) rather than a re-derivation, because
the point is to agree with SonarQube's own server, not approximate it.

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
