Feature: A module that carries architecture breaches pays one down whenever it is touched
  architecture.yaml lists the imports that break the layering today. The list may only shrink, so a
  change that edits a module owning some of them must remove at least one, or say why it cannot.

  Background:
    Given a repository with the modules shop.domain.bad and shop.domain.clean

  Scenario: touching the module and leaving its breaches is refused
    Given architecture.yaml lists two known violations in shop.domain.bad
    And a branch for the change
    When the change edits shop/domain/bad.py
    Then the architecture ratchet fails
    And the report names "shop/domain/bad.py: 2 listed in architecture.yaml, still 2"

  Scenario: touching the module and removing one breach passes
    Given architecture.yaml lists two known violations in shop.domain.bad
    And a branch for the change
    When the change edits shop/domain/bad.py
    And the change removes one known violation
    Then the architecture ratchet passes

  Scenario: touching a module that owns no breach passes
    Given architecture.yaml lists two known violations in shop.domain.bad
    And a branch for the change
    When the change edits shop/domain/clean.py
    Then the architecture ratchet passes

  Scenario: a Tidy-Exempt trailer waives the rule
    Given architecture.yaml lists two known violations in shop.domain.bad
    And a branch for the change
    When the change edits shop/domain/bad.py with a Tidy-Exempt trailer
    Then the architecture ratchet passes

  Scenario: a repository without an architecture.yaml has nothing to check
    Given a branch for the change
    When the change edits shop/domain/bad.py
    Then the architecture ratchet passes
