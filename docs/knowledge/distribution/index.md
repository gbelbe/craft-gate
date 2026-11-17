# What craft-gate ships and how

The files a consuming repo receives, and the repo's own tools that produce them.

- [Bootstrap](bootstrap.md): Copies the scripts a repo needs and leaves per-project files to the adopter, who pastes the templates into their own CI and `AGENTS.md`.
- [Catalog](catalog.md): The source of truth for the craftsmanship catalog.
- [Craftsmanship](craftsmanship.md): The generated catalog and procedure that every other piece points back to.
- [Render Catalog](render-catalog.md): Generates `CRAFTSMANSHIP.md`, its tables, counts and the README badge, from `catalog.yaml`.
- [Next Version](next-version.md): Derives the release version from the commit log.
- [Check Knowledge](check-knowledge.md): Keeps the documents in `docs/knowledge/` faithful to the repository: the frontmatter is valid, every code anchor exists, every file has an owner, every link resolves, every typed relation is true, and no page still carries the stub's placeholder description.
- [Templates](templates.md): Fragments a repo pastes into its own CI, `AGENTS.md` and config. They are not complete files.
- [Craft Reviewer](craft-reviewer.md): A subagent that reads the diff with no knowledge of how the code was written, and checks that the `docs/knowledge/` page of each modified file still tells the truth.
- [Craft Review Skill](craft-review-skill.md): Hands the diff to the reviewer subagent and runs the design-review prompts.
- [Tidy First Skill](tidy-first-skill.md): The optional Claude Code wrapper around the procedure in the craftsmanship catalog.
- [Sync Knowledge](sync-knowledge.md): Writes what the code already says into the bundle: imports and installs relations, and a placeholder page for every file no concept owns.
- [Check Knowledge Touch](check-knowledge-touch.md): Fails (or warns) when a change modifies a file that a page in `docs/knowledge/` describes without touching that page; a `Docs-Exempt:` trailer waives it.
- [Build Site](build-site.md): Writes the source of a browsable site from `docs/knowledge/`, with relation tables, diagrams, usage and scenarios computed from the bundle and the code.
