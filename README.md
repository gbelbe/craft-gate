# craft-gate

[![CI](https://github.com/gbelbe/craft-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/gbelbe/craft-gate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![craft-gate](https://img.shields.io/badge/craft--gate-enabled-blue)](https://github.com/gbelbe/craft-gate)
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

- **A named, attributed catalog** (`CRAFTSMANSHIP.md` / `catalog.yaml`) — every
  entry citing its source (see the badge for the count). "Feature Envy (Fowler,
  *Refactoring*)" is a checkable claim; "this could be cleaner" is not.
- **A commit convention** — `tidy(<type>): ...` with a `Tidy-Source:` trailer
  naming the book, `test(characterize): ...` for legacy code, and
  `Tidy-Exempt: <reason>` when nothing applies.
- **Six CI gates**, cheapest first:

  | Gate | Fails a PR when | Needs | `Tidy-Exempt:` waives it |
  |---|---|---|---|
  | `tidy` | no tidying, characterization test or recorded exemption is in the commit range | `bash`, `git` | yes |
  | `refactor-first` | a touched file's total across the 8 detectable heuristics did not go down (or stay at 0), or any finding sits on a line the change added | the `craftcov` extra | the per-file ratchet only; a finding on an added line always fails |
  | `complexity` | a function the diff touches is over threshold and did not come out lower; or a new function over the threshold, invariant return or triplicated literal | the `complexity` extra | the debt rule only; new code always fails |
  | `patch-coverage` | the lines this diff changed are under-covered | `diff-cover` and your own `pytest --cov` | no |
  | `mutation-ratchet` | a touched function's mutants survive: its tests run it but would not notice a change | `mutmut` and a `[tool.mutmut]` section | no |
  | `behaviour-coverage` | the lines this diff changed are not covered by Gherkin scenarios | `pytest-bdd` scenarios under `tests/features` | no |

  The last three are **on by default**. You switch one off in `pyproject.toml`,
  with a written reason that shows in the PR comment; a gate that is on but has
  nothing to check (no suite, no scenarios) fails instead of passing quietly. See
  CRAFTSMANSHIP.md's "Test gates".

  All six skip bot-authored PRs (dependabot, renovate, ...). The reasoning
  behind each is in [DESIGN.md](DESIGN.md).
- **Two reporting jobs** — a sticky PR comment and a GitHub code-scanning
  (SARIF) export. Neither blocks a merge. The SARIF one needs a public repo or
  GitHub Advanced Security, the only reason to skip it.
- **A bootstrap script**, not a package dependency — copies the files it
  owns into your repo and leaves the files that vary per project to you.
- **Agent-agnostic guidance** (`AGENTS.md`) — the catalog and procedure are
  plain markdown any tool or human can read; an optional thin skill wrapper is
  included for teams using Claude Code.

## Install

```bash
# vX.Y.Z: the latest tag, see https://github.com/gbelbe/craft-gate/releases
git clone --branch vX.Y.Z --depth 1 https://github.com/gbelbe/craft-gate /tmp/craft-gate
bash /tmp/craft-gate/bootstrap.sh ~/code/my-project
```

This copies the files craft-gate owns (`CRAFTSMANSHIP.md`, `catalog.yaml`, the
gate scripts, `.claude/skills/tidy-first/SKILL.md`) into your repo. What it
leaves to you is in [INSTALL.md](INSTALL.md), because those files differ too
much per project to merge automatically:

| # | What | Template | Goes into |
|---|---|---|---|
| 1 | Pre-push hook (optional) | `templates/pre-commit-hook.yaml` | `.pre-commit-config.yaml` |
| 2 | CI gates + reporting (all eight jobs) | `templates/ci-job.yml` | `.github/workflows/ci.yml` |
| 3 | Agent guidance | `templates/AGENTS.md.snippet.md` | `AGENTS.md` |
| 4 | Weekly auto-update | `templates/update-check.yml` | `.github/workflows/craft-gate-update.yml` |
| 5 | PR labels for review (optional) | `templates/label-tidy-prs.yml` | `.github/workflows/craft-gate-label.yml` |
| 6 | PR checklist for judgement calls (optional) | `templates/PULL_REQUEST_TEMPLATE.md` | `.github/PULL_REQUEST_TEMPLATE.md` |
| 7 | Review gate changes (optional) | `templates/CODEOWNERS.snippet` | `.github/CODEOWNERS` |

Step 4 matters most in practice; without it, staying current means remembering
to re-run `bootstrap.sh`. Each gate's toolchain, with exact version pins, is
listed in this repo's [`pyproject.toml`](pyproject.toml) extras (`craftcov`,
`complexity`, `mutation`). Skip a gate and you skip its dependency too.

Python 3.10 or later. `scripts/gate_config.py` reads `pyproject.toml` with `tomllib`
(standard library from 3.11); on 3.10 your environment needs `tomli` installed, which
this repo's `pyproject.toml` declares for itself. The scripts are bash and Python, tested on
Linux and macOS; Windows is untested.

Confirm the install works:

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main   # your default branch
```

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

## Documentation

| | |
|---|---|
| [CRAFTSMANSHIP.md](CRAFTSMANSHIP.md) | The catalog, the commit convention, the legacy-code method, the mechanical thresholds |
| [INSTALL.md](INSTALL.md) | The manual wiring steps after `bootstrap.sh` |
| [docs/architecture.md](docs/architecture.md) | How the pieces fit, with a diagram and a repo map |
| [DESIGN.md](DESIGN.md) | Why each gate works the way it does (calibration, engines, what's grandfathered) |
| [docs/operating.md](docs/operating.md) | Staying current, reviewing what craft-gate changed, the badge |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Adding a heuristic or rule; development setup |
| [AGENTS.md](AGENTS.md) | The rules for coding agents working in this repo |
| [CHANGELOG.md](CHANGELOG.md) | What changed in each release |

This repo applies its own tooling to itself (`AGENTS.md`,
`.pre-commit-config.yaml`, `.claude/skills/tidy-first/SKILL.md` are produced by
`bash bootstrap.sh .`, not hand-written).

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, strip out what your team
doesn't want.
