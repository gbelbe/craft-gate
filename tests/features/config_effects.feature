Feature: Every value in craft-gate.toml changes what a gate does
  A threshold nobody has seen take effect is a threshold nobody can trust. Each scenario
  below moves one value and shows the verdict move with it. The @key tag names the value it
  proves; a test fails if any value in the schema has no scenario.

  Background:
    Given a repo whose base commit has one calm module

  # -- complexity ---------------------------------------------------------------------------

  @key:complexity.cyclomatic
  Scenario Outline: the cyclomatic limit decides whether a new function is too complex
    Given the config sets complexity.cyclomatic to <limit>
    And the change adds a function with 11 flat branches
    When the complexity ratchet runs
    Then the complexity ratchet <verdict>

    Examples:
      | limit | verdict |
      | 15    | passes  |
      | 10    | fails   |

  @key:complexity.cognitive
  Scenario Outline: the cognitive limit decides whether deep nesting is too complex
    Given the config sets complexity.cognitive to <limit>
    And the change adds a function nested 4 levels deep
    When the complexity ratchet runs
    Then the complexity ratchet <verdict>

    Examples:
      | limit | verdict |
      | 15    | passes  |
      | 5     | fails   |

  @key:complexity.duplicated-literal-occurrences
  Scenario Outline: how many repeats make a literal duplicated is a setting
    Given the config sets complexity.duplicated-literal-occurrences to <occurrences>
    And the change repeats a 9-character literal 3 times
    When the complexity ratchet runs
    Then the complexity ratchet <verdict>

    Examples:
      | occurrences | verdict |
      | 3           | fails   |
      | 4           | passes  |

  @key:complexity.duplicated-literal-min-length
  Scenario Outline: how short a literal may be before it is ignored is a setting
    Given the config sets complexity.duplicated-literal-min-length to <length>
    And the change repeats a 9-character literal 3 times
    When the complexity ratchet runs
    Then the complexity ratchet <verdict>

    Examples:
      | length | verdict |
      | 5      | fails   |
      | 10     | passes  |

  # -- refactor first -------------------------------------------------------------------------

  @key:refactor-first.per-file
  Scenario Outline: a touched file must end lower, or merely not worse
    Given the base commit already has a smelly module
    And the config sets refactor-first.per-file to "<mode>"
    And the change only edits a comment in the smelly module
    When Refactor First runs
    Then Refactor First <verdict>

    Examples:
      | mode              | verdict |
      | must-decrease     | fails   |
      | must-not-increase | passes  |

  # -- exemptions -------------------------------------------------------------------------------

  @key:exemptions.legacy-debt
  Scenario Outline: whether Tidy-Exempt waives the legacy-debt rules is a setting
    Given the base commit already has a smelly module
    And the config sets exemptions.legacy-debt to <waived>
    And the change only edits a comment in the smelly module
    And the commit carries a Tidy-Exempt trailer
    When Refactor First runs
    Then Refactor First <verdict>

    Examples:
      | waived | verdict |
      | true   | passes  |
      | false  | fails   |

  @key:exemptions.new-code
  Scenario Outline: whether Tidy-Exempt waives the new-code rules is a setting
    Given the config sets exemptions.new-code to <waived>
    And the change adds a function with 20 flat branches
    And the commit carries a Tidy-Exempt trailer
    When the complexity ratchet runs
    Then the complexity ratchet <verdict>

    Examples:
      | waived | verdict |
      | false  | fails   |
      | true   | passes  |

  # -- design review ------------------------------------------------------------------------------

  @key:design-review.max-parameters
  Scenario Outline: how many parameters the design review tolerates is a setting
    Given the config sets design-review.max-parameters to <limit>
    And the change adds a function with 3 parameters
    When the design review runs
    Then the design review <outcome> a prompt about "parameters"

    Examples:
      | limit | outcome  |
      | 2     | has      |
      | 3     | lacks    |

  @key:design-review.max-lines
  Scenario Outline: how long a function the design review tolerates is a setting
    Given the config sets design-review.max-lines to <limit>
    And the change adds a function 25 lines long
    When the design review runs
    Then the design review <outcome> a prompt about "lines"

    Examples:
      | limit | outcome  |
      | 20    | has      |
      | 40    | lacks    |

  # -- the test gates: every setting reaches the workflow --------------------------------------------

  @key:patch-coverage.threshold
  Scenario: patch coverage publishes its threshold
    Given the config sets patch-coverage.threshold to 75
    When the workflow asks for the patch-coverage gate
    Then the workflow is told threshold=75

  @key:patch-coverage.source
  Scenario: patch coverage publishes the package it measures
    Given the config sets patch-coverage.source to "mypkg"
    When the workflow asks for the patch-coverage gate
    Then the workflow is told source=mypkg

  @key:patch-coverage.exclude
  Scenario: patch coverage publishes what it leaves out
    Given the config sets patch-coverage.exclude to ["gen/*", "vendor/*"]
    When the workflow asks for the patch-coverage gate
    Then the workflow is told exclude=gen/* vendor/*

  @key:patch-coverage.enabled
  Scenario: patch coverage can be switched off with a reason
    Given the config sets patch-coverage.enabled to false
    And the config sets patch-coverage.reason to "scripts only"
    When the workflow asks for the patch-coverage gate
    Then the workflow is told status=skip

  @key:patch-coverage.reason
  Scenario: the reason for switching a gate off is published
    Given the config sets patch-coverage.enabled to false
    And the config sets patch-coverage.reason to "scripts only"
    When the workflow asks for the patch-coverage gate
    Then the workflow is told reason=scripts only

  @key:mutation.threshold
  Scenario: the mutation ratchet publishes its minimum score
    Given a [tool.mutmut] section exists
    And the config sets mutation.threshold to 65
    When the workflow asks for the mutation gate
    Then the workflow is told threshold=65

  @key:mutation.improvement
  Scenario: the mutation ratchet publishes how much a baseline must improve
    Given a [tool.mutmut] section exists
    And the config sets mutation.improvement to 35
    When the workflow asks for the mutation gate
    Then the workflow is told improvement=35

  @key:mutation.dependency-change
  Scenario: the mutation ratchet publishes whether a dependency change keeps its cache
    Given a [tool.mutmut] section exists
    And the config sets mutation.dependency-change to "keep"
    When the workflow asks for the mutation gate
    Then the workflow is told dependency-change=keep

  @key:mutation.enabled
  Scenario: the mutation ratchet can be switched off
    Given the config sets mutation.enabled to false
    And the config sets mutation.reason to "no mutmut yet"
    When the workflow asks for the mutation gate
    Then the workflow is told status=skip

  @key:mutation.reason
  Scenario: the mutation ratchet publishes why it was switched off
    Given the config sets mutation.enabled to false
    And the config sets mutation.reason to "no mutmut yet"
    When the workflow asks for the mutation gate
    Then the workflow is told reason=no mutmut yet

  @key:bdd.threshold
  Scenario: behaviour coverage publishes its threshold
    Given the repo has scenarios under tests/features
    And the config sets bdd.threshold to 60
    When the workflow asks for the bdd gate
    Then the workflow is told threshold=60

  @key:bdd.paths
  Scenario: behaviour coverage publishes where its scenarios live
    Given the repo has scenarios under spec
    And the config sets bdd.paths to ["spec"]
    When the workflow asks for the bdd gate
    Then the workflow is told paths=spec

  @key:bdd.exclude
  Scenario: behaviour coverage publishes what it leaves out
    Given the repo has scenarios under tests/features
    And the config sets bdd.exclude to ["steps/*"]
    When the workflow asks for the bdd gate
    Then the workflow is told exclude=steps/*

  @key:bdd.enabled
  Scenario: behaviour coverage can be switched off
    Given the config sets bdd.enabled to false
    And the config sets bdd.reason to "specified in unit tests"
    When the workflow asks for the bdd gate
    Then the workflow is told status=skip

  @key:bdd.reason
  Scenario: behaviour coverage publishes why it was switched off
    Given the config sets bdd.enabled to false
    And the config sets bdd.reason to "specified in unit tests"
    When the workflow asks for the bdd gate
    Then the workflow is told reason=specified in unit tests
