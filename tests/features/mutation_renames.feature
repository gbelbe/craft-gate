Feature: Moving a test file does not cost a mutation re-run
  A test file moved to another folder is the same tests. The mutation cache knows them by their path,
  so the plan follows the move instead of forgetting them and measuring every function they cover again.

  Scenario: a test file moved without a change
    Given a mutation cache that knows the tests of tests/unit/test_a.py
    When tests/unit/test_a.py is moved to tests/brick/test_a.py
    Then the plan re-tests no function
    And the cache names those tests after tests/brick/test_a.py

  Scenario: a test file moved and edited, covering a function the change does not touch
    Given a mutation cache that knows the tests of tests/unit/test_a.py
    When tests/unit/test_a.py is moved to tests/brick/test_a.py and edited
    Then the plan measures those tests again
    And the plan re-tests no function

  Scenario: a test file moved and edited, covering a function the change touches
    Given a mutation cache that knows the tests of tests/unit/test_a.py
    When tests/unit/test_a.py is moved to tests/brick/test_a.py and edited, and the function it covers is edited too
    Then the plan re-tests the function those tests cover
