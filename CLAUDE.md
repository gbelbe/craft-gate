# craft-gate — Claude Code guidelines

This repo is the source of the practice it ships, so it follows its own
rules — installed on itself via `bash bootstrap.sh .` (see `.claude/skills/`
and `.pre-commit-config.yaml`, both produced that way, not hand-written).

## Code quality gate (mandatory before every commit)

```bash
python3 -c "import yaml; yaml.safe_load(open('catalog.yaml'))"   # catalog.yaml parses
for f in scripts/*.sh; do bash -n "$f"; done                     # scripts parse
bash scripts/check_tidy_ratchet.sh --base origin/main            # this commit range earned its tidy
```

Or let CI's `validate` and `tidy` jobs do it — see `.github/workflows/ci.yml`.
(`refactor-first` and `complexity`, same file, are diff-aware against a
real base branch the same way `tidy` is — there's nothing useful to run
locally for either outside a PR context; see below.)

## Tidy First & craftsmanship (mandatory before every feature/fix commit)

Before writing a feature or fix, check the file(s)/function(s)/class(es) it
touches against the catalog in `CRAFTSMANSHIP.md` (Kent Beck's *Tidy First?*,
Fowler's *Refactoring* smells, *Clean Code*, and Feathers' legacy-code
method). If a tidying applies, do it alone, verify the suite is unchanged,
and commit it separately, naming the source:

```
tidy(<type>): <what and where>

Tidy-Type: <type>
Tidy-Source: <author, book>
```

Only then commit the feature/fix. If nothing applies, don't invent one —
commit with a `Tidy-Exempt: <reason>` trailer instead.

The catalog is also a checklist for **new** code, not just a pre-touch
ritual: Beck's four rules of simple design (pass the tests, reveal intention,
no duplication, fewest elements) and Clean Code's function-size/SOLID
principles are the acceptance bar for anything written from scratch — there's
nothing to "tidy" in code that doesn't exist yet, but there's everything to
get right the first time.

Touching code with no tests? It's legacy by Feathers' definition regardless
of age — write a `test(characterize):` commit pinning its current behavior
first, *then* tidy under that safety net. See `CRAFTSMANSHIP.md`'s "Working
with legacy code."

The `tidy-ratchet` check (pre-push hook / CI, `scripts/check_tidy_ratchet.sh`)
enforces the discipline — it fails a push/PR with no `tidy(...)` commit, no
`test(characterize):` commit, and no `Tidy-Exempt:` trailer in range. It's a
text check on commit messages only, so it costs milliseconds; it cannot judge
whether the right tidying was picked.

For the 8 heuristics craftCov detects (`scripts/craftcov.py
--list-detectors`), skip the judgment call: `scripts/craftcov.py --file
<path>` before touching a file, fix one instance of every heuristic present,
bundle it into one `tidy(multi):` commit (see CRAFTSMANSHIP.md's "Refactor
First"). CI's `refactor-first` job (`scripts/check_refactor_first.py`)
enforces the outcome — a touched file's total must go down, or stay at 0 —
`Tidy-Exempt:` bypasses it too.

A third, independent gate covers cyclomatic/cognitive complexity, invariant
return, and duplicated string literal (CG032-CG035, no `detectors` field —
craftcov.py has no awareness of it): `scripts/check_complexity_ratchet.py`
(CI's `complexity` job) fails a touched function/literal whose metric got
worse than where the branch diverged. Same `Tidy-Exempt:` bypass. See
CRAFTSMANSHIP.md's "The complexity ratchet".

**Write within these limits from the start**: CRAFTSMANSHIP.md's "The
mechanical floor" table has the exact numbers these two gates check (≤5
params, ≤50 statements, ≤12 branches, ≤7 instance attributes, ≤15
cyclomatic/cognitive complexity, etc.) — know them while writing, not only
when a gate flags something after the fact. Before calling a change done,
run `scripts/craftcov.py --file <path>` and
`scripts/check_complexity_ratchet.py --path <dir> --base origin/main`
against what you touched.

## Editing this repo specifically

- `CRAFTSMANSHIP.md` and `catalog.yaml` must stay in sync by hand — the
  content is the same, the format differs (prose table vs. structured data).
  CI's `validate` job checks `catalog.yaml` parses and every entry has a
  `kind`/`source`; it doesn't diff the two files against each other, so a
  new catalog entry added to one and not the other won't be caught
  automatically. Add to both in the same commit.
- `skills/tidy-first/SKILL.md` is the distributable template — its wording
  is written to be correct once copied to `.claude/skills/tidy-first/` in
  *any* repo (including this one), not just as read in place. Don't add a
  relative link back to `CRAFTSMANSHIP.md`; the "no link, say 'repo root'"
  choice is deliberate (see the comment inside the file).
- `templates/` are fragments, not complete files (`ci-job.yml` is a single
  job meant to be pasted under an existing `jobs:` key) — the CI `validate`
  job wraps `ci-job.yml` in a synthetic `jobs:` key before parsing it, which
  is why that check looks slightly different from the others.
