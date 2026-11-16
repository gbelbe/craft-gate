# craft-gate knowledge

Start here before you propose or design a change. Each page says what one file or folder is for, which files it stands for (`code`), and its typed relations to other pages (`imports`, `installs`, `writes`, `calls`, `runs`), which are the things a change to it can break.

- [Gates](gates/index.md): the checks a pull request must pass.
- [Shared tooling](tooling/index.md): what the gates are built from.
- [What craft-gate ships and how](distribution/index.md): the files a consuming repo receives, and the tools that produce them.
