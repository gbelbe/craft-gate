# Design

The full rationale behind craft-gate's mechanical pieces — calibration
numbers, engine choices, what's grandfathered and why. The README covers
*what* to run; this covers *why it works the way it does*. Nothing here is
required reading to use the tool.

## craftCov

A coverage-report-style scan — like `coverage.py`'s report, but for the
catalog's mechanically-checkable heuristics instead of executed lines.

```bash
uv run python3 scripts/craftcov.py                  # scan, text report
uv run python3 scripts/craftcov.py --format json     # machine-readable
uv run python3 scripts/craftcov.py --verbose         # + every finding, file:line
uv run python3 scripts/craftcov.py --list-detectors  # which heuristics are detectable, and how
uv run python3 scripts/craftcov.py --no-diff         # skip the "changes since last run" section
uv run python3 scripts/craftcov.py --file path/to/f.py --class SomeClass  # scope the report (Refactor First)
```

```
craftCov — craftsmanship heuristic scan
Scanned 669 files (0 changed, 669 from cache) in 1.45s
Duplicate-code pass: 1.10s (always full-corpus — see below)

Changes since last run (2026-09-21T09:03:11Z)
  CG002   dead-code                                1685 -> 1699  (+14)
  CG024   consolidate-duplicate-conditional          432 -> 428   (-4)
  CG012   extract-helper                                0 -> 1    (+1) (NEW)
          TOTAL                                     2563 -> 2579  (+16)

By heuristic
CODE    ID                                      COUNT  SOURCE
CG002   dead-code                                1685  Kent Beck, Tidy First? (2023)
CG024   consolidate-duplicate-conditional         432  Martin Fowler (with Kent Beck), Refactoring, 2nd ed. (2018)
...
        TOTAL                                    2579

8/35 heuristics have an automatic detector (22%) — the rest need the
procedure in CRAFTSMANSHIP.md (ask the developer), not a scan.
```

craftCov's own accounting stops there — it has no awareness of
`scripts/check_complexity_ratchet.py`, a fully separate script. Four more
catalog entries (CG032-CG035: cyclomatic/cognitive complexity, invariant
return, duplicated literal) are mechanically enforced by that ratchet
instead — see **The complexity ratchet** below, not craftCov's own report.

**Honest about its limits, on purpose.** Real semantic smell detection
(Feature Envy, Data Clumps *precisely* — not just "too many params," the
*same group* repeating — Message Chains, Primitive Obsession, Refused
Bequest) needs judgment a regex or AST check can't safely fake, or tooling
that doesn't exist for Python (checked against the academic
design-smell-detection literature, which is Java/C#/C++-tooling-only). So
craftCov doesn't try to fake any of them. It reuses three engines, and
ports one technique, for the entries where each is a decent proxy — 8 of 35:

- [`ruff`](https://astral.sh/ruff) (Rust, a dependency your project almost
  certainly already has, own fast internal cache) — `guard-clauses`,
  `dead-code`, `explaining-constant`, `extract-helper`,
  `introduce-parameter-object`, `replace-conditional-with-polymorphism`.
- `pylint`, scoped to exactly `R0902`/`R0904` (not a full pylint run) —
  `extract-class` / God Class. ruff hasn't ported these two yet (one's
  preview-only there, the other doesn't exist in ruff at all — checked
  against ruff 0.16.9); upstream pylint's originals are stable.
- `vulture` — a second, higher-recall pass for `dead-code` alongside ruff's
  F401/F811/F841, catching unused functions/classes ruff's own-file-scoped
  checks can't see. Verified on a real, framework-heavy codebase while
  building this (kai-ster: pytest-bdd + Textual): vulture's own confidence
  scores cluster hard into unused-*variables* at 100% (redundant with
  ruff's F841) and unused functions/classes/methods at 60% (vulture's own
  "fairly sure but could be wrong" floor — decorator-registered pytest-bdd
  steps and Textual's `on_*` handlers score exactly here without being
  genuinely dead). That 60% tier is also where all of vulture's unique
  value lives, so craftCov reports it unfiltered by default rather than
  quietly discarding it — tune with `--vulture-min-confidence N` once
  you've triaged a first pass and know your codebase's noise floor (its
  effect on the earlier example: `dead-code` 1685 → 36 at `N=80`).
- **`dupes`** — not a subprocess, `scripts/craftcov.py`'s own code:
  `consolidate-duplicate-conditional`, via a from-scratch port of the
  rolling-hash line-window matching technique both PMD CPD (Karp-Rabin
  string matching over a token stream — verified against PMD's own docs)
  and pylint's own `R0801` checker (the same technique, one level coarser —
  verified against pylint's actual source) use internally. Ported instead
  of subprocessing pylint's checker because pylint's own CLI JSON only
  gives ONE of a duplicate pair's two locations in structured form (the
  other is free text embedded in the message), and its internal API
  (`_compute_sims`) is private and churns across versions. Costs nothing
  new to install — stdlib only. Exact-match, like both reference tools'
  default mode (no identifier/literal normalization — PMD's fuzzy Type-2
  matching needs a real per-language tokenizer to do properly, out of
  scope here); doesn't special-case docstrings the way pylint's checker
  does either, so a duplicated docstring block is still reported.

Every other entry shows `0` findings not because your code is clean by that
measure, but because craftCov has nothing to say about it — see
`--list-detectors` for exactly which is which, and `catalog.yaml`'s
`detectors` field (a list — an entry can name more than one tool, as
`dead-code` does) to add more as a rule or tool that's a genuinely good
proxy shows up for something currently undetected.

**Calibrated against the real PMD CPD, not guessed.** The first version of
this shipped with `min_lines=4` (pylint's own default) and reported 8778
`consolidate-duplicate-conditional` findings on a real ~670-file codebase —
84% of them were the minimum 4-5 line matches, and inspecting a sample
turned up things like a bare
`subprocess.run(..., capture_output=True, text=True, check=False)` call
flagged as "duplicated" against three unrelated files: real, but not
useful signal. Rather than guess a better number, installed PMD 7.9.0 and
ran its actual CPD against the identical file set at a few
`--minimum-tokens` settings. Result: both tools **agree on the real
duplicates**, and PMD's own `--minimum-tokens=50` (common in its own
examples; PMD ships no built-in default, unlike pylint) does *not* flag
the bare `subprocess.run(...)` snippet standalone, only as part of a
larger, real duplicate. Measuring tokens/line directly on that codebase
(~5.2) and testing several `min_lines` values against PMD's cluster counts,
`min_lines=8` landed closest in the same order of magnitude as PMD@50 —
that's the new default (`catalog.yaml`'s comment on this entry has the
full numbers). 8778 → 432, a 20x drop, from fixing the threshold alone —
the algorithm itself needed no changes.

**Only code this repo wrote, not the libraries it imports.** `import`/`from
... import` lines (AST-located, so a multi-line parenthesized import has
every line excluded, not just the first) are stripped before the
duplicate-window scan even starts — two files that both do `import os`,
`import sys`, `from pathlib import Path` the same way share a dependency,
not duplicated logic. Measured on the same 669-file set: 432 → 384, 48 of
the post-PMD-calibration findings (~11%) were import-block matches, not
real duplication.

**Findings, aggregated four ways**: by heuristic (code, count, source — so
you can see *which book* your codebase disagrees with most), by file, by
enclosing class (via a lightweight `ast` walk — module-level findings are
excluded from this view rather than miscounted against "no class"), and by
"library" (the top-level directory a file lives under).

**Caching, per-file tools only.** ruff's own `.ruff_cache/` already skips
re-linting unchanged files internally (pylint and vulture have no cache of
their own). On top of that, craftCov keeps `.craftcov_cache.json`, keyed by
each file's content hash (not mtime) and by a path *relative* to the scan
root. Its cache also stores the class/function attribution none of the
three subprocess tools track on their own, so a warm re-run skips
re-parsing ASTs too, not just re-linting. A cold run over ~670 files
across ruff/pylint/vulture took 9.1s; warm, 1.45s. One caveat: the cache
doesn't know about scan *parameters* — changing `--vulture-min-confidence`
between runs needs `--no-cache` to actually take effect.

**`dupes` doesn't participate in that cache, on purpose.** A duplicate only
means anything relative to its *other* copy — if file B changes, file A's
cached "duplicate of B" finding could go stale even though A itself didn't
change. So the duplicate-code pass always re-scans every file, every run.
In practice this is cheap enough not to matter: ~1.4s over ~670 files /
~130k lines, whether cold or warm.

**Changes since last run.** Every run saves its by-heuristic totals to
`.craftcov_last_report.json` (gitignored — a local run-to-run diary, not a
checked-in artifact) and, unless `--no-diff` is passed, diffs the new
totals against that file before printing the rest of the report. The
first-ever run says so explicitly rather than printing a misleading
all-zero diff. A heuristic whose old count was 0 is tagged `(NEW)`; one
whose new count is 0 is tagged `(RESOLVED)`. `--no-diff` skips *printing*
the section (the snapshot still updates, so a later run stays accurate).
`--format json` carries the same information under a `"diff"` key. Point
`--snapshot-file` at a different path to keep separate histories (e.g. one
per branch).

**Not a hard whole-repo gate.** A full `craftcov.py` run doesn't fail CI —
it's a report, meant for a human to decide what's worth a `tidy(...)`
commit, the same "ask the developer, don't decide silently" principle as
the rest of the catalog. What **does** gate CI is Refactor First (see
`CRAFTSMANSHIP.md`) — not an absolute threshold, a relative one.

**Testing the detectors: `tests/fixtures/`.** One small, hand-authored file
per detectable heuristic, plus `clean.py`, a negative control genuinely
free of all eight. `tests/test_fixtures.py` runs `craftcov.py` against that
directory and asserts each detector fired on its own fixture; CI runs it on
every push. Checks are presence-based, not exact-match — real code
routinely trips more than one heuristic at once. Added after the
`min_lines=4` miscalibration above was found — the two are complementary:
this fixture corpus catches "did a detector regress," the PMD-style
comparison is what catches "is the threshold reasonable" in the first
place.

## The complexity ratchet

A second diff-aware gate, fully independent of craftCov (different script,
different catalog entries, its own dependency extra) — for the 4 catalog
entries it covers (CG032-CG035), a touched function/literal already over
threshold must come out *lower* than it went in, stricter than Refactor
First's "must not get worse": leaving it exactly as bad as before doesn't
pass just because it didn't get worse.

```bash
uv run python3 scripts/check_complexity_ratchet.py --base origin/main
```

```
Complexity ratchet: 2 violation(s):
  - ster/tui/query_screen.py::QueryScreen._render_results: cyclomatic complexity 12 -> 18 (> 15) — refactor to reduce cyclomatic complexity instead of adding to it
  - ster/tui/query_screen.py::QueryScreen._render_results: new function with cognitive complexity 16 (> 15) — keep new functions at or below 15
```

**Four checks, one mechanism:**

- **Cyclomatic complexity** (McCabe, 1976) and **cognitive complexity**
  (SonarQube S3776) — same threshold (15), reported separately because
  they measure different things: cyclomatic counts independent paths,
  cognitive charges for *nesting*, so a function radon calls simple can
  still fail cognitive.
- **Invariant return** (S3516) — every `return` in a function hands back
  the same never-rebound name; two returns of a mutated list read as two
  outcomes but are one.
- **Duplicated string literal** (S1192) — the same literal (5+ chars)
  repeated 3+ times in one file (not per-function), excluding docstrings.

**Grandfathered, not retroactive.** A function already over threshold that
the diff never reaches isn't a violation — touch detection is a real
`git diff -U0` (see `_changed_lines`/`_touched_names`), matched against
each function's line range, not just "did the complexity number change."
A function the diff *does* reach, already over threshold, must decrease —
unchanged is a violation, worse is a violation, only lower passes (it
doesn't have to reach the threshold in one PR). The point is forward
pressure on debt you're already touching, not a demand to go looking for
complexity to fix in code nobody's touching.

**Diff-aware via a throwaway `git worktree`**, same technique as
`check_refactor_first.py`: one worktree checkout of the base ref computes
all four metrics at once, compared against the current tree. Touch
detection is a second, separate `git diff` (unified-zero, against the same
base ref) read for its changed-line ranges, not the worktree. A file move
counts as a change to everything it carries — there's no rename-awareness.

**Ported from a real, load-bearing script, not written from scratch for
this repo.** Originated in a project that hit SonarQube's cognitive-
complexity and duplicated-literal rules often enough to want them caught
locally, before a push. The two smells beyond plain cyclomatic complexity
are checked against the *reference implementation* (the
`cognitive-complexity` package) rather than a re-derivation, because the
point is to agree with SonarQube's own server, not approximate it.

## Patch coverage

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

**Not dogfooded on craft-gate's own CI.** This repo's own tests
(`tests/test_fixtures.py`) are a deliberate non-pytest script, not a suite
with coverage tracking (see this repo's own README's Requirements — no
test-framework dependency is a stated design choice), so there's no
coverage.xml here to gate on. Wiring this into craft-gate's own `ci.yml`
would mean building test infrastructure this repo has specifically chosen
not to carry, just to dogfood a gate meant for consumers' own Python
packages.

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

## Mutation ratchet

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

## Reporting

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

## Design choices worth knowing about

- **The ratchet checks discipline, not correctness.** It can tell you a
  `tidy(...)` commit exists; it cannot tell you the tidying was the right
  one, or that it actually preserved behavior. That's still a human (or
  agent-plus-human) judgment call — the tool's job is only to make sure the
  judgment call was *recorded*, not skipped under pressure.
- **`Tidy-Exempt:` is load-bearing, not a loophole to remove.** Without an
  honest way to say "nothing applied here," the ratchet would pressure
  people into manufacturing fake tidyings just to pass a gate — a textbook
  Goodhart's Law failure. The trade-off is that the exemption rate needs
  periodic review (`report_tidy_history.sh`) rather than blind trust.
- **Legacy code gets a named first step, not an exception.** Feathers'
  definition — *legacy code is code without tests* — means "tidy first"
  doesn't work on it as-is; there's nothing to confirm unchanged. A
  `test(characterize):` commit is the prerequisite move, and it satisfies
  the ratchet exactly like a tidying does, because it *is* the tidying-first
  move for untested code.
- **Any diff-aware skip heuristic you build on top of this should follow
  the same rule as everything else here: widen what it trusts from
  evidence, never a hunch, and keep an unconditional full run on a
  schedule as backstop.** A heuristic that quietly gets more permissive
  over time is the same failure mode as a rubber-stamped exemption — just
  automated.
- **The three gates skip bot-authored PRs** (`if: ... &&
  !endsWith(github.actor, '[bot]')` — see `templates/ci-job.yml`). This is
  a narrower exemption than it looks: it only fires for an *automated PR
  author* like dependabot or renovate, which can't write a `tidy(<type>)`
  commit or a `Tidy-Exempt:` trailer and whose diffs (dependency-file
  bumps) rarely have a craftsmanship heuristic to apply anyway. It does
  not exempt a human pushing to their own branch, and a skipped job still
  reports a passing check, so it doesn't create a required-check gap for
  anyone else's PR.

## Further reading (the actual sources)

- Kent Beck, *Tidy First?* (2023)
- Martin Fowler (with Kent Beck), *Refactoring*, 2nd ed. (2018)
- Robert C. Martin, *Clean Code* (2008) and *Agile Software Development,
  Principles, Patterns, and Practices* (2002)
- Kent Beck, *Extreme Programming Explained* (1999/2004)
- Michael Feathers, *Working Effectively with Legacy Code* (2004)
- Sandi Metz's rules (widely cited, originally a conference-talk heuristic)
- Thomas J. McCabe, "A Complexity Measure", IEEE TSE (1976)
- G. Ann Campbell, "Cognitive Complexity", SonarSource whitepaper (2018)
