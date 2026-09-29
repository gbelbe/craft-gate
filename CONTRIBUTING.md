# Contributing

## Adding a heuristic or rule

For the common case — a named smell with a fix (the `tidying` and
`smell-fix` tables), which is most of the catalog — this is a one-file edit.

**1. Add an entry to `catalog.yaml`:**

```yaml
- id: your-fix-name          # kebab-case, names the FIX, not the smell —
                              # this becomes the tidy(your-fix-name): commit type
  name: The Smell's Name     # what a reader recognizes ("Feature Envy")
  kind: smell-fix            # tidying | smell-fix | principle | workflow — see below
  source: "Author, Title (year)"   # exact citation — this is what makes a
                                    # tidy(...) commit a checkable claim later
  smell: What you'd notice that makes you reach for this
  action: What the fix actually does
```

**2. Regenerate `CRAFTSMANSHIP.md` from it:**

```bash
python3 scripts/render_catalog.py
```

This rewrites the two generated tables (between the `<!-- BEGIN GENERATED -->`
/ `<!-- END GENERATED -->` markers) to match `catalog.yaml`, and touches
nothing else in the file — the procedure, the principles, the legacy-code
workflow all stay hand-written. CI's `validate` job runs the same script
with `--check` and fails the PR if you edited `catalog.yaml` and forgot to
regenerate, so this can't silently drift.

**3. Open a PR.** That's it for the common case — two files change
(`catalog.yaml` and the regenerated `CRAFTSMANSHIP.md`), CI either passes or
tells you exactly what to run.

**The `kind` field** decides which section an entry lands in and whether
it's auto-generated:

| `kind` | What it means | Generated? |
|---|---|---|
| `tidying` | Structural-only move (Beck's *Tidy First?* sense) — a commit's tests must be identical before/after | Yes — table |
| `smell-fix` | A named design smell and its standard fix (Fowler's sense) — broader than structural-only | Yes — table |
| `principle` | A new-code design rule, not a retrospective commit type (Clean Code, XP's simple design, Metz) | No — prose |
| `workflow` | A named procedure, not a single fix (Feathers' characterization-test method) | No — prose |

`principle` and `workflow` entries don't reduce to one table row without
losing the nuance that makes them useful — adding one means writing a short
prose section in `CRAFTSMANSHIP.md` by hand (near the existing "New-code
principles" or "Working with legacy code" sections) *and* adding the
`catalog.yaml` entry, so the structured record still exists for tooling that
wants it. `render_catalog.py` won't touch or validate that prose — it only
owns the two tables.

**Naming the `id`:** name it after the *fix*, not the smell — `extract-class`
reads correctly in a commit (`tidy(extract-class): ...`) for "Large Class",
"God Class," and "Divergent Change" alike, since they share one fix. Check
whether an existing `id` already covers your fix before adding a new one; a
new smell that shares a known remedy is a one-line addition to an existing
row's `name` field, not a new entry.

**A `detectors` field means specifically "craftcov.py's own scan covers
this"** — only add one if you're wiring up ruff/pylint/vulture/dupes (see
[DESIGN.md](DESIGN.md#craftcov) for the schema). A smell with a *different*
mechanical check — your own script, not craftcov.py's four engines — gets
no `detectors` field at all; document the check itself in its own
CRAFTSMANSHIP.md section instead, the way `check_complexity_ratchet.py`
has "The complexity ratchet." Leaving `detectors` off doesn't mean
"unchecked," just "not craftCov's job" — `--list-detectors` will call it
"needs judgment" regardless, since that's genuinely true from craftCov's
own point of view.

## Everything else

Scripts, templates, workflows: normal PR process. Since this repo eats its
own dog food, your PR needs a `tidy(<type>):`, `test(characterize):`, or
`Tidy-Exempt:` commit somewhere in it — see `CRAFTSMANSHIP.md` for what
that means and why.

```bash
bash scripts/check_tidy_ratchet.sh --base origin/main
```

tells you locally whether your branch already satisfies it before you push.
