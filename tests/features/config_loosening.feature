Feature: A pull request cannot loosen craft-gate.toml unnoticed
  A looser value fails no check, so the change is reported instead. Each row moves one value
  from the base commit's config to the head's and says whether it is reported. A test fails if
  a value in the schema has no row, so a new setting cannot ship without a ruling on which
  direction is looser.

  Scenario Outline: moving a value is reported only when it makes the gates weaker
    Given the base commit sets <key> to <before>
    And the head commit sets <key> to <after>
    When the loosening check runs
    Then the change to <key> <verdict>

    Examples: limits, where higher is looser
      | key                                       | before | after | verdict          |
      | complexity.cyclomatic                     | 15     | 40    | is reported      |
      | complexity.cyclomatic                     | 15     | 10    | is not reported  |
      | complexity.cognitive                      | 15     | 40    | is reported      |
      | complexity.cognitive                      | 15     | 10    | is not reported  |
      | complexity.duplicated-literal-occurrences | 3      | 6     | is reported      |
      | complexity.duplicated-literal-occurrences | 3      | 2     | is not reported  |
      | complexity.duplicated-literal-min-length  | 5      | 12    | is reported      |
      | complexity.duplicated-literal-min-length  | 5      | 2     | is not reported  |
      | design-review.max-parameters              | 2      | 5     | is reported      |
      | design-review.max-parameters              | 2      | 1     | is not reported  |
      | design-review.max-lines                   | 20     | 50    | is reported      |
      | design-review.max-lines                   | 20     | 10    | is not reported  |

    Examples: floors, where lower is looser
      | key                       | before | after | verdict          |
      | patch-coverage.threshold  | 90     | 60    | is reported      |
      | patch-coverage.threshold  | 90     | 95    | is not reported  |
      | mutation.threshold        | 80     | 50    | is reported      |
      | mutation.threshold        | 80     | 90    | is not reported  |
      | mutation.improvement      | 20     | 5     | is reported      |
      | mutation.improvement      | 20     | 30    | is not reported  |
      | bdd.threshold             | 80     | 50    | is reported      |
      | bdd.threshold             | 80     | 90    | is not reported  |

    Examples: switches
      | key                       | before | after | verdict          |
      | patch-coverage.enabled    | true   | false | is reported      |
      | patch-coverage.enabled    | false  | true  | is not reported  |
      | mutation.enabled          | true   | false | is reported      |
      | mutation.enabled          | false  | true  | is not reported  |
      | bdd.enabled               | true   | false | is reported      |
      | bdd.enabled               | false  | true  | is not reported  |
      | exemptions.legacy-debt    | false  | true  | is reported      |
      | exemptions.legacy-debt    | true   | false | is not reported  |
      | exemptions.new-code       | false  | true  | is reported      |
      | exemptions.new-code       | true   | false | is not reported  |

    Examples: refactor first
      | key                       | before            | after             | verdict         |
      | refactor-first.per-file   | "must-decrease"   | "must-not-increase" | is reported   |
      | refactor-first.per-file   | "must-not-increase" | "must-decrease" | is not reported |

    Examples: lists of what is counted
      | key                       | before            | after             | verdict         |
      | patch-coverage.exclude    | ["tests/*"]       | ["tests/*", "src/gen/*"] | is reported |
      | patch-coverage.exclude    | ["tests/*", "src/gen/*"] | ["tests/*"] | is not reported |
      | bdd.exclude               | ["tests/*"]       | ["tests/*", "src/gen/*"] | is reported |
      | bdd.exclude               | ["tests/*", "src/gen/*"] | ["tests/*"] | is not reported |
      | bdd.paths                 | ["tests/features", "tests/more"] | ["tests/features"] | is reported |
      | bdd.paths                 | ["tests/features"] | ["tests/features", "tests/more"] | is not reported |

    Examples: words and paths that judge nothing
      | key                       | before | after        | verdict          |
      | patch-coverage.reason     | ""     | "slow suite" | is not reported  |
      | mutation.reason           | ""     | "slow suite" | is not reported  |
      | bdd.reason                | ""     | "slow suite" | is not reported  |
      | patch-coverage.source     | ""     | "src"        | is not reported  |

  Scenario: a repo with no config yet is compared against the defaults
    Given the base commit has no craft-gate.toml
    And the head commit sets complexity.cyclomatic to 40
    When the loosening check runs
    Then the change to complexity.cyclomatic is reported

  Scenario: a file that only restates the defaults reports nothing
    Given the base commit has no craft-gate.toml
    And the head commit sets complexity.cyclomatic to 15
    When the loosening check runs
    Then nothing is reported

  Scenario: moving the settings from pyproject.toml to craft-gate.toml unchanged reports nothing
    Given the base commit keeps complexity.cyclomatic at 20 in pyproject.toml
    And the head commit keeps complexity.cyclomatic at 20 in craft-gate.toml
    When the loosening check runs
    Then nothing is reported

  Scenario: the pull request comment shows the loosening
    Given the base commit sets complexity.cyclomatic to 15
    And the head commit sets complexity.cyclomatic to 40
    When the pull request comment is drafted
    Then the comment has a "Thresholds loosened" section naming complexity.cyclomatic
