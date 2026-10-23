Feature: A file that only moved is not new code
  Moving a module into a folder rewrites its path, not its contents. The complexity ratchet follows the
  move (git's own rename detection): what the file carried is compared with what it was, so legacy
  debt is grandfathered the same way and anything written after the move is judged as new.

  Background:
    Given a base commit whose module has an over-limit function and a thrice-used literal

  Scenario: the same module in another folder passes
    When the module moves to another folder unchanged
    Then the complexity ratchet passes

  Scenario: a module moved without being edited is not touched, so it owes nothing
    When the module moves to another folder unchanged
    Then no function of it counts as touched

  Scenario: a function made worse while the module moves is refused
    When the module moves to another folder and its long function gains a branch
    Then the complexity ratchet fails

  Scenario: a new complex function added while the module moves is refused
    When the module moves to another folder and gains a new function over the limit
    Then the complexity ratchet fails

  Scenario: a copy of the module, with the original kept, is new code
    When the module is copied to another folder and the original kept
    Then the complexity ratchet fails
