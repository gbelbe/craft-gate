# Changelog

Releases are tagged automatically from Conventional Commits (see
[Staying current](README.md#staying-current)); this file is the human summary.
Versions below v0.22.1 are reconstructed from the git history, so a line
describes the change as it shipped, not every commit. `git log vX..vY` has the
rest.

While the major version is 0, a breaking change bumps the minor version.

## Unreleased

- **Added:** `craft-gate.toml`, one readable file for every number and rule the gates use: the
  complexity limits, Refactor First's per-file rule, the design-review limits, the test gates'
  thresholds, and what a `Tidy-Exempt:` trailer may waive. Copy `templates/craft-gate.toml`; every
  value in it is the default, so adding it changes nothing. `[tool.craft-gate]` in `pyproject.toml`
  still works and the standalone file wins. Unknown keys and out-of-range values are errors.
  Each value has a Gherkin scenario showing it changes a verdict, and a test fails if one does not.
- **Changed:** the agent guidance (`AGENTS.md`, the paste-in snippet, the `tidy-first` skill) now
  covers the config file, the default-on test gates, behaviour coverage and "never loosen a value
  to pass"; a test keeps every gate named in all three.

- **Added:** an independent reviewer for Claude Code users. The `craft-reviewer` subagent
  reviews a branch as a lead developer with no knowledge of how it was written, against the
  catalog's new-code principles; every finding must quote the code and cite a catalog code. The
  `craft-review` skill runs it. Advisory and read-only; `bootstrap.sh` installs both, and the
  local runner now prints the design-review prompts. Also: `tidy-first`'s frontmatter was invalid
  YAML (an unquoted `: ` in its description); it is now a folded block, and a test parses every
  shipped skill and agent.

- **Added:** an advisory "Design review" section in the PR comment
  (`scripts/design_review.py`). For the Python functions a change touched it flags
  flag arguments, more than two parameters, "and" in a name, a query that changes
  state, and long functions, as prompts for the reviewer. Nothing blocks. Also a
  PR checklist template (`templates/PULL_REQUEST_TEMPLATE.md`) for the judgement calls
  with no smell to flag.

## v0.24.1 — 2026-10-14

- **Fixed:** patch coverage and behaviour coverage counted test files' own changed lines, which
  always run, so they padded the percentage (a trial repo passed at 90% with 71% of the production
  lines covered by scenarios). Both now exclude test files by default (`exclude`, settable in
  `[tool.craft-gate.<gate>]`). Re-copy the jobs from `templates/ci-job.yml` and
  `scripts/local-craft-gate.sh` to get it.

## v0.24.0 — 2026-10-13

- **Breaking:** a `Tidy-Exempt:` trailer no longer skips Refactor First and the
  complexity ratchet outright. It waives only what is about legacy debt (a touched
  file's total must go down; a touched over-threshold function must come out lower).
  New code is always checked: Refactor First fails any finding on a line the change
  added or rewrote (a new file must scan clean), and the complexity ratchet fails a new
  function over the threshold, a new invariant return and a new duplicated literal.
  Before, an exempt PR could add all of those and pass.

## v0.23.0 — 2026-10-13

- **Breaking:** the three test gates, patch coverage, the mutation ratchet and a new
  behaviour-coverage gate, are **on unless the repo declares otherwise**. Before,
  they ran only if you pasted the job in, and the mutation job quietly passed
  without `[tool.mutmut]`. Now each job first asks `scripts/gate_config.py`: it
  runs, is skipped because `pyproject.toml`'s `[tool.craft-gate.<gate>]` says
  `enabled = false` with a required `reason` (shown in the PR comment), or fails
  saying what the repo lacks. To upgrade, re-run `bootstrap.sh`, copy the new jobs
  from `templates/ci-job.yml`, and for each gate you don't want yet add the opt-out.
- **Added:** behaviour coverage. It runs only the Gherkin scenarios
  (`tests/features` by default) under coverage and requires the lines a diff
  changed to be covered by them. Thresholds are settings now (`threshold`,
  `improvement`), not edits to the workflow.
- **Added:** the PR comment lists the test gates a repo has switched off, and why.

## v0.22.2 — 2026-10-13

Internal restructuring and tests; nothing a consumer has to change.

- `bootstrap.sh` is driven by one file list and prints a pointer instead of 60
  lines of instructions; the manual steps now live in `INSTALL.md`.
- `scripts/` holds exactly what `bootstrap.sh` installs. This repo's own tooling
  (`render_catalog.py`, `next_version.py`) moved to `tools/`. The gate scripts no
  longer insert their own directory into `sys.path`; Python already does when a
  script is run by path.
- The catalog counts in `CRAFTSMANSHIP.md`, the README badge and `AGENTS.md`
  are generated from `catalog.yaml` by `tools/render_catalog.py`, and checked
  in CI. A test fails when a catalog code is missing from `CRAFTSMANSHIP.md`.
- craftCov's summary is a `Summary` dataclass and a finding a `Finding`
  `TypedDict`; the JSON report is unchanged.
- The test suite runs under pytest, with tests for the complexity, Refactor
  First, PR-comment and bootstrap scripts.
- The documentation is split: `DESIGN.md` is an index of per-gate notes under
  `docs/design/`, with an architecture page and an operating guide.

## v0.22.1 — 2026-10-13

- **Fixed:** a file the tokenizer can't read no longer crashes the craftCov
  scan (the duplicate-code pass caught a nonexistent `tokenize.TokenizeError`).
- **Fixed:** nested class and method names no longer get a doubled dot
  (`Outer..Inner`), so `--class Outer.Inner` now matches. The scan cache
  version was bumped, so cached names are rescanned once.
- **Changed:** `craftcov.py` is now a thin entry point over the
  `scripts/craftcov_core/` package (catalog, discovery, scopes, dupes, adapters,
  scan, cache, summary, models, render, pipeline, cli). The command line, report
  text, JSON and SARIF output are unchanged. `bootstrap.sh` ships the package
  and removes modules a release no longer has.

## v0.22.0 — 2026-10-13

- **Added:** diff-scoped mutation runs. A change re-tests only the mutants it
  can have affected (`scripts/mutation_plan.py`), instead of the whole set.
- **Changed:** the gate scripts share their git and AST helpers
  (`scripts/gitdiff.py`, `scripts/astfuncs.py`); `bootstrap.sh` installs them
  with the scripts that import them.
- **CI:** fails when this repo's installed gate copies drift from their sources.

## v0.21.0 — 2026-10-10

- **Breaking:** the mutation ratchet no longer gives a function with no
  recorded baseline a second chance. A new (or never-measured) function must
  reach the 80% threshold on its first push; the 20% improvement path applies
  only to functions with a recorded baseline.
- **Docs:** "what to expect before you push": the gate behaviours that surprise
  a first-time PR.

## v0.20.0 — 2026-10-05

- **Added:** a workflow that labels PRs carrying `tidy(...)` commits or a
  `Tidy-Exempt:` trailer, and a `CODEOWNERS` template for the gate files.

## v0.19.x — 2026-10-03 to 2026-10-05

- **v0.19.2 fixed:** a duplicate import and function in the mutation ratchet.
- **v0.19.1 fixed:** the mutation baseline fingerprint is preserved.
- **v0.19.0 added:** the mutation improvement ratchet. A function passes at 80%,
  or by improving 20% on its recorded baseline.

## v0.17.0 – v0.18.0 — 2026-09-30 to 2026-10-03

- **v0.18.0:** the mutation ratchet runs against a focused test selection.
- **v0.17.1:** guidance and tests for focused mutation test selection.
- **v0.17.0:** the mutation ratchet becomes a default gate, opted out of by
  leaving its config absent rather than opted into.

## v0.16.0 — 2026-09-29

- **Added:** an optional mutation-testing ratchet on top of mutmut.

## v0.15.x — 2026-09-29

- **v0.15.0 added:** the patch-coverage gate (diff-cover). The lines a change
  adds must be covered, not just structured.
- **v0.15.1 fixed:** an E501 in `check_complexity_ratchet.py`.

## v0.14.0 — 2026-09-29

- **Changed:** the complexity ratchet requires a touched, over-threshold
  function to come out lower than it went in; unchanged no longer passes.

## v0.11.0 – v0.13.0 — 2026-09-29

- **v0.13.0:** the agent guidance file is agent-agnostic (`AGENTS.md`), and
  the reporting jobs are default.
- **v0.12.0:** the gates skip bot-authored PRs (dependabot, renovate, ...).
- **v0.11.0 added:** craftCov reporting, a sticky PR comment and a GitHub
  code-scanning SARIF upload.

## v0.9.0 – v0.10.1 — 2026-09-28 to 2026-09-29

- **v0.10.1 fixed:** the complexity ratchet scans untracked-but-not-ignored
  files too.
- **v0.10.0 added:** the complexity ratchet, ported from kai-ster. It covers
  cyclomatic and cognitive complexity, invariant return and duplicated string
  literals, and is the third default CI gate.
- **v0.9.1 – v0.9.3:** `scripts/` is held to `line-length = 100` and the ruff
  rule set every consumer repo enables.
- **v0.9.0 added:** Refactor First. A touched file's craftCov total must go down
  or stay at zero.

## v0.3.0 – v0.8.1 — 2026-09-28

- **v0.8.1 fixed:** import statements are excluded from duplicate-code scanning.
- **v0.8.0:** craftCov reports what changed since the last run.
- **v0.7.0:** a ground-truth fixture corpus tests each detector.
- **v0.6.0:** duplicate-code detection, validated and recalibrated against PMD
  CPD.
- **v0.5.0:** craftCov gains pylint and vulture backends; `catalog.yaml` gets
  multi-tool detectors.
- **v0.4.0 added:** craftCov, a coverage-style scan of the 8 mechanically
  detectable heuristics.
- **v0.3.0:** `CRAFTSMANSHIP.md`'s tables are generated from `catalog.yaml`;
  contributing guide.

## v0.2.0

- **Added:** a weekly update-check workflow that opens a PR in a consuming repo
  when a new release is out.

## v0.1.0 — initial release

- `CRAFTSMANSHIP.md` / `catalog.yaml`: 15 Tidy First tidyings (Beck), 9
  Fowler smell-and-fix pairs, 6 new-code principles (Martin, Beck-XP), the
  legacy-code characterization-test workflow (Feathers), and Sandi Metz's
  rules as an optional stricter reference.
- `scripts/check_tidy_ratchet.sh`: commit-message ratchet, recognizes
  `tidy(<type>):`, `test(characterize):`, and `Tidy-Exempt:`.
- `scripts/report_tidy_history.sh`: exemption-ratio and cited-sources report.
- `skills/tidy-first/SKILL.md`: thin Claude Code wrapper.
- `templates/`: agent-guidance section, pre-commit hook entry, CI job fragment.
- `bootstrap.sh`: install/update script for consuming repos.
- Self-applied to this repo, with automatic semantic-version releases.
