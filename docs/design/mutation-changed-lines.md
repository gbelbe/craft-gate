# Mutation runs on changed lines

The mutation ratchet asks one question of a pull request: do the tests covering the code you touched kill
at least `[mutation] threshold` percent of the mutants on it? Answering it needs mutmut to run, and mutmut,
left alone, mutates a whole project and reruns the tests once per mutant: minutes on a small repo, hours on
a large one. This note is how `scripts/mutation_run.py` keeps the run proportional to the change, with
nothing stored from one run to the next.

## The design

A run starts from an empty `mutants/` and does four things:

1. **Find the files** mutmut is set to mutate: `[tool.mutmut] only_mutate`, else everything tracked under
   `source_paths`. A file outside that list is never looked at.
2. **Find the mutants on changed lines.** For each such file whose diff against the base changed lines, it
   asks mutmut for every mutant of the file (`mutmut.mutation.file_mutation.mutate_file_contents`, a pure
   function of the source) and keeps those whose mutated line is a line the diff changed.
3. **Run only those.** `python -m mutmut run <names>` tests the chosen mutants and nothing else.
4. **Judge them.** The names are written to `mutants/mutation-selection.json`; `check_mutation_ratchet.py`
   counts the outcomes of exactly those mutants per function and refuses a function below the threshold.
   A chosen mutant with no verdict (the run was interrupted, or a test failed to collect) refuses its
   function, rather than being ignored.

## Placing a mutant on a line

mutmut writes every mutant as a full copy of its function with one change, next to the original:
`x_price__mutmut_orig`, `x_price__mutmut_1`, `x_price__mutmut_2`, and for a method `xǁBoxǁsize__mutmut_1`.
Comparing a mutant's body with the original's, line by line and without the `def` line (which differs by name
alone), gives the offsets of the lines the mutation changed; the original function's start line in the source
turns an offset into a line of the file. A mutant that inserts a line is attributed to the line it precedes.

## What a run costs, and what it does not

A cold run costs mutmut's fixed start-up plus the chosen mutants. The start-up is generating every mutant of
the project's mutated files and measuring, once, which tests cover which function; on a mid-sized repo
(measured: one function of twelve mutants, no cache) it was about two and a half minutes, nearly all of it
that fixed part. The mutants themselves ran at about thirteen per second there. A function whose tests
wait out a production time budget when a mutant breaks it costs that wait for every killed mutant (one such
function took 25 seconds per mutant in a consumer repo, the length of its production budget): that is a
property of the tests, and the cure is in them (shorten the budget there).

## Why nothing is kept between runs

The previous design kept mutmut's cache of verdicts and a planner (`mutation_plan.py`) that dropped the
verdicts a change could have staled. It was correct only as far as the planner's model of staleness was: a
touched function whose tests changed but whose own code did not has a cached verdict that is wrong, and the
planner had to reset it by hand, along with renames, lock files, unmutated modules and pytest arguments. Each
was a way to serve a stale verdict, and a cache also needed priming, evicting and rebuilding. A cold run has
none of that, and for a change that touches a few lines it costs about what the cache saved.

There is also no baseline: no score is stored, compared or committed, and a function that is only covered by
a test the pull request edited is not judged. A scheduled full campaign is no longer part of the gate; it
would judge nothing, because the ratchet looks only at the lines a diff changed.

## Limits

- The start-up grows with the number of mutants and covering tests in the mutated files, not with the diff.
  `only_mutate` and a focused `pytest_add_cli_args_test_selection` keep it small.
- A change that adds a line no mutation touches (a comment, a blank line) selects nothing, and a run that
  selects nothing starts no mutmut at all.
- The mapping reads mutmut's generated module and imports one of its functions: the same kind of coupling
  `check_mutation_ratchet.py` already accepts. If the generated layout changes, the mapping selects nothing
  rather than guessing, and the tests that drive real mutmut end to end fail first.
