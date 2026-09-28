## Tidy First & craftsmanship (mandatory before every feature/fix commit)

Before writing a feature or fix, check the file(s)/function(s)/class(es) it
touches against the catalog in `CRAFTSMANSHIP.md` (Kent Beck's *Tidy First?*,
Fowler's *Refactoring* smells, *Clean Code*, and Feathers' legacy-code
method). If a tidying applies, do it alone, verify the suite is unchanged,
and commit it separately, naming the source:

```
tidy(<type>): <what and where>

Tidy-Type: <type>
Tidy-Source: <author, book>
```

Only then commit the feature/fix. If nothing applies, don't invent one —
commit with a `Tidy-Exempt: <reason>` trailer instead.

The catalog is also a checklist for **new** code, not just a pre-touch
ritual: Beck's four rules of simple design (pass the tests, reveal intention,
no duplication, fewest elements) and Clean Code's function-size/SOLID
principles are the acceptance bar for anything written from scratch — there's
nothing to "tidy" in code that doesn't exist yet, but there's everything to
get right the first time.

Touching code with no tests? It's legacy by Feathers' definition regardless
of age — write a `test(characterize):` commit pinning its current behavior
first, *then* tidy under that safety net. See `CRAFTSMANSHIP.md`'s "Working
with legacy code."

The `tidy-ratchet` check (pre-push hook / CI, `scripts/check_tidy_ratchet.sh`)
enforces the discipline — it fails a push/PR with no `tidy(...)` commit, no
`test(characterize):` commit, and no `Tidy-Exempt:` trailer in range. It's a
text check on commit messages only, so it costs milliseconds; it cannot judge
whether the right tidying was picked.
