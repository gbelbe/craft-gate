# What craft-gate ships and how

The files a consuming repo receives, and the repo's own tools that produce them.

- [Bootstrap](/distribution/bootstrap.md): Copies the scripts a repo needs and leaves per-project files to the adopter, who pastes the templates into their own CI and `AGENTS.md`.
- [Catalog](/distribution/catalog.md): The source of truth for the craftsmanship catalog.
- [Craftsmanship](/distribution/craftsmanship.md): The generated catalog and procedure that every other piece points back to.
- [Render Catalog](/distribution/render-catalog.md): Generates `CRAFTSMANSHIP.md`, its tables, counts and the README badge, from `catalog.yaml`.
- [Next Version](/distribution/next-version.md): Derives the release version from the commit log.
- [Check Knowledge](/distribution/check-knowledge.md): Keeps the documents in `docs/knowledge/` faithful to the repository: every code anchor exists, every file has an owner, every link resolves, every typed relation is true.
- [Templates](/distribution/templates.md): Fragments a repo pastes into its own CI, `AGENTS.md` and config. They are not complete files.
- [Craft Reviewer](/distribution/craft-reviewer.md): A subagent that reads the diff with no knowledge of how the code was written.
- [Craft Review Skill](/distribution/craft-review-skill.md): Hands the diff to the reviewer subagent and runs the design-review prompts.
- [Tidy First Skill](/distribution/tidy-first-skill.md): The optional Claude Code wrapper around the procedure in the craftsmanship catalog.
