# Changelog

Releases are tagged automatically from Conventional Commits (see
[Staying current](README.md#staying-current)); this file is the human summary.
Versions below v0.22.1 are reconstructed from the git history, so a line
describes the change as it shipped, not every commit. `git log vX..vY` has the
rest.

While the major version is 0, a breaking change bumps the minor version.

## Unreleased

Merged after v0.22.1; none of it changes what a consumer receives except where
noted. `tidy:`, `test:` and `docs:` commits don't cut a release.

- `bootstrap.sh` is driven by one file list and prints a pointer instead of 60
  lines of instructions; the manual steps now live in `INSTALL.md`.
- The catalog counts in `CRAFTSMANSHIP.md`, the README badge and `AGENTS.md`
  are generated from `catalog.yaml` by `scripts/render_catalog.py`, and checked
  in CI.
- The test suite runs under pytest, with tests for the complexity, Refactor
  First and PR-comment gates.

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
