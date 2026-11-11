# What craft-gate ships and how

The files a consuming repo receives, and the repo's own tools that produce them.

::config
tool: rectangle, #4CAF50, 100
asset: ellipse, #FF9800, 100
agent: round-rectangle, #E91E63, 110

Bootstrap: type=tool, path=bootstrap.sh
Catalog: type=asset, path=catalog.yaml
Craftsmanship: type=asset, path=CRAFTSMANSHIP.md
RenderCatalog: type=tool, path=tools/render_catalog.py
NextVersion: type=tool, path=tools/next_version.py
CheckKnowledge: type=tool, path=tools/check_knowledge.py
Templates: type=asset, path=templates
CraftReviewer: type=agent, path=agents/craft-reviewer.md
CraftReviewSkill: type=agent, path=skills/craft-review
TidyFirstSkill: type=agent, path=skills/tidy-first
::

[[Bootstrap]] copies the scripts a repo needs and leaves per-project files to the adopter, who
pastes the [[Templates]] into their own CI and AGENTS.md. [[Catalog]] is the source of truth;
[[RenderCatalog]] generates [[Craftsmanship]] from it, and [[NextVersion]] derives the release
version from the commit log. [[CheckKnowledge]] keeps the documents in docs/knowledge/ faithful to
the repository: every anchor exists, every file has an owner, every link resolves, and the `imports`
and `installs` edges are true.

::rel Bootstrap -> GateConfig [installs] ::
::rel Bootstrap -> GitDiff [installs] ::
::rel Bootstrap -> RefactorFirst [installs] ::
::rel Bootstrap -> ComplexityRatchet [installs] ::
::rel Bootstrap -> MutationRatchet [installs] ::
::rel Bootstrap -> ArchitectureRatchet [installs] ::
::rel Bootstrap -> RenderArchitecture [installs] ::
::rel Bootstrap -> CraftCov [installs] ::
::rel Bootstrap -> Catalog [installs] ::
::rel RenderCatalog -> Craftsmanship [writes] ::

The independent review is two parts: the [[CraftReviewSkill]] hands the diff to [[CraftReviewer]],
a subagent that reads the code with no knowledge of how it was written. [[TidyFirstSkill]] is the
optional Claude Code wrapper around the procedure in [[Craftsmanship]].

::rel CraftReviewSkill -> CraftReviewer [calls] ::
::rel CraftReviewSkill -> DesignReview [runs] ::
