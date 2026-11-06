Feature: Every touched function owes the threshold
  The mutation ratchet judges a touched function against one number, the threshold, and nothing
  else: not whether the function is new, not what it scored the last time. Touching a weak function
  means strengthening its tests.

  Scenario Outline: the verdict for a touched function
    Given a threshold of <threshold> percent
    When the function scores <score> percent
    Then the ratchet <verdict>

    Examples:
      | threshold | score | verdict                |
      | 80        | 80    | accepts it             |
      | 80        | 79    | refuses it, needing 80 |
      | 80        | 60    | refuses it, needing 80 |
      | 90        | 89    | refuses it, needing 90 |
      | 90        | 90    | accepts it             |
