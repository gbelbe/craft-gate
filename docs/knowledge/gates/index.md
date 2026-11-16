# Gates

The checks a pull request must pass. Each is a script (or a CI job around a tool) that compares the branch with where it diverged from its base. What they share lives in [Shared tooling](../tooling/index.md).

- [Tidy Ratchet](tidy-ratchet.md): Reads only commit messages: a range needs a `tidy(...)` commit, a `test(characterize):` commit or a `Tidy-Exempt:` trailer. It cannot judge whether the right tidying was picked.
- [Refactor First](refactor-first.md): Requires every touched file's craftCov total to go down (or stay at 0), and that no finding sits on a line the diff added. `Tidy-Exempt:` waives the first, never the second.
- [Complexity Ratchet](complexity-ratchet.md): Holds touched functions to the cyclomatic and cognitive limits. A function the diff reaches that is over the limit must come out lower; a new over-limit function, invariant return or repeated literal always fails.
- [Patch Coverage](patch-coverage.md): A CI job around `diff-cover`: the lines this diff changed must be covered. It has no script of its own and no `Tidy-Exempt:` bypass.
- [Mutation Ratchet](mutation-ratchet.md): Judges the mutants on changed lines: a touched function must reach the kill threshold (80% by default). No `Tidy-Exempt:` bypass.
- [Behaviour Coverage](behaviour-coverage.md): A CI job around pytest-bdd: every changed line must be exercised by a Gherkin scenario, not only by unit tests. It has no script of its own.
- [Architecture Ratchet](architecture-ratchet.md): Makes the list of known violations in `architecture.yaml` shrink: a touched module that is the importer of some must lose at least one.
- [Mutation Run](mutation-run.md): Chooses which mutants to run for a diff.
- [Test Impact](test-impact.md): Maps a diff to the tests it can affect.
- [Render Architecture](render-architecture.md): Turns `architecture.yaml` into import-linter contracts and, through Architecture Docs, into the generated overview. `--check` fails when either is stale.
- [Architecture Docs](architecture-docs.md): Draws the declared layers and the imports grimp reads from the code into `docs/architecture/overview.md`.
