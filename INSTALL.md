# Wiring craft-gate into a repo

`bootstrap.sh` copies the files craft-gate fully owns. It never edits your
`AGENTS.md`, `.pre-commit-config.yaml` or CI workflow, because those differ too
much per project to merge automatically. These are the steps it leaves to you.

In the commands below, `$CRAFT_GATE` is the craft-gate checkout you ran
`bootstrap.sh` from. Re-run `bash $CRAFT_GATE/bootstrap.sh <repo>` any time to
pull an update.

## 1. Local pre-push hook

```bash
cat $CRAFT_GATE/templates/pre-commit-hook.yaml
```

Merge its `local` repo block into `.pre-commit-config.yaml` (or start from it if
you have none), then `prek install --hook-type pre-push`.

## 2. CI jobs

```bash
cat $CRAFT_GATE/templates/ci-job.yml
```

Add the jobs to `.github/workflows/ci.yml` and set your branch name. There are
eight: six gates (the tidy ratchet, Refactor First, the complexity ratchet,
patch coverage, the mutation ratchet, behaviour coverage) and two reporting jobs (a sticky PR comment
and a code-scanning SARIF upload) that show what the gates found without blocking
a merge themselves.

Each gate needs its own toolchain; skip a gate and you skip its dependency:

| Gate | Needs |
|---|---|
| Refactor First | a `craftcov` extra: ruff, pylint, vulture (and pyyaml unless already a dependency) |
| Complexity ratchet | a `complexity` extra: radon, cognitive-complexity |
| Patch coverage | `diff-cover` and a coverage runner in your dev deps, and a pytest suite |
| Mutation ratchet | a `mutation` extra (mutmut), your own test-running deps, and a `[tool.mutmut]` section in `pyproject.toml` |
| Behaviour coverage | `pytest-bdd` (or any runner that puts scenarios under pytest) and `.feature` files under `tests/features` |

The last three are on by default and take their settings from `pyproject.toml`'s
`[tool.craft-gate]`, not from the workflow file. To skip one, set `enabled = false`
with a `reason` there; a gate that is on but has nothing to check fails and tells you
so. CRAFTSMANSHIP.md's "Test gates" has the table and an example.
| SARIF upload | a public repo or GitHub Advanced Security. Skip just this job if neither applies |

The local runner is `scripts/local-craft-gate.sh`. Call it after your test
command has produced `coverage.xml`; it writes `craftcov-report.md` and
`craftcov.sarif` and reuses mutmut's `mutants/` cache.

Exact version pins are the extras in this repo's `pyproject.toml` (`craftcov`, `complexity`, `mutation`). The rationale for each
gate is in `DESIGN.md`, which indexes the notes under `docs/design/` (craftCov, the complexity ratchet, patch coverage, the
mutation ratchet, reporting).

## 3. AGENTS.md

```bash
cat $CRAFT_GATE/templates/AGENTS.md.snippet.md
```

Append it to your project's `AGENTS.md` (or create one). This is the
cross-tool convention a growing set of coding agents read directly. If yours
looks for a different filename (e.g. `CLAUDE.md`), point it at `AGENTS.md` or
symlink: `ln -s AGENTS.md CLAUDE.md`.

Optional, and not a craftsmanship gate: `templates/tdd-bdd-yagni.snippet.md` is a
TDD + BDD + YAGNI workflow section. Skip it if you don't want test-first
mandated for every feature.

## 4. Stop needing to remember to re-run bootstrap (optional)

```bash
cp $CRAFT_GATE/templates/update-check.yml .github/workflows/craft-gate-update.yml
```

A weekly workflow that checks for a new craft-gate release and opens a PR with
the diff. No new credentials needed.

## 5. Label tidy PRs (optional, recommended)

```bash
cp $CRAFT_GATE/templates/label-tidy-prs.yml .github/workflows/craft-gate-label.yml
```

Labels PRs that carry `tidy(...)` commits or a `Tidy-Exempt` trailer, so
`gh pr list --label tidy-first` (or `--label tidy-exempt`) finds them. The
workflow warns if squash merges would drop the commit list; its header comment
has the one-line repo setting that fixes that.

## 6. PR checklist for the judgement calls (optional, recommended)

```bash
cp $CRAFT_GATE/templates/PULL_REQUEST_TEMPLATE.md .github/PULL_REQUEST_TEMPLATE.md
```

The gates check what can be measured. This template is the reviewer's list for what
cannot: whether a function does one thing, whether names say what they mean, command-query
separation, responsibility, whether tests state the behaviour, and YAGNI. It pairs with the
"Design review (advisory)" section the PR comment adds, which flags functions worth a second
look (flag arguments, more than two parameters, "and" in a name, a query that changes state,
long functions). Neither blocks a merge; a person decides.

`bootstrap.sh` also installs the `craft-review` skill and the `craft-reviewer` subagent
(`.claude/skills/craft-review/`, `.claude/agents/craft-reviewer.md`) for Claude Code users: an
independent, read-only review of the current branch, run before pushing. See
`docs/design/reviewer.md`. Other tools can use `agents/craft-reviewer.md` as a plain prompt.

## 7. Review requirement on the gates themselves (optional)

```bash
cat $CRAFT_GATE/templates/CODEOWNERS.snippet
```

Add it to `.github/CODEOWNERS` with your handle, and turn on "Require review
from Code Owners" in branch protection.
