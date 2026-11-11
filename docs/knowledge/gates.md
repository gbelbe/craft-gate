# Gates

The checks a pull request must pass. Each is a script (or a CI job around a tool) that compares the
branch with where it diverged from its base. This document defines the gates; [[GateConfig]] and
[[GitDiff]] in tooling.md are what they share.

::config
// type: shape, colour, size
gate: round-rectangle, #2196F3, 120
tool: rectangle, #4CAF50, 100
concept: diamond, #9C27B0, 90

TidyRatchet: type=gate, path=scripts/check_tidy_ratchet.sh
RefactorFirst: type=gate, path=scripts/check_refactor_first.py
ComplexityRatchet: type=gate, path=scripts/check_complexity_ratchet.py
PatchCoverage: type=concept
MutationRatchet: type=gate, path=scripts/check_mutation_ratchet.py
BehaviourCoverage: type=concept
ArchitectureRatchet: type=gate, path=scripts/check_architecture_ratchet.py
MutationRun: type=tool, path=scripts/mutation_run.py
TestImpact: type=tool, path=scripts/test_impact.py
RenderArchitecture: type=tool, path=scripts/render_architecture.py
ArchitectureDocs: type=tool, path=scripts/architecture_docs.py
::

## Commit and file gates

[[TidyRatchet]] reads only commit messages: a range needs a `tidy(...)` commit, a characterization
test or a `Tidy-Exempt:` trailer. [[RefactorFirst]] requires every touched file's craftCov total to
go down. [[ComplexityRatchet]] holds touched functions to the cyclomatic and cognitive limits.

::rel RefactorFirst -> CraftCov [imports] ::
::rel RefactorFirst -> GateConfig [imports] ::
::rel RefactorFirst -> GitDiff [imports] ::
::rel ComplexityRatchet -> AstFuncs [imports] ::
::rel ComplexityRatchet -> GateConfig [imports] ::
::rel ComplexityRatchet -> GitDiff [imports] ::

## Test gates

[[PatchCoverage]] and [[BehaviourCoverage]] are CI jobs around `diff-cover` and pytest-bdd; they have
no script of their own. [[MutationRatchet]] judges the mutants on changed lines, and [[MutationRun]]
chooses which mutants to run. [[TestImpact]] maps a diff to the tests it can affect.

::rel MutationRatchet -> AstFuncs [imports] ::
::rel MutationRatchet -> GitDiff [imports] ::
::rel MutationRun -> MutationRatchet [imports] ::
::rel MutationRun -> GateTiming [imports] ::
::rel MutationRun -> GitDiff [imports] ::
::rel TestImpact -> GitDiff [imports] ::

## Architecture

The application's own hexagon is declared in `architecture.yaml`. [[RenderArchitecture]] turns it
into import-linter contracts and, through [[ArchitectureDocs]], into the generated overview.
[[ArchitectureRatchet]] makes the list of known violations shrink: a touched module that owns some
must lose one.

::rel RenderArchitecture -> ArchitectureDocs [imports] ::
::rel ArchitectureRatchet -> GateConfig [imports] ::
::rel ArchitectureRatchet -> GitDiff [imports] ::
