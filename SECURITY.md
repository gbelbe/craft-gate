# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting:
[Report a vulnerability](https://github.com/gbelbe/craft-gate/security/advisories/new)
(the repository's Security tab, "Report a vulnerability").

Include what you found, how to reproduce it (a minimal repository or command is ideal), and
the version (`git describe --tags` in your checkout, or the contents of `.craft-gate-version`).

This is a one-maintainer project. I will acknowledge a report within about a week and aim to
fix a confirmed issue in the next release, but I cannot promise a fixed timeline. I will credit
you in the release notes unless you prefer otherwise.

## Supported versions

Only the latest release receives fixes. craft-gate is on 0.x: a breaking change bumps the minor
version, and fixes are not backported.

## What is in scope

craft-gate's scripts and templates run inside *your* CI and local checkouts, on repository
content you may not fully trust (a pull request from a fork, a branch name, a commit message, a
file path). Things worth reporting:

- command or argument injection through a branch name, file name, commit message or PR field in
  a script (`scripts/*`, `bootstrap.sh`) or a workflow template (`templates/*.yml`);
- a template that asks for broader GitHub token permissions than it needs, or that exposes
  secrets to code from a fork;
- `bootstrap.sh` or the update workflow writing outside the intended files;
- the PR-comment script posting content it should not, or to the wrong place;
- the `craft-reviewer` subagent being made to act on instructions found in the code it reviews
  (it is read-only by design, but a bypass is worth knowing about).

## What is not

- Findings craft-gate reports about *your* code. That is the tool working.
- Vulnerabilities in the tools it wraps (ruff, pylint, vulture, radon, mutmut, diff-cover):
  report those upstream. If craft-gate pins a vulnerable version, that is in scope.
- A gate that can be skipped by a documented mechanism (`Tidy-Exempt:`, a declared opt-out in
  `[tool.craft-gate]`). Those are visible by design.

## Good practice when you adopt it

- Pin the release you install (`git clone --branch vX.Y.Z`) and review the weekly update PR like
  any dependency bump; it never auto-merges.
- Keep the permissions in the CI templates as written (`contents: read`; `pull-requests: write`
  only on the PR-comment job).
- If you add the optional model-based review to CI, treat the diff as untrusted input and its
  output as untrusted text; see `docs/design/reviewer.md`.
