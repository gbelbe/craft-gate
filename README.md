# craft-gate

[![CI](https://github.com/gbelbe/craft-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/gbelbe/craft-gate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Catalog entries](https://img.shields.io/badge/catalog-35_entries-blue)](CRAFTSMANSHIP.md)
[![Sources](https://img.shields.io/badge/sources-Beck·Fowler·Martin·Feathers·Metz·McCabe·SonarSource-lightgrey)](CRAFTSMANSHIP.md)

A small, dependency-light toolkit that turns software-craftsmanship
literature — Kent Beck's *Tidy First?*, Fowler's *Refactoring*, Martin's
*Clean Code*, Feathers' *Working Effectively with Legacy Code* — into
something a team (human or AI-assisted) actually follows: a named catalog,
a handful of CI gates, and a method for code that has no tests yet.

It answers two separate questions, on purpose:

- **Writing new code today** — what's the bar, and where does it come from?
- **Changing code that's already there** — how do you improve it without a
  behavior-change diff hiding inside a refactor, or vice versa?

## What it does

- **A named, attributed catalog** (`CRAFTSMANSHIP.md` / `catalog.yaml`) — 35
  entries, every one citing its source. "Feature Envy (Fowler,
  *Refactoring*)" is a checkable claim; "this could be cleaner" is not.
- **A commit convention** — `tidy(<type>): ...` with a `Tidy-Source:`
  trailer naming the book, `test(characterize): ...` for legacy code,
  `Tidy-Exempt: <reason>` when nothing applies.
- **Four CI gates**, cheapest first:
  - **`tidy`** — a commit-message check, zero dependencies: did a tidying
    (or a recorded exemption) happen at all?
  - **`refactor-first`** — built on **craftCov**, a coverage-style scan for
    8 mechanically-detectable heuristics: a touched file's total across
    them must go down (or stay at 0).
  - **`complexity`** — cyclomatic/cognitive complexity, invariant return,
    duplicated string literal: a function/literal the diff actually
    touches, already over threshold, must come out *lower* than it went
    in — unchanged doesn't pass, only a genuine decrease does.
  - **`patch-coverage`** — [`diff-cover`](https://github.com/Bachmann1234/diff_cover)
    against a `pytest --cov` report: the lines this diff *changed* must be
    ≥90% covered (your own threshold to set). Not a whole-repo floor — a
    well-tested old codebase can't carry an untested new file past it.
  - All four skip bot-authored PRs (dependabot, renovate, etc.) — a
    dependency bump usually has no heuristic to apply and no new code to
    test. But only the first three understand `Tidy-Exempt:` — a human's
    `patch-coverage` failure has no trailer bypass, by design; see
    DESIGN.md's "Patch coverage".
- **Two reporting jobs, on by default** — a sticky PR comment and a GitHub
  code-scanning (SARIF) export, surfacing what the gates found where
  you're already looking. Neither blocks a merge; the SARIF one needs a
  public repo or GitHub Advanced Security, the only reason to skip it.
- **A bootstrap script**, not a package dependency — copies the files it
  owns into your repo and prints exactly what to wire up by hand. Never
  silently merges into files that vary per project.
- **Agent-agnostic guidance** (`AGENTS.md`) — the catalog and procedure are
  plain markdown any tool or human can read; an optional thin skill
  wrapper is included for teams using Claude Code specifically.

See [DESIGN.md](DESIGN.md) for the full rationale behind each of
these — calibration numbers, engine choices, what's grandfathered and why.
None of it is required reading to use the tool.

## Requirements

`tidy` needs only `bash` and `git` — every dev machine and CI runner
already has both. `refactor-first` and `complexity` each need their own
Python toolchain (below); skip either gate and you skip its dependency too.
`patch-coverage` needs your own `pytest --cov` setup plus `diff-cover` —
skip it if your repo isn't Python/pytest-shaped, or doesn't have a test
suite worth gating on yet. The pre-push hook is optional (CI catches
everything it does, just later). The two reporting jobs are part of the
default setup; skip `craftcov-sarif` only if your repo has neither a public
visibility nor GitHub Advanced Security to run code scanning with.

## Install

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/gbelbe/craft-gate /tmp/craft-gate
bash /tmp/craft-gate/bootstrap.sh ~/code/my-project
```

This copies the files craft-gate owns (`CRAFTSMANSHIP.md`, `catalog.yaml`,
every `scripts/*`, `.claude/skills/tidy-first/SKILL.md`) into your repo and
prints the manual steps below — each is a template file to merge, not
something bootstrap.sh guesses at, since these vary too much per project to
auto-merge safely:

| # | What | Template | Goes into |
|---|---|---|---|
| 1 | Pre-push hook (optional) | `templates/pre-commit-hook.yaml` | `.pre-commit-config.yaml` |
| 2 | CI gates + reporting (all six jobs, on by default) | `templates/ci-job.yml` | `.github/workflows/ci.yml` |
| 3 | Agent guidance | `templates/AGENTS.md.snippet.md` | `AGENTS.md` |
| 4 | Weekly auto-update | `templates/update-check.yml` | `.github/workflows/craft-gate-update.yml` |

Row 3 targets `AGENTS.md`, the cross-tool convention a growing set of
coding agents read directly. Check what your own agent looks for; if it's
a different filename, point it at `AGENTS.md` or symlink
(`ln -s AGENTS.md CLAUDE.md`).

`refactor-first` and `complexity` need their own toolchains added to your
dependency file (exact versions — see this repo's own `pyproject.toml`):

```toml
craftcov = ["pyyaml>=6.0", "ruff>=0.13", "pylint>=3.3", "vulture>=2.14"]
complexity = ["radon>=6.0", "cognitive-complexity>=1.3"]
```

`patch-coverage` needs `diff-cover` (and a coverage runner — `pytest-cov`
or plain `coverage`) in your own `dev`-style dependency group, not a new
craft-gate-owned extra: this gate runs *your* test suite, which craft-gate
has no involvement in beyond wiring the job.

`craftcov-sarif` needs a **public repo or GitHub Advanced Security** — the
only one of the six default jobs with a real precondition; code scanning
isn't available otherwise.

Confirm the install works:

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main   # your default branch
```

**Optional, not printed by `bootstrap.sh`:** `templates/tdd-bdd-yagni.snippet.md`
is a companion `AGENTS.md` section mandating a Gherkin spec and a test list
*before* implementation, with an explicit YAGNI challenge first. A
methodology choice, not a craftsmanship gate — skip it if your project
doesn't use BDD.

**Optional, and not one of the six default jobs:** `templates/mutation-ratchet-job.yml`
wires [`mutmut`](https://github.com/boxed/mutmut) + `scripts/check_mutation_ratchet.py`
in — a function this PR's diff touches must clear a mutation-score floor
(80% starting point), catching tests that execute a line without actually
asserting anything about it. Left out of the default set on purpose:
mutation testing reruns your whole suite once per mutant, a different cost
order than every other gate here. Needs the `mutation` extra (`mutmut`)
plus your own test-running dependencies. See DESIGN.md's "Mutation
ratchet" for the full rationale.

Step 4 matters most in practice — without it, staying current means
remembering to re-run `bootstrap.sh` by hand. See **Staying current**
below.

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
# ── Cited sources (Tidy-Source: trailer) ────────────────
#    9 Kent Beck, Tidy First? (2023)
#    5 Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
```

## Repo layout

```
CRAFTSMANSHIP.md          procedure, commit convention, legacy-code method
                           (hand-written) + the two catalog tables
                           (generated — see catalog.yaml)
catalog.yaml               the actual catalog data — edit this, not the
                           tables in CRAFTSMANSHIP.md directly
pyproject.toml             PyYAML (base) + the craftcov / complexity / mutation extras
scripts/
  check_tidy_ratchet.sh     the CI/pre-push ratchet
  report_tidy_history.sh    the periodic exemption-ratio / sources report
  render_catalog.py         catalog.yaml -> CRAFTSMANSHIP.md's tables (--check in CI)
  craftcov.py               coverage-style scan for the detectable heuristics
  check_refactor_first.py   CI gate: a touched file's craftCov total must go down
  check_complexity_ratchet.py  CI gate: complexity, invariant return, duplicated literal
  craftcov_pr_comment.py    optional: sticky PR comment
  check_mutation_ratchet.py optional: touched functions' mutation score (needs mutmut)
  next_version.py           Conventional-Commits -> semver, used by release.yml
skills/tidy-first/
  SKILL.md                 optional Claude Code skill wrapper around CRAFTSMANSHIP.md
templates/
  AGENTS.md.snippet.md       section to paste into your AGENTS.md
  tdd-bdd-yagni.snippet.md   optional companion section
  pre-commit-hook.yaml       hook entry for .pre-commit-config.yaml
  ci-job.yml                 job fragments for .github/workflows/ci.yml
  mutation-ratchet-job.yml   optional job fragment, not part of ci-job.yml's default six
  update-check.yml           weekly drift-check + auto-PR
bootstrap.sh               installer/updater
tests/
  fixtures/                 ground truth for craftCov's detectors
  test_fixtures.py          checks each detector fired where it should
```

This repo applies its own tooling to itself (`AGENTS.md`,
`.pre-commit-config.yaml`, `.claude/skills/tidy-first/SKILL.md` — produced
by `bash bootstrap.sh .`, not hand-written).

## Staying current

Every push to `main` auto-tags a release (`next_version.py` reads
Conventional Commits: `feat:` → minor, `fix:`/`perf:`/`refactor:` → patch, a
breaking-change footer → major). Pin a version with `git clone --branch
vX.Y.Z`; `main` always has the latest, possibly-unreleased state.

Add `templates/update-check.yml` as
`.github/workflows/craft-gate-update.yml` and you never have to remember to
re-run `bootstrap.sh`: a weekly job compares your `.craft-gate-version`
against the latest release and opens a PR with whatever changed. Nothing
auto-merges — review it like any other dependency bump. No new credentials:
it uses the repo's own default `GITHUB_TOKEN`, and craft-gate is only ever
read from, never written to.

## Badge

A static claim that the gates are wired in, the same pattern
[pre-commit](https://github.com/pre-commit/pre-commit) uses for its own
badge:

```md
[![craft-gate](https://img.shields.io/badge/craft--gate-enabled-blue)](https://github.com/gbelbe/craft-gate)
```

[![craft-gate](https://img.shields.io/badge/craft--gate-enabled-blue)](https://github.com/gbelbe/craft-gate)

Or point at your own CI run instead of a static claim — live pass/fail,
same technique this README's own `CI` badge at the top uses:

```md
[![CI](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<you>/<repo>/actions/workflows/ci.yml)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — adding a heuristic is a one-file
`catalog.yaml` edit plus a regenerate command.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, strip out what your team
doesn't want.
