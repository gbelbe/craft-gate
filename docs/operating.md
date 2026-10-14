# Operating craft-gate in a repo

## Staying current

Every push to `main` auto-tags a release (`tools/next_version.py` reads
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

## Reviewing what craft-gate changed

Everything craft-gate does reaches a repo through a PR, so review starts from
labels, the way Dependabot's `dependencies` label works:

```sh
gh pr list --label craft-gate  --state all   # automated version syncs
gh pr list --label tidy-first  --state all   # PRs with tidy(...) / test(characterize) commits
gh pr list --label tidy-exempt --state all   # every use of a Tidy-Exempt bypass
```

`craft-gate` is applied by `update-check.yml`; the other two by
`templates/label-tidy-prs.yml`, which follows the PR's commits and lists the
`Tidy-Exempt:` reasons in its run summary. `tidy-exempt` is the one worth
auditing, since it skips the Tidy First and Refactor First gates.

Squash merging collapses a PR's commits into one, so the base branch only keeps
the `tidy(...)` subjects and `Tidy-Exempt:` trailers if the squash message lists
them. Set it once (needs admin) and `git log --grep='^tidy('` works on `main`:

```sh
gh api -X PATCH repos/<owner>/<repo> \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=COMMIT_MESSAGES
```

A looser `craft-gate.toml` fails no check, so the PR comment has a "Thresholds loosened" section
(`scripts/config_loosening.py`): it compares the config at the base with the head and lists each
value that got weaker, with before and after. It never blocks. `templates/CODEOWNERS.snippet` adds
the last piece: review on changes to the gate files and the config, so a person decides.
It only blocks merges when branch protection requires Code Owner review.

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
