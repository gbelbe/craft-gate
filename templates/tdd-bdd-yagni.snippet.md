## TDD + BDD workflow (mandatory)

This project follows strict TDD with BDD for behaviour specification.

**Before writing any implementation code for a new feature, you MUST:**

1. **Clarify and challenge the request — before any spec or code:**
   - **Rephrase** the request in your own words (different phrasing, same meaning) to confirm you understood it.
   - **Ask for clarification / validation** — 3–5 focused questions on scope, user-facing behaviour, edge cases, and the success criterion.
   - **Apply YAGNI** ("You Aren't Gonna Need It" — Kent Beck, *Extreme Programming Explained*): actively challenge the use case. Question anything speculative or not strictly required to meet the goal, and propose the simplest design that satisfies it. Prefer cutting scope to adding it.
   - Proceed only once the user has validated the (possibly reduced) scope.
2. Write the Gherkin `.feature` file under `tests/features/`
3. List every unit test case — happy path, edge cases, error paths
4. Show which files will receive them and the function names
5. Wait for explicit user confirmation

**Only after approval:**
- Write the `pytest-bdd` step definitions under `tests/step_defs/`
- Write the unit tests under `tests/unit/`
- Write the implementation
