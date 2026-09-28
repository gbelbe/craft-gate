# Contributing

**Adding a heuristic or rule?** See the README's [How to add a new
heuristic / rule](README.md#how-to-add-a-new-heuristic--rule) — the short
version: add an entry to `catalog.yaml`, run
`python3 scripts/render_catalog.py`, open a PR. CI checks the regeneration
for you.

**Everything else** (scripts, templates, workflows): normal PR process.
Since this repo eats its own dog food, your PR needs a `tidy(<type>):`,
`test(characterize):`, or `Tidy-Exempt:` commit somewhere in it — see
`CRAFTSMANSHIP.md` for what that means and why.

`bash scripts/check_tidy_ratchet.sh --base origin/main` locally tells you
whether your branch already satisfies it before you push.
