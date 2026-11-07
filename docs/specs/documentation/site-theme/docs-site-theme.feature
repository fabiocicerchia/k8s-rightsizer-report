@domain:documentation @area:site-theme @from:stylesheets/extra
Feature: Docs site theme and branding
  Gives readers of the documentation site and the splash page one consistent, privacy-respecting look that works offline.

  Background:
    Given the project's documentation site and its splash page are published

  @id:docs.documentation.site-theme.001 @rule:documentation.site-theme.no-external-font-requests @inferred @source:docs/stylesheets/extra.css#:root
  Scenario: The docs render in system fonts without fetching anything from the network
    Given a reader's browser blocks all third-party requests
    When the reader opens a page of the documentation site
    Then body text renders in the operating system's own sans-serif font
    And code renders in the operating system's own monospace font
    And no web font or CDN stylesheet is requested

  @id:docs.documentation.site-theme.002 @rule:documentation.site-theme.shared-accent-palette @inferred @source:docs/stylesheets/extra.css#:root
  Scenario: The splash page and the docs show the same accent colours
    Given the accent pair is set to the platform/Kubernetes blue, #38bdf8 and #3b82f6
    When a reader moves from the splash page to the documentation
    Then the splash headline and button use a #38bdf8 to #3b82f6 gradient
    And the docs hero headline and primary buttons use the same gradient
    And links in the docs' light scheme are #3b82f6 and links in the dark scheme are #38bdf8

  @id:docs.documentation.site-theme.003 @rule:documentation.site-theme.no-placeholder-logo @inferred @source:docs/stylesheets/extra.css#.md-header__button.md-logo
  Scenario: The docs header shows no stand-in logo while the project has none
    Given no project logo is configured for the documentation site
    When a reader opens a page of the documentation site
    Then the header shows the site title with no logo glyph
    And the navigation drawer title shows no logo glyph
