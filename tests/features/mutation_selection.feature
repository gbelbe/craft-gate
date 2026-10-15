Feature: The mutation run and the `mutation` marker cannot drift apart
  mutmut re-runs the tests named in pytest_add_cli_args_test_selection, narrowed by -m mutation.
  A marked test left out of that list is never run against a mutant, and an unregistered marker
  makes pytest refuse to start, so the mutation gate reports either instead of passing on less.

  Scenario Outline: the gate says what is inconsistent
    Given a repo that selects tests/unit/test_a.py with -m mutation
    And <setup>
    When the workflow asks for the mutation gate
    Then the mutation gate <verdict>

    Examples:
      | setup                                   | verdict                                  |
      | the marker is registered                | runs                                     |
      | the marker is not registered            | stops: the marker is not registered      |
      | the selected file is deleted            | stops: names file(s) that do not exist   |
      | another test file also carries the marker | stops: missing from pytest_add_cli_args_test_selection |
