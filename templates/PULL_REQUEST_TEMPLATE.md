<!-- craft-gate: the gates check what can be measured. This is for what they cannot. -->

## What and why

<!-- One paragraph. The "why" is what a reviewer can't get from the diff. -->

## Reviewer checklist: the judgement calls no gate makes

Tick what you checked, or say why it does not apply. The "Design review (advisory)" comment
lists functions worth a second look; this list is the rest.

- [ ] **One thing.** Each new or changed function does one thing, and you can say what in a
      sentence without "and".
- [ ] **Names.** Names say what a thing is or does. A reader does not need the body to guess.
- [ ] **Commands and queries.** Nothing that reads like a query (`get_`, `is_`, `find_`) also
      changes state.
- [ ] **Responsibility.** A new class has one reason to change; an external library sits
      behind a thin adapter, not spread through the code.
- [ ] **Tests say the behaviour.** A test fails if the behaviour breaks, not only if the code
      is deleted (exact values, both sides of each boundary).
- [ ] **Nothing speculative.** No parameter, hook or option without a caller today (YAGNI).

<!-- Tidy-Exempt: used? Give the reason in the commit trailer. New code is still checked. -->
