Feature: A repository that declares its architecture must run the ratchet
  The list of known violations in architecture.yaml may only shrink, and only the architecture ratchet
  makes it. craft-gate ships that script, but the job that calls it is pasted into the repository by
  hand, so the architecture check fails until a workflow or a pre-commit hook runs it.

  Background:
    Given a repository that declares its layers and has generated the architecture files

  Scenario: no workflow and no hook runs the ratchet
    When the architecture check runs
    Then the architecture check fails
    And the report names "check_architecture_ratchet.py"

  Scenario: a workflow runs the ratchet
    Given a workflow runs the ratchet
    When the architecture check runs
    Then the architecture check passes

  Scenario: a pre-commit hook runs the ratchet
    Given a pre-commit hook runs the ratchet
    When the architecture check runs
    Then the architecture check passes

  Scenario: a comment that names the script is not a job
    Given a workflow only mentions the ratchet in a comment
    When the architecture check runs
    Then the architecture check fails
