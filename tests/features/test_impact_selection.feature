Feature: A pull request runs only the test files its change can affect
  The last full run on the main branch recorded which test file ran which source line. A change is
  read against that run: a line selects the tests that ran it, and whatever cannot be placed selects
  everything, so the selection is never narrower than the change allows.

  Background:
    Given a project with two tests, one for each of its two functions

  Scenario Outline: a change selects the tests it can affect
    Given the full run recorded which test ran which line
    When the change is "<change>"
    Then the pull request runs <selection>

    Examples:
      | change                                      | selection                          |
      | a line only the first test ran is edited    | the first test                     |
      | a line that runs at import is edited        | both tests                         |
      | a test file is edited                       | that test                          |
      | only the readme is edited                   | no test                            |
      | a new source file no test ran is added      | no test                            |
      | the lock file is edited                     | every test                         |
      | conftest.py is edited                       | every test                         |

  Scenario: without a map every test runs
    When a change edits a line only the first test ran
    Then the pull request runs every test

  Scenario: a map older than the limit is not trusted
    Given the full run recorded which test ran which line
    And that map is older than the limit
    When a change edits a line only the first test ran
    Then the pull request runs every test

  Scenario: a map restored into the checkout is not a change
    Given the full run recorded which test ran which line
    And the map is restored into the checkout
    When a change edits a line only the first test ran
    Then the pull request runs the first test

  Scenario: the map is made from a real run with per-test coverage
    When the tests run with per-test coverage and the map is recorded
    Then the map names each test file against the lines it ran
    And a change to a line only the first test ran selects the first test
