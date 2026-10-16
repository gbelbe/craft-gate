# craft-gate — agent guidelines

This repo is the source of the practice it ships, so it follows its own
rules — installed on itself via `bash bootstrap.sh .` (see
`.pre-commit-config.yaml`, produced that way, not hand-written). This file
is coding-agent-agnostic; `.claude/skills/tidy-first/SKILL.md` is an
optional thin wrapper for teams using Claude Code specifically — the actual
procedure lives in `CRAFTSMANSHIP.md`, which both point back to.

## Code quality gate (mandatory before every commit)

```bash
uv run --extra dev pytest tests                                  # the suite
uv run --extra dev ruff check scripts tools tests/*.py tests/features/*.py           # lint (what CI runs)
uv run --extra dev ruff format --check scripts tools tests/*.py tests/features/*.py
python3 tools/render_catalog.py --check                          # generated docs match catalog.yaml
bash scripts/check_tidy_ratchet.sh --base origin/main            # this commit range earned its tidy
```

Then, against a real base ref, the three diff-aware gates (CI runs the same
commands on a PR, and they work locally too):

```bash
uv run --extra dev python3 scripts/check_refactor_first.py --base origin/main
uv run --extra dev python3 scripts/check_complexity_ratchet.py --base origin/main --path .
```

CI's `validate`, `craftcov`, `tidy`, `refactor-first` and `complexity` jobs
(`.github/workflows/ci.yml`) are required to merge; see below for what each
checks. `docs/architecture.md` has the map of how they fit together.

Before you push, read your own design prompts and get an independent review. Run
`python3 scripts/design_review.py --base origin/main` (it also runs in
`scripts/local-craft-gate.sh`) and either fix each prompt or write one line on why it does not
apply. Then run the `craft-review` skill: it hands the diff to the `craft-reviewer` subagent, a
lead-developer reviewer with no knowledge of how the code was written. Give it nothing but the
base ref; your reasons are exactly what it must not inherit. Present its findings as they come,
fix them or say why not. Both are advisory: they cover the judgement calls no gate can make (see
`docs/design/reviewer.md`).

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

For the heuristics craftCov detects (`scripts/craftcov.py
--list-detectors`), skip the judgment call: `scripts/craftcov.py --file
<path>` before touching a file, fix one instance of every heuristic present,
bundle it into one `tidy(multi):` commit (see CRAFTSMANSHIP.md's "Refactor
First"). CI's `refactor-first` job (`scripts/check_refactor_first.py`)
enforces the outcome — a touched file's total must go down, or stay at 0 — and,
separately, that no finding sits on a line you added or rewrote. `Tidy-Exempt:`
waives the first (legacy debt) but never the second: new code is never exempt.

A third, independent gate covers cyclomatic/cognitive complexity, invariant
return, and duplicated string literal (CG032-CG035, no `detectors` field —
craftcov.py has no awareness of it): `scripts/check_complexity_ratchet.py`
(CI's `complexity` job) grandfathers a function/literal the diff never
reaches, but one it *does* reach that's already over threshold must come
out lower than it went in — unchanged doesn't pass. `Tidy-Exempt:` waives that
debt rule, but a new function over the threshold, a new invariant return or a new
duplicated literal fails regardless. See CRAFTSMANSHIP.md's "The complexity ratchet".

**Write within these limits from the start**: CRAFTSMANSHIP.md's "The
mechanical floor" table has the exact numbers these two gates check (≤5
params, ≤50 statements, ≤12 branches, ≤7 instance attributes, ≤15
cyclomatic/cognitive complexity, etc.) — know them while writing, not only
when a gate flags something after the fact. Before calling a change done,
run `scripts/craftcov.py --file <path>` and
`scripts/check_complexity_ratchet.py --path <dir> --base origin/main`
against what you touched.

A fourth gate covers whether new code is tested at all, not just
well-structured: CI's `patch-coverage` job runs `diff-cover` against a
coverage report, failing when the lines *this diff changed* are
under-covered — a whole-repo average can't hide behind old tests carrying
new, untested code. No `Tidy-Exempt:` bypass here — write the test with
the code, not after a gate asks for it.

A fifth gate goes one step further: coverage only proves a line *ran*, not
that a test would notice if its behavior changed. CI's `mutation-ratchet`
job (`mutmut`) mutates a small piece of a touched function's logic and
reruns the tests — a function whose mutants all survive has tests that
execute it without actually checking anything. Write toward killing
mutants (exact-value assertions, both sides of every boundary, every
branch tested on its own — see `templates/tdd-bdd-yagni.snippet.md`'s
"Writing tests mutants can't survive" if this repo has that section) as a
matter of course, not just when this gate flags something. No
`Tidy-Exempt:` bypass here either — a genuinely equivalent mutant gets
mutmut's own `# pragma: no mutate`.

**The numbers live in `craft-gate.toml`** (or `[tool.craft-gate]` in `pyproject.toml`): the
complexity limits, Refactor First's per-file rule, the design-review limits, the thresholds of the
test gates, and what a `Tidy-Exempt:` trailer may waive. craft-gate's `templates/craft-gate.toml`
lists every value with its default. Read the repo's file for the real numbers before you write
code, and **never loosen a value to make a gate pass**: fix the code. If a change must edit that
file, say why in the commit message: the PR comment lists every value the change loosens, and a
person decides, because a looser value fails no check.

**The test gates are on by default.** `patch-coverage`, `mutation-ratchet` and
`behaviour-coverage` run unless the config switches one off with `enabled = false` and a written
`reason`. A gate that is on but has nothing to check (no pytest suite, no `[tool.mutmut]`, no
`.feature` files) fails; it never passes silently. Write the test with the code.

**Behaviour coverage.** Where the repo has Gherkin scenarios (default `tests/features`), every
line you add or change must be exercised by a scenario, not only by unit tests: add or extend a
scenario with the change. Test files are left out of the patch and behaviour percentages, so a
test's own lines never count toward them.

**Opening a pull request.** If the repo has `.github/PULL_REQUEST_TEMPLATE.md`, fill in its reviewer
checklist honestly (one thing per function, names, commands vs queries, responsibility, tests that
state the behaviour, YAGNI): tick what you checked, or say why it does not apply. It covers the
judgement calls no gate can make.

Mutation-quality rule for new tests:

- Every changed production function needs a focused behavioral test or an
  explicit explanation that an existing test covers it.
- New tests should assert exact observable behavior, not just execution or
  truthiness.
- Add boundary, empty, and error cases for changed branches.
- Use focused mutmut and inspect survivors before declaring the change complete.
- The ratchet passes at the threshold (80% by default, `craft-gate.toml`), or
  after a 20% improvement over the function's recorded baseline, which never
  asks for more than the threshold itself. A function with no recorded baseline
  (new, or never measured) has no second chance: it must reach the threshold on
  the first push. Design the tests for that before writing them.

## Editing this repo specifically

- `catalog.yaml` is the source of truth; `CRAFTSMANSHIP.md`'s tables, counts and
  the README badge are generated from it (`python3 tools/render_catalog.py`).
  The steps, and the `principle`/`workflow` entries you still write by hand,
  are in `CONTRIBUTING.md`; don't duplicate them here.
- `scripts/` is exactly what `bootstrap.sh` installs into other repos; this
  repo's own tooling goes in `tools/`. Files in `scripts/` import each other by
  bare name and must work when run by path from any directory.
- `skills/tidy-first/SKILL.md` is the distributable template — its wording
  is written to be correct once copied to `.claude/skills/tidy-first/` in
  *any* repo (including this one), not just as read in place. Don't add a
  relative link back to `CRAFTSMANSHIP.md`; the "no link, say 'repo root'"
  choice is deliberate (see the comment inside the file).
- `templates/` are fragments, not complete files (`ci-job.yml` is a single
  job meant to be pasted under an existing `jobs:` key) — the CI `validate`
  job wraps `ci-job.yml` in a synthetic `jobs:` key before parsing it, which
  is why that check looks slightly different from the others.
