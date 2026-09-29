## TDD + BDD workflow (mandatory)

This project follows strict TDD with BDD for behaviour specification.

**Before writing any implementation code for a new feature, you MUST:**

1. **Clarify and challenge the request — before any spec or code:**
   - **Rephrase** the request in your own words (different phrasing, same meaning) to confirm you understood it.
   - **Ask for clarification / validation** — 3–5 focused questions on scope, user-facing behaviour, edge cases, and the success criterion.
   - **Apply YAGNI** ("You Aren't Gonna Need It" — Kent Beck, *Extreme Programming Explained*): actively challenge the use case. Question anything speculative or not strictly required to meet the goal, and propose the simplest design that satisfies it. Prefer cutting scope to adding it.
   - Proceed only once the user has validated the (possibly reduced) scope.
2. Write the Gherkin `.feature` file under `tests/features/`
3. List every unit test case — happy path, edge cases, error paths. Write
   each one to catch a *wrong* implementation, not just to execute a
   correct one — see "Writing tests mutants can't survive" below.
4. Show which files will receive them and the function names
5. Wait for explicit user confirmation

**Only after approval:**
- Write the `pytest-bdd` step definitions under `tests/step_defs/`
- Write the unit tests under `tests/unit/`
- Write the implementation

## Writing tests mutants can't survive

A test that runs a line without checking anything specific about the
result "covers" that line without verifying it — the same code with a
`>` flipped to `>=`, a `+` to a `-`, or a condition inverted would still
pass it. (If this repo has the `mutation-ratchet` CI job, that's exactly
what it measures — a surviving mutant in a function you touched.) Write
toward this whether or not the gate is present; it's the difference
between a suite that catches bugs and one that only runs:

- **Assert exact values, not truthiness.** `assert result` or
  `assert result is not None` passes for almost any wrong answer;
  `assert result == 42` doesn't.
- **Assert every field that matters, not just one.** A test that only
  checks `response.status == "ok"` won't notice a mutation to
  `response.count` — check everything the caller actually relies on, not
  just the first convenient field.
- **Test both sides of every boundary.** For `if n > 10`, test `n = 10`
  (the boundary — should be false) *and* `n = 11` (just past it — should
  be true). A test that only tries `n = 1000` can't distinguish `>` from
  `>=`, or `>` from `<`.
- **Test every branch on its own, not just the easiest path.** Each
  `if`/`elif`/`else` needs a test asserting *that branch's* specific
  outcome — one happy-path test leaves every other branch's mutants
  alive.
- **Don't over-mock.** A mock that returns the same fixed value regardless
  of its arguments can't catch a mutation to what your code passes it —
  assert on the call itself (`mock.assert_called_with(...)`), not just
  that some call happened (`mock.assert_called()`).
- **Test the error path deliberately**, not as an incidental side effect
  of another test — a condition that should raise but a mutation silently
  doesn't needs its own test expecting the raise.

This isn't "write more tests" for its own sake — it's the same YAGNI
discipline step 1 already applies, aimed at what each test actually needs
to prove.
