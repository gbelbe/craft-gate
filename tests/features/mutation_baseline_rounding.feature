Feature: A function whose tests changed is judged on the precision its baseline stores
  The baseline file keeps a score to four decimals. A function re-tested because a test changed must
  not be refused for the rounding of that stored value when its mutant counts did not change.

  Scenario Outline: the verdict for a function whose recorded score has decimals
    Given a function recorded at <recorded> percent
    When a test change leaves it with <killed> killed and <survived> surviving mutants
    Then the ratchet <verdict>

    Examples:
      | recorded | killed | survived | verdict                                    |
      | 97.4359  | 38     | 1        | accepts it                                 |
      | 97.2973  | 36     | 1        | accepts it                                 |
      | 97.4359  | 35     | 1        | refuses it, from 97.44% to 97.22%          |
