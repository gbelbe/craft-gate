Feature: The declared hexagon is enforced on the real imports
  architecture.yaml says how the application is layered. The rendered contracts, run by
  import-linter, fail a change that points an import the wrong way, leaves a module in no layer,
  or lets the list of known violations go stale; and they pass code that follows the declaration.

  Background:
    Given an application with adapters, application and domain layers

  Scenario: imports that point inward pass
    When the application layer imports the domain
    Then the architecture check passes

  Scenario: the domain importing an adapter is refused
    When the domain imports an adapter
    Then the architecture check fails
    And the report names the import "shop.domain.bad -> shop.adapters.db"

  Scenario: a known violation is tolerated while it exists
    Given the domain imports an adapter
    And that import is listed as a known violation
    Then the architecture check passes

  Scenario: a known violation that was fixed must leave the list
    Given that import is listed as a known violation
    Then the architecture check fails

  Scenario: a module in no layer is refused
    When a module is added that no layer owns
    Then the architecture check fails
    And the report names the module "shop.stray"

  Scenario: a module declared as shared belongs to no layer and passes
    When a module is added that no layer owns
    And that module is declared shared
    Then the architecture check passes

  Scenario: the contracts file must match the declaration
    When the declaration gains a layer without re-rendering
    Then the render check fails

  Scenario: the generated overview shows an import that breaks the rule
    Given the architecture documentation is requested
    And the domain imports an adapter
    When the documentation is generated
    Then the overview contains "domain -.->|1 against the rule| adapters"

  Scenario: the documentation goes stale when the code changes
    Given the architecture documentation is requested
    And the documentation is generated
    When the domain imports an adapter
    Then the render check fails
