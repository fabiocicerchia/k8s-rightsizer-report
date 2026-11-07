@domain:developer-tooling @area:installation @from:k8s-rightsizer-report/install
Feature: Installing the CLI with the one-line installer
  Lets an operator install the k8s-rightsizer-report command in one step, using pipx when it is available and pip otherwise.

  Background:
    Given the operator runs the one-line installer from the project's main branch

  @id:developer-tooling.installation.001 @rule:installation.installer.prefers-pipx-falls-back-to-pip @inferred @source:install.sh#install.sh
  Scenario Outline: The installer uses pipx when available and otherwise installs for the current user with pip
    Given pipx <pipx_state> on the operator's machine
    When the operator runs the installer
    Then k8s-rightsizer-report is installed from the project's GitHub repository with <installer>
    And the operator sees "k8s-rightsizer-report installed. Run: k8s-rightsizer-report --help"

    Examples:
      | pipx_state       | installer          |
      | is installed     | pipx install       |
      | is not installed | pip install --user |

  @id:developer-tooling.installation.002 @rule:installation.installer.failure-stops-without-success-message @inferred @source:install.sh#install.sh
  Scenario: A failed install stops the installer without claiming success
    Given the install step fails, for example because the repository cannot be reached
    When the operator runs the installer
    Then the installer exits with a non-zero status
    And the operator does not see "k8s-rightsizer-report installed"
