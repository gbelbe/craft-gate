# The complexity ratchet

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
base ref) read for its changed-line ranges, not the worktree. A file git sees as
moved (`git diff -M`) is **followed**: what it carries is compared with what it was at the old
path, and a move that changes nothing touches nothing, so a legacy function is grandfathered
exactly as it was before the move. Without that, moving a few hundred test files into folders read
as writing them from scratch (nearly two thousand repeated literals at once). Only the file that
git can pair with an old one is followed: a copy that leaves the original in place is new code.

**Ported from a real, load-bearing script, not written from scratch for
this repo.** Originated in a project that hit SonarQube's cognitive-
complexity and duplicated-literal rules often enough to want them caught
locally, before a push. The two smells beyond plain cyclomatic complexity
are checked against the *reference implementation* (the
`cognitive-complexity` package) rather than a re-derivation, because the
point is to agree with SonarQube's own server, not approximate it.
