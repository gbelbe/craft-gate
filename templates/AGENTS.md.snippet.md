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

For the subset of the catalog craftCov can detect mechanically (`scripts/
craftcov.py --list-detectors`, if you've installed the `craftcov` extra —
see README), skip the judgment call: `scripts/craftcov.py --file <path>`
before touching a file, fix one instance of every heuristic it finds
present, bundle it all into one `tidy(multi):` commit (see
`CRAFTSMANSHIP.md`'s "Refactor First" for the exact convention). CI's
`refactor-first` job (`scripts/check_refactor_first.py`,
`templates/ci-job.yml`) enforces the *outcome* — a touched file's total
across those heuristics must go down, or stay at 0 — the same
`Tidy-Exempt:` trailer bypasses it too.

A third, independent gate covers cyclomatic/cognitive complexity,
invariant return, and duplicated string literal (if you've installed the
`complexity` extra — see README): `scripts/check_complexity_ratchet.py`
(CI's `complexity` job) grandfathers a function/literal the diff never
reaches, but one it *does* reach that's already over threshold must come
out lower than it went in — unchanged doesn't pass, only a genuine
decrease does (needn't reach the threshold in one PR). `Tidy-Exempt:`
bypasses this one too — one exemption mechanism for all three gates. See
`CRAFTSMANSHIP.md`'s "The complexity ratchet".

**Write within these limits from the start, don't wait for a gate to catch
it**: CRAFTSMANSHIP.md's "The mechanical floor" table has the *exact*
numbers `refactor-first`/`complexity` check (≤5 params, ≤50 statements,
≤12 branches, ≤7 instance attributes, ≤15 cyclomatic/cognitive complexity,
no repeated 5+ char literal more than twice per file, etc.) — know them
while writing new code, not only when craftCov or the complexity ratchet
flags something after the fact. Before calling a change done, run both
locally against what you touched: `scripts/craftcov.py --file <path>` and
`scripts/check_complexity_ratchet.py --path <dir> --base origin/main`.

If this repo has the `patch-coverage` job (see README — it needs your own
`pytest --cov` setup, not every repo has it wired in): new code must be
covered by a test *in the same change*, not added after a gate flags a
gap. That job has no `Tidy-Exempt:` bypass.

If this repo also has the `mutation-ratchet` job (default alongside
`patch-coverage`; mutation testing requires `[tool.mutmut]` source paths — see
README): coverage proving a line ran isn't the same as a test proving it
matters. Write toward killing mutants — exact-value assertions, both sides
of every boundary, every branch tested on its own — see
`templates/tdd-bdd-yagni.snippet.md`'s "Writing tests mutants can't
survive" if this repo uses that companion section. Same no-`Tidy-Exempt:`
rule; a genuinely equivalent mutant gets mutmut's own `# pragma: no
mutate` instead.

Before declaring a Python behavior change complete, apply the mutation-quality
checklist:

1. Identify changed production functions from the diff, not only the files.
2. Select or add focused unit tests and mark them `@pytest.mark.mutation` when
   the repository uses focused mutmut selection.
3. Assert exact outputs, side effects, calls, and errors, not just execution.
4. Cover both sides of changed boundaries and each changed error/empty branch.
5. Run focused mutmut and inspect survivors for the changed functions.
6. Strengthen a survivor with a behavior-specific test, or use `# pragma: no
   mutate` only when the mutation is genuinely equivalent.

The default ratchet passes per changed function at 80% mutation score, or at
20% improvement over that function's first recorded score in
`.mutation-baseline.json`. The first run records the baseline.
