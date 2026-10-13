# Mutation ratchet

Coverage's blind spot: a line can be *executed* by a test that asserts
nothing meaningful about it, and still counts as "covered." Mutation
testing closes that gap by checking whether tests actually *notice* when
behavior changes — [`mutmut`](https://github.com/boxed/mutmut) mutates one
operator/constant/comparison at a time and reruns the suite; a mutant that
doesn't make any test fail *survived*, meaning nothing was really checking
that code. `scripts/check_mutation_ratchet.py` reads a prior `mutmut run`'s
results and fails when a function the diff touches scores below a flat
floor.

```bash
uv sync --extra mutation
uv run mutmut run
uv run python3 scripts/check_mutation_ratchet.py --base origin/main --threshold 80
```

**On by default (`templates/ci-job.yml`'s fifth gate).** Configure
`[tool.mutmut]` with `source_paths` and
`pytest_add_cli_args_test_selection` pointing at focused behavioral tests; the
default local runner and CI job then run mutation testing on every full/PR run.
Mark those tests with `@pytest.mark.mutation`. Name the test files explicitly,
not only `-m mutation`, because mutmut must not collect unrelated test modules
before applying the marker. The normal test job still runs the full suite. The
mutation cache is incremental:
mutmut regenerates and retests changed functions, while
`cache_invalidation_files` plus `on_dependency_change = "rerun"` force a full
rerun when tests or test configuration change. Scheduled and manually
dispatched CI runs delete `mutants/` before running, providing a periodic
fresh campaign. Use the local runner's `--fresh` option for the same behavior.

The ratchet is per changed function, not aggregate: a function at or above
80% passes; a function below 80% must improve by at least 20% over its
recorded score in `.mutation-baseline.json`. A function with no recorded score
has nothing to improve on, so it must reach 80% outright and is refused
otherwise; a refused run writes no baseline, so the low score cannot become its
own starting point on the next push. This keeps legacy code improvable (it has
a baseline) without letting new or never-measured code in at a low score.

**Why a flat floor, not base-vs-head like the complexity ratchet.** That
gate reruns fast, cheap checks (radon, an AST walk) against both refs — a
second run costs nothing meaningful. Mutation testing reruns your entire
test suite once per mutant; doing that against *two* refs on every PR
would make this the slowest thing in CI by a wide margin, for a comparison
whose main value (catching a function that got worse) coverage and
complexity already provide more cheaply. So this checks the current tree
only, against a threshold you set — closer in spirit to patch coverage
than to the complexity ratchet.

**Why touched-functions-only, not the whole diff's total.** Same reasoning
as everywhere else in this document: a repo adopting this gate on day one
likely has plenty of pre-existing code with a mediocre mutation score, and
demanding the whole repo clear a bar immediately would be exactly the kind
of unfunded mandate that gets a gate disabled within a week instead of
respected.

**A real internal-API coupling, disclosed rather than hidden.**
`check_mutation_ratchet.py` maps a mutant key (`pkg.mod.x_foo__mutmut_3`)
back to the function it mutated via
`mutmut.utils.format_utils.orig_function_and_class_names_from_key` — not
mutmut's own per-mutant line-span index (`mutants/<file>.spans`), which a
real end-to-end run against a toy repo confirmed holds lines in the
*generated* mutants file, not the original source, so it can't be
intersected with a `git diff` on the original file. `format_utils` isn't
marked as mutmut's public API (no `__all__`, no mention in its README) —
this is a real coupling to an internal module, verified against an actual
installed 3.8.0 rather than assumed from documentation, and worth
re-verifying on any future mutmut major-version bump. The function's
behavior is simple and unlikely to change silently (it undoes mutmut's own
one-line naming convention), which is why this was judged worth the risk
rather than re-deriving the same parsing from scratch.

**Equivalent mutants get mutmut's own escape hatch**
(`# pragma: no mutate`, the same idea as `# pragma: no cover`), not a
craft-gate mechanism — there was nothing to build here, the tool already
solved it.

**Not meaningfully dogfooded on craft-gate's own CI**, for the same reason
as patch coverage — no pytest suite here to mutate against. Being one of
the default seven jobs means craft-gate's own `ci.yml` *could* carry this
job like any consumer's would, and it would correctly no-op (no
`[tool.mutmut]` here either) rather than fail — but wiring it in just to
exercise the no-op path isn't worth a seventh job that never does
anything, so it's left out of this repo's own workflow the same way
patch-coverage is.

## Using it

The local runner (`scripts/local-craft-gate.sh`) starts mutation testing
automatically when Python files change; pass `--mutation` to force it for an
otherwise non-Python change. Keep `source_paths` or `only_mutate` limited to the
production contracts your focused tests cover, so the results stay actionable
instead of reporting large numbers of untested legacy mutants.

Each changed function is accepted by one of two paths:

- a mutation score of `>= 80%` passes immediately;
- below `80%`, the function must already have a score in
  `.mutation-baseline.json` and improve on it by at least `20%`.

A touched function with **no** recorded baseline has only the first path: it
must reach `80%` outright, or the gate refuses it. Its score is recorded once
the gate passes; a refused run records nothing. There is no repository-wide
aggregate baseline.

Without a `[tool.mutmut]` section in `pyproject.toml` the job is a verified-safe
no-op, so it is fine to leave wired in before you decide to adopt it.
