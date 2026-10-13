# craftCov

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
- **`dupes`** — not a subprocess, `scripts/craftcov_core/dupes.py`'s own code:
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
