# Behaviour coverage

The question patch coverage asks of *all* tests, asked of the Gherkin scenarios
alone: is every line this diff changed exercised by a behaviour test?

## Why a separate gate

A line can be 100% covered by unit tests while no scenario ever describes what it is
for. Teams that specify behaviour in Gherkin want a change to the code to show up as
a change, or at least a hit, in the scenarios. Patch coverage cannot tell the two
apart because it merges every test into one report.

## How it works

1. `scripts/gate_config.py bdd` decides whether the gate applies (see
   CRAFTSMANSHIP.md's "Test gates").
2. `pytest <paths> --cov --cov-report=xml:coverage-bdd.xml` runs only the behaviour
   tests (`paths`, default `tests/features`).
3. `diff-cover coverage-bdd.xml --compare-branch origin/<base> --fail-under <threshold>`
   fails when too few of the changed lines were hit. The default threshold is 80,
   lower than patch coverage's 90: a scenario exercises a path end to end and rarely
   reaches every guard clause.

Nothing here is Gherkin-specific except the default `paths`: it measures whatever
the behaviour tests under `paths` execute, so `pytest-bdd` scenarios, or behave or
Cucumber suites that run under pytest, all work. It needs no craft-gate script of
its own beyond the configuration reader, which is the point; the mechanism is the
one patch coverage already uses.

## What it does not do

- **Order.** It cannot tell whether a scenario was written before the code. A
  diff has no memory of which came first, and a squash merge erases the commit order.
- **Quality of a scenario.** Coverage says a scenario ran the line, not that it
  asserts the right thing. The mutation ratchet is the check for that, and it runs
  against the full suite, scenarios included.
- **Orphaned steps.** Not a separate check: a step with no definition raises when the
  scenario runs, so the behaviour tests fail before coverage is measured.

## Opting out

On by default, like patch coverage and mutation. A repo with no scenarios yet either
adds some or declares it off:

```toml
[tool.craft-gate.bdd]
enabled = false
reason = "specified in unit tests; revisit when we adopt pytest-bdd"
```

The reason is required and appears in the PR comment. With the gate on and no
`.feature` files under `paths`, the job fails and says what to add.
