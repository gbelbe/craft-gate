# Reporting

The gates above (`refactor-first`, `complexity`) tell you whether a PR is
allowed to merge; they don't tell anyone *what the debt actually looks
like* — the running total, the trend, what's left. Two default,
non-blocking mechanisms cover that — on by default because visibility
without enforcement is still worth having even where a gate would be too
strict; `craftcov-sarif` is the one exception, skipped when the repo can't
run code scanning at all (see below).

**"What changed in this PR?" — a sticky PR comment**
(`scripts/craftcov_pr_comment.py`, the `craftcov-pr-comment` job). Posts a
comment showing the repo-wide craftCov total and its by-heuristic
breakdown, diffed against where the branch diverged — then *updates that
same comment in place* on every subsequent push. Reuses `diff_by_heuristic`
(the same function driving craftCov's own "changes since last run"),
computed the same way `check_refactor_first.py` computes its per-file
diff: a full scan of the merge-base tree via a throwaway `git worktree`,
compared against HEAD — no persisted state between CI runs to keep in
sync.

```
<!-- craftcov-pr-report -->
## craftCov report

**Repo-wide total: 2579 → 2563 (-16)**

| Code | Heuristic | Before | After | Δ |
|---|---|---|---|---|
| CG002 | `dead-code` | 1699 | 1685 | -14 |
| CG012 | `extract-helper` | 1 | 0 | -1 ✅ |
```

Needs `pull-requests: write` (not the default `read`) to post/edit the
comment — see `templates/ci-job.yml`'s permissions block.

**"What's the current state, and where exactly?" — GitHub code scanning**
(`craftcov.py --format sarif`, the `craftcov-sarif` job). Rather than
building a custom badge-and-report page, craftCov's findings map cleanly
onto SARIF 2.1.0, and `github/codeql-action/upload-sarif` feeds them into
GitHub's own code-scanning dashboard on push to your default branch: a
persistent, browsable, filterable list of every current finding, a native
alert count, and history across runs.

```bash
uv run python3 scripts/craftcov.py --format sarif --no-cache --no-diff > craftcov.sarif
```

**The real catch**: GitHub code scanning needs either a **public repo** or
**GitHub Advanced Security** on a private one — the upload step will fail
(or silently do nothing) if it isn't. Check this before wiring the job in.

Want an actual badge in your README on top of the dashboard? A shields.io
[endpoint badge](https://shields.io/badges/endpoint-badge) reading a small
JSON file that a scheduled or on-push-to-main step writes and commits
works with zero hosting. Not built here (it's real upkeep of its own),
but it's a small addition on top if the dashboard alone isn't visible
enough for your team.

## Advisory design review

The gates check what can be measured. Some Clean Code rules are about intent and cannot
be decided from a diff, but they can be *smelled*, and the PR comment is where a reviewer
is already looking. `scripts/design_review.py` adds a "Design review (advisory)" table to
the comment for the Python functions the change touched (a function with any line the
change added or rewrote, reviewed whole):

| Prompt | Rule it points at |
|---|---|
| a `bool`-annotated or `True`/`False`-defaulted parameter | no flag arguments |
| more than 2 parameters (the gate's hard limit is 5) | prefer 0 to 2 arguments |
| `_and_` in the name | a function does one thing |
| `get_`, `is_`, `has_`, `find_`, `count_`, `compute_`, `calculate_` that assigns to an attribute or calls a mutator on `self` or a parameter | command-query separation |
| more than 20 lines (the gate's limit is 50 statements) | stays small |

Deliberately: deterministic and offline (no model, no credentials, same input, same output);
advisory only (nothing fails); test files are skipped, because fixtures make test functions
look parameter-heavy. The table is capped at 15 rows. A smell is a question, not a verdict:
a flag argument is sometimes right, and the reviewer decides. The rules with no smell to flag
(naming, responsibility, whether a test states the behaviour, YAGNI) are on the PR checklist,
`templates/PULL_REQUEST_TEMPLATE.md`.

