# Design

The full rationale behind craft-gate's mechanical pieces: calibration numbers,
engine choices, what's grandfathered and why. The README covers *what* to run;
these notes cover *why it works the way it does*. Nothing here is required
reading to use the tool. For how the pieces fit together, start with
[docs/architecture.md](docs/architecture.md).

| Topic | Note |
|---|---|
| craftCov: the scan behind Refactor First (detectors, calibration, cache, report) | [docs/design/craftcov.md](docs/design/craftcov.md) |
| The complexity ratchet (cyclomatic, cognitive, invariant return, duplicated literal) | [docs/design/complexity-ratchet.md](docs/design/complexity-ratchet.md) |
| Patch coverage | [docs/design/patch-coverage.md](docs/design/patch-coverage.md) |
| Mutation ratchet | [docs/design/mutation-ratchet.md](docs/design/mutation-ratchet.md) |
| Diff-scoped mutation runs | [docs/design/diff-scoped-mutation-runs.md](docs/design/diff-scoped-mutation-runs.md) |
| Behaviour coverage (Gherkin scenarios cover the changed lines) | [docs/design/behaviour-coverage.md](docs/design/behaviour-coverage.md) |
| Reporting (the PR comment and SARIF export) | [docs/design/reporting.md](docs/design/reporting.md) |
| Design choices worth knowing about, and the sources | [docs/design/design-choices.md](docs/design/design-choices.md) |

Running craft-gate in a repo day to day (updates, review labels, the badge):
[docs/operating.md](docs/operating.md).
