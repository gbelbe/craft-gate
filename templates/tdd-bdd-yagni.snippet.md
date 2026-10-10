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

## Design the tests before the code

The mutation gate scores each function you touch, on the first push, against
80%. A function with no recorded score has no second chance (there is no
"improve 20% over your first run" path for it), and *touching* a legacy
function with no recorded score makes the whole function yours to cover. So
the design of the tests is where a pushed branch is won or lost — decide it
*before* writing the code, not after the gate refuses it.

1. **Count what has to be killed.** For every function you will add or edit,
   list its mutation points: each comparison, arithmetic operator, boolean
   operator, constant, string literal, default argument, `return` value, and
   each argument passed to a call. Each one is a mutant. A test plan is
   finished when every item on that list has an assertion that would fail if
   that item changed.
2. **Write the cases as a table, one row per mutation point or branch** —
   input, exact expected output — and turn the table into tests (a
   `pytest.mark.parametrize` is the natural shape). A row you cannot fill in
   is a branch you do not understand yet, which is the moment to ask.
3. **Test each function directly.** A whole-file or end-to-end test that
   only checks "it loaded" or "there are 3 rows" can run a function 100% and
   kill none of its mutants — a real case: a promotion helper reached by
   every file-load test scored 0 of 32 until it got its own tests. Keep the
   scenario test for behaviour; add small direct tests for the function.
4. **Make functions small and pure where you can.** The score is per
   function and a large function has many mutants to kill. Splitting a
   branchy function (which the complexity ratchet wants anyway) turns one
   hard target into several easy ones.
5. **Register the tests with the mutation run.** A test file outside
   `pytest_add_cli_args_test_selection`, or without `@pytest.mark.mutation`,
   exists for CI's normal test job but kills nothing in mutmut — the gate
   will report survivors you believe you covered. Add the file to the
   selection and the marker when you create it.
6. **Check before you push, on the function only.** Run mutmut for just the
   functions you changed (`mutmut run "<module>.x_<function>*"`), read the
   survivors, and for each one either add the assertion that kills it or
   decide it is equivalent. Do not wait for CI to find them: a full mutation
   run costs minutes and a failed push costs a round trip.
7. **Equivalent means no test could tell.** `# pragma: no mutate` goes only
   on a mutation that cannot change observable behaviour (a log message, a
   cache key that never collides, an unreachable guard), with a one-line
   comment saying why. If you can write a test that would see the difference,
   the mutant is not equivalent — write the test.
8. **Do not pad.** Duplicate assertions or tests that only call the code to
   raise a number are caught by review, and by the next mutation run. One test
   per surviving mutant, named for the rule it protects.

## Mutation-quality delivery loop

When the mutation-ratchet gate is present, finish each production change with
this loop:

1. Map changed lines to changed functions.
2. Map each function to the smallest focused behavioral test files.
3. Mark those tests with `@pytest.mark.mutation` when the repository uses it.
4. Run mutmut on the configured source/test scope.
5. Read survivors for changed functions and add the missing boundary/error
   assertion.
6. Repeat until the function reaches 80%. (A function that already has a
   recorded score may instead improve on it by 20%; a function with no recorded
   score must reach 80%.)

Do not add duplicate assertions only to increase a number. Prefer one test
that kills a specific survivor and names the business rule it protects.
