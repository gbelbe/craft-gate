Feature: Every touched function owes the threshold, whatever it scored before
  The mutation ratchet judges a touched function against one number, the threshold. A function that
  is new, one that was recorded at a low score and one that was recorded high are all held to it:
  nothing is compared with an earlier score, so touching a weak function means strengthening its tests.

  Scenario Outline: the verdict for a function that was recorded before
    Given a threshold of <threshold> percent
    And a function recorded at <baseline> percent
    When the function now scores <score> percent
    Then the ratchet <verdict>

    Examples:
      | threshold | baseline | score | verdict                |
      | 80        | 78       | 80    | accepts it             |
      | 80        | 78       | 79    | refuses it, needing 80 |
      | 90        | 78       | 89    | refuses it, needing 90 |
      | 90        | 78       | 90    | accepts it             |
      | 80        | 50       | 60    | refuses it, needing 80 |
      | 80        | 95       | 85    | accepts it             |

  Scenario Outline: the verdict for a function that was never recorded
    Given a threshold of <threshold> percent
    And a function that was never recorded
    When the function now scores <score> percent
    Then the ratchet <verdict>

    Examples:
      | threshold | score | verdict                |
      | 80        | 80    | accepts it             |
      | 80        | 79    | refuses it, needing 80 |
