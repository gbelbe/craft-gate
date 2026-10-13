# Patch coverage

A fourth gate, and the only one not built on craftCov, radon, or a
craft-gate script at all: [`diff-cover`](https://github.com/Bachmann1234/diff_cover)
against a `pytest --cov` XML report. Everything above checks that code is
*structured* well; nothing above checks that it's *tested* at all — a
brand-new 200-line untested file is invisible to `tidy`, `refactor-first`,
and `complexity` alike, as long as no individual function happens to cross
a threshold.

**Why patch coverage, not a whole-repo floor.** A whole-repo percentage
(`coverage report --fail-under 80`) is the weaker of the two shapes: it
measures the *average*, so a well-tested old codebase has enough slack to
absorb an entirely untested new module and still clear the bar. Patch
coverage measures only the lines the diff actually changed — there's no
slack to hide behind, and no way for a genuinely untested addition to pass
just because the rest of the repo carries it.

```bash
uv run pytest --cov=<your_package> --cov-report=xml
uv run diff-cover coverage.xml --compare-branch origin/main --fail-under 90
```

**Ported from kai-ster as-is, not redesigned.** Unlike the complexity
ratchet, this wasn't rewritten into a craft-gate-owned script — `diff-cover`
already does exactly this job, well, as a maintained third-party tool.
craft-gate's contribution is the wiring (`templates/ci-job.yml`'s
`patch-coverage` job) and the threshold-as-starting-point framing, not new
code.

**No `Tidy-Exempt:` bypass, deliberately.** Every other gate this repo
ships shares one exemption mechanism; this one doesn't, because it's
porting kai-ster's actual, currently-running behavior faithfully — that
gate has never had a bypass there either, and `diff-cover` itself has no
hook to add one to short of wrapping it in a craft-gate-owned script, which
would reintroduce the "why does this gate need its own script" question
this section just answered. A genuine exception (generated code, a
vendored file) belongs in coverage configuration itself — an `omit` entry
— not a commit trailer.

**Not dogfooded on craft-gate's own CI.** This repo's tests run under
pytest (`uv run pytest tests`), but its CI doesn't produce a `coverage.xml`
or run diff-cover/mutmut against them: those two gates are meant for a
consuming repo's own Python package, and wiring them here would mean
choosing which of the scripts are "the package" just to dogfood a gate.

**The standalone job is a default, not a mandate — embed the step when a
coverage-producing job already exists.** Discovered by actually wiring
this into three real repos, not assumed: kai-ster's own `diff-cover`
predates craft-gate and has always run this way — a single step appended
to the same job that already runs `pytest --cov`, once per CI pass, never
a second standalone test run. semanticlint had its own coverage-producing
`quality` job already; the diff-cover step went there, no new job added.
semanticdiff's local `scripts/ci.sh` had a matrix loop with no existing
`--cov-report=xml` at all, so the standalone-shaped addition (one
`diff-cover` call after the loop, reusing whichever Python version's
`coverage.xml` ran last, not per-version) was actually correct there —
the *job* per se still isn't duplicated, since `ci.sh` itself is already
looped by the workflow. The pattern held three-for-three: never assume a
second job is necessary, check for an existing coverage-producing step
first. A real portability bug surfaced doing this by hand, worth noting
since it's the kind of thing that only shows up by actually running the
script: `${arr[-1]}` for "last item" needs bash 4.3+, and macOS ships 3.2
as `/usr/bin/bash` — silently breaks any contributor testing the local
gate on a Mac who hasn't installed a newer bash. Fixed by tracking the
last value in a plain variable instead of relying on negative indexing.

## On by default, opted out in writing

Patch coverage, the mutation ratchet and behaviour coverage used to be jobs a repo
adopted by pasting them in; a repo that never did had no test gate and nothing said
so. They now run unless `pyproject.toml` declares otherwise, and a gate that is on but
has nothing to check (no pytest suite) fails instead of passing. Opting out needs a
`reason`, which the PR comment shows. The rule, the table of states and an example
are in CRAFTSMANSHIP.md's "Test gates"; `scripts/gate_config.py` implements it.
