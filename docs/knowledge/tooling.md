# Shared tooling

What the gates in gates.md are built from. Nothing here judges a pull request by itself.

::config
gate: round-rectangle, #2196F3, 120
tool: rectangle, #4CAF50, 100
asset: ellipse, #FF9800, 100

GateConfig: type=tool, path=scripts/gate_config.py
GitDiff: type=tool, path=scripts/gitdiff.py
AstFuncs: type=tool, path=scripts/astfuncs.py
GateTiming: type=tool, path=scripts/gate_timing.py
CiHistory: type=tool, path=scripts/ci_history.py
CraftCov: type=tool, path=scripts/craftcov.py;scripts/craftcov_core
CraftCovPrComment: type=tool, path=scripts/craftcov_pr_comment.py
DesignReview: type=tool, path=scripts/design_review.py
ConfigLoosening: type=tool, path=scripts/config_loosening.py
ReportTidyHistory: type=tool, path=scripts/report_tidy_history.sh
LocalRunner: type=tool, path=scripts/local-craft-gate.sh
GateRequirements: type=asset, path=scripts/gate-requirements.txt
::

[[GateConfig]] reads `craft-gate.toml` (or `[tool.craft-gate]`) and says which gate runs and what a
`Tidy-Exempt:` trailer waives. [[GitDiff]] answers "which lines did this branch change" for every
gate. [[AstFuncs]] maps changed lines to the functions that contain them.

[[CraftCov]] scans for the eight detectable heuristics. [[CraftCovPrComment]] turns the gates'
results into the sticky pull-request comment, with [[DesignReview]] prompts and the values
[[ConfigLoosening]] found loosened.

::rel CraftCovPrComment -> ConfigLoosening [imports] ::
::rel CraftCovPrComment -> CraftCov [imports] ::
::rel CraftCovPrComment -> DesignReview [imports] ::
::rel CraftCovPrComment -> GateConfig [imports] ::
::rel CraftCovPrComment -> GitDiff [imports] ::
::rel DesignReview -> AstFuncs [imports] ::
::rel DesignReview -> GateConfig [imports] ::
::rel DesignReview -> GitDiff [imports] ::
::rel ConfigLoosening -> GateConfig [imports] ::
::rel ConfigLoosening -> GitDiff [imports] ::

[[LocalRunner]] runs the same gates before a push. [[GateRequirements]] pins every tool the gates
call, so a consuming repo needs no extras of its own. [[CiHistory]] and [[GateTiming]] record how
long the jobs take; [[ReportTidyHistory]] summarises the tidy trailers in a range.
