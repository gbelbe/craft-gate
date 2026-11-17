Feature: The knowledge bundle becomes a browsable site without anyone writing the extra parts
  docs/knowledge stays the one place a person edits. The site source adds, from the bundle and the
  code, what makes it easy to browse: what a page depends on and what uses it, a diagram of its
  neighbours, the usage of its script and the scenarios that exercise it, and a map of the folders.

  Background:
    Given a repository whose knowledge bundle has a gates folder and a tooling folder
    And the page for alpha imports beta

  Scenario: a page lists what it depends on and what uses it
    When the site source is built
    Then the alpha page has a "Depends on" table naming Beta
    And the beta page has a "Used by" table naming Alpha

  Scenario: a page draws its neighbours
    When the site source is built
    Then the alpha page has a diagram with the arrow "imports" to Beta

  Scenario: a page with many targets of one kind collapses them by folder
    Given alpha calls 7 pages of the tooling folder
    When the site source is built
    Then the alpha diagram shows "7 tooling pages" instead of the 7 pages

  Scenario: a page shows the usage of its script
    When the site source is built
    Then the alpha page shows the help of "scripts/alpha.py"

  Scenario: a page shows the scenarios of the feature that exercises its script
    When the site source is built
    Then the alpha page shows the feature "alpha"

  Scenario: a folder hub is copied as it is
    When the site source is built
    Then the gates hub is unchanged

  Scenario: the system page draws one box per folder
    When the site source is built
    Then the overview names the folders "Gates" and "Tooling"

  Scenario: the bundle itself is left alone
    When the site source is built
    Then no page of docs/knowledge changed
