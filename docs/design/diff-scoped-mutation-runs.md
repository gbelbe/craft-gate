# Diff-scoped mutation runs

A full mutmut campaign is the slowest thing in a pipeline, and by default it reruns whenever *anything*
near the tests changes. `scripts/mutation_plan.py` makes the run follow the diff: a full campaign on a
repo's first initialisation, and from then on only the verdicts the change can have staled.

**What the cost was.** On a consumer repo (3,098 mutants), a full local campaign took 1,429 s on a
laptop under heavy load (load average 80-99; the first 2,000 mutants had taken about 2.4 minutes before
the machine filled up), and a CI mutation job took 11 min 24 s on a PR that touched no mutated function —
it only added a test file. The cause is mutmut's invalidation, read from its 3.8 source and then
observed: with `cache_invalidation_files = ["tests/**/*.py"]` and `on_dependency_change = "rerun"`,
editing one test file reset the cached verdicts of four functions that test does not cover. The same
policy also fires on `pyproject.toml`, any lock file and every tracked non-Python file git reports as
changed since the last full run — including `.mutation-baseline.json`, which the ratchet itself rewrites.

**What mutmut already does well.** It hashes each mutated function's source and re-tests only the
mutants of a function that changed (plus its recorded callers). It measures a test it has never seen
(one with no recorded duration) on its own, without a full stats pass. And `mutmut run <name>` re-tests
named mutants even when a verdict is cached; a plain `mutmut run` re-tests every mutant whose verdict is
empty. Those three facts are all this feature needs.

**What it cannot see**, and so cannot invalidate narrowly: an edited test, a fixture or helper those
tests import, a data file they read, an unmutated module a mutated function calls. Its only answer is
the global reset above. The planner supplies the missing precision:

| The diff changes | Effect |
|---|---|
| a mutated function | nothing: mutmut hashes it |
| a test file in the selection | that file's tests are measured again; the functions they cover are re-tested |
| a test file added to the selection | first pass measures it; the second pass re-tests what it covers |
| a test file removed from the selection | what it used to cover is re-tested |
| a `conftest.py` below `tests/` | the tests beneath it |
| a helper under `tests/` | the tests that import it |
| a data file under `tests/` | the tests that name it, else the tests nearest it |
| a data file under the source tree | the functions of the mutated modules that name it |
| an unmutated module | the tests whose imports reach it, directly or through other modules |
| a lock file, the dependency list, pytest's own arguments, the root `conftest.py` | **full rerun**: any verdict may change |
| docs, workflows, the baseline file, other `pyproject.toml` sections | nothing |

**Mechanism.** The planner empties the verdicts of the functions to re-test (what mutmut's own
`_reset_mutant_results` does), forgets the stale tests so mutmut measures them again, and, when the
selection only grew, re-signs the stored selection fingerprint so mutmut does not reset everything over a
list that merely got longer. Then a plain `mutmut run` does the work. The fingerprint is verified against
the exact scheme before it is touched; if the cache does not look like mutmut 3.8's, or planning fails for
any reason, the run falls back to a full campaign, so a wrong plan costs time and never a wrong verdict.

**Judging what was re-tested.** A function re-tested because its tests changed was not touched, so it is
not held to the threshold. But a test change must not leave it weaker: the ratchet refuses a function whose
score fell below its recorded baseline (`--regression-tolerance` points of slack, default 0) and raises the
baseline when it rose; a function with no baseline is recorded. A mutant still without a verdict after
the run (the run was interrupted, or a test failed to collect) is reported as not re-tested rather than
silently ignored.

**Measured**, on the same consumer repo narrowed to one mutated file (654 mutants): first initialisation
37 s; after editing one test file, 16 s, re-testing 89 mutants (14%), with all 654 verdicts present and
unchanged elsewhere. Most of the 16 s is fixed overhead (mutmut start-up, the clean test run, measuring the
changed tests), so the gain grows with the size of the campaign it avoids. Deleting the tests of one
function was caught: `a test change lowered its mutation score from 100% to 66%`. Not measured: a CI run
with this planner on a real PR.

**Limits.**
- Static imports only: a module reached through `importlib`, a plugin entry point or a string is not followed.
- A production edit that changes which functions an *existing* test runs is not re-measured (mutmut does not
  either); the effect is a mapping that can miss a test, so a survivor may be over-reported, never a kill.
- Non-Python files outside `tests/` and the source tree are ignored.
- A renamed test file is a deletion plus an addition.
- Needs Python 3.11 for `tomllib`; on 3.10 every run is a full run.
- Keep a scheduled full run (`--fresh`) as the backstop for a test weakened without any function being
  touched at all.

Set `on_dependency_change = "warn"` and keep `tests/**/*.py` out of `cache_invalidation_files`; otherwise
mutmut's own invalidation resets everything before the planner has a say (the plan then costs nothing, but
saves nothing).
