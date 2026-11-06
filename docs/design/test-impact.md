# Test impact

A pull request runs only the test files its diff can affect; the whole suite runs when a change lands.
`scripts/test_impact.py` does the choosing, `templates/test-impact.yml` wires it into a workflow. It is
opt-in: nothing changes for a repo until its workflow adds the job.

## Why not the import graph

Selecting by what a test file imports is static and needs no stored data, but it is an upper bound:
a shared `conftest.py`, or a few modules that import most of the package, make nearly every test file
"reach" nearly every change. A viz or protocol feature in a repo like that selects all of its tests. What a
test file actually *executed* is far narrower, and coverage already measures it.

## The map

The full run that lets a change land is made with `pytest --cov --cov-context=test`. `record` reads the data
file and keeps, for each source file, the lines each *test file* executed (as ranges), with the **tree** the
run was made on and the time. A tree, not a commit: a squash or rebase merge lands the tested content as a
new commit, and the map still names it. Code that runs when a module is imported (module-level statements) is
executed outside any test and has no test to name; it is not recorded against one.

## The choice

`select` compares the working tree with the map's tree and reads the **old side** of the diff, so the map's
line numbers hold even when the main branch has moved on since the run (the diff then also holds those
other changes, a superset, which is the safe side).

| Change | Selects |
|---|---|
| a source line a test executed | the test files that executed it |
| a source line no test names (import-time code, a comment, a line no test ran) | every test file that ran the file at all |
| a test file (`test_*.py`) | that file |
| a deleted test file, a documentation file | nothing |
| a source file no test ran, or a new one | nothing (its tests are the changed ones) |
| `conftest.py`, a helper beside the tests, a lock file, a workflow, a data file, a feature file | everything |
| no map, an unreadable or old one (`--max-age-days`, 14), a map tree not in the checkout | everything |

The map file itself is not a change: a run restores it into the checkout, where git sees a new file.
A file git has not yet seen counts as added, so the selection works before a commit as well.

## What stops a miss from landing, and who records the map

A pull request that runs only a selection could merge a change that breaks a test it did not run. The template
runs the whole suite in the **merge queue**: the change about to land is tested in full, and a failure
refuses the merge. That same run records the map and keeps it as an artifact named `test-impact-map-<tree>`.

The push to the main branch that follows looks for the artifact of its own tree. Found: the queue already ran
every test on exactly this content, and the push runs nothing. Not found (an administrator pushed past the
queue, or the repository has none): the push runs the whole suite and records the map itself. The whole suite
therefore runs once per change, not twice. A pull request restores the newest map; one whose tree never
landed (a queue entry that passed and was dropped) is not in the checkout, and the pull request runs everything.

## Limits

- Dynamic dispatch, files read at run time (templates, JSON, JavaScript assets) and tests of command-line
  output are not tied to lines; a file of a kind the map cannot place selects everything.
- The map ages: it is rebuilt by each run on the main branch, and one older than `--max-age-days` is refused.
- Selection is by test *file*: the cost of running a few extra tests in a file is less than the risk of
  missing one.
