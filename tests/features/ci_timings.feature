Feature: A repo can see where its CI time goes
  The history of a workflow is already on GitHub; a gate's own stages and the tests behind a
  mutation run are not. These scenarios show both questions answered from recorded data.

  Scenario: the slowest job and step of a workflow are named
    Given a workflow history where "test" took 8 minutes and "lint" took 1 minute
    When the history is analysed
    Then the report lists "test" before "lint"
    And the report says "test" takes 89% of the job time

  Scenario: a gate's stages are timed into a file the job can render
    Given the timings file is named in the environment
    When a gate times a slow stage and a quick stage
    Then the rendered report lists the slow stage first

  Scenario: the tests that make every mutant slow are ranked
    Given mutmut recorded a 4 second test and a half second test for one function
    When the mutation costs are asked for
    Then the function costs 4.5 seconds per mutant

  Scenario: a mutation run that needs two passes shows each stage in the trace
    Given the timings file is named in the environment
    And a mutation plan that needs a second pass
    When the mutation run executes
    Then the trace names the stages "mutmut run (pass 1)" and "mutmut run (pass 2)"
