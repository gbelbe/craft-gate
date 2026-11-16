# Shared tooling

What the gates in [Gates](../gates/index.md) are built from. Nothing here judges a pull request by itself.

- [Gate Config](gate-config.md): Reads `craft-gate.toml` (or `[tool.craft-gate]`) and says which gate runs and what a `Tidy-Exempt:` trailer waives.
- [Git Diff](git-diff.md): Answers "which lines did this branch change" for every gate.
- [Ast Funcs](ast-funcs.md): Maps changed lines to the functions that contain them.
- [Gate Timing](gate-timing.md): Records how long the jobs take.
- [Ci History](ci-history.md): Records how long the jobs take over time.
- [Craft Cov](craft-cov.md): Scans for the eight detectable craftsmanship heuristics (`--list-detectors`).
- [Craft Cov Pr Comment](craft-cov-pr-comment.md): Turns the gates' results into the sticky pull-request comment, with design-review prompts and the values that were loosened.
- [Design Review](design-review.md): Prints design prompts about the diff for the author to answer before the independent review.
- [Config Loosening](config-loosening.md): Finds the values in `craft-gate.toml` a change makes looser, so a person decides.
- [Report Tidy History](report-tidy-history.md): Summarises the tidy trailers in a commit range.
- [Local Runner](local-runner.md): Runs the same gates before a push.
- [Gate Requirements](gate-requirements.md): Pins every tool the gates call, so a consuming repo needs no extras of its own.
