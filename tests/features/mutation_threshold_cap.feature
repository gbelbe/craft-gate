Feature: A recorded baseline never owes more than the threshold
  A function below the threshold may pass by improving on its recorded score. That improvement is
  capped at the threshold, which is the bar for fresh code: 78% plus 20% would be 94%, but reaching
  the threshold is enough.

  Scenario Outline: the verdict for a function that has a recorded baseline
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
      | 80        | 50       | 59    | refuses it, needing 60 |
      | 80        | 50       | 60    | accepts it             |
