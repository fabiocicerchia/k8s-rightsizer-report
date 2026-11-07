@domain:run-history @area:reading-history @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Reading the run history
  Ensures the comparison over time is only made on a history the tool can fully trust.

  @id:run-history.reading-history.001 @rule:run-history.reading-history.unreadable-run-refused @verified @source:k8s_rightsizer_report.py#load_history @test:tests/test_rightsizer.py#test_load_history_refuses_a_corrupt_run
  Scenario Outline: A damaged history file stops the run instead of being skipped
    Given the history directory contains `2026-09-02T06-00-00Z.json` holding <content>
    When the operator runs the rightsizer
    Then stderr shows `error: <path> <message>`
    And the command exits with status 1
    And no new run is recorded

    Examples:
      | content                               | message                                                   |
      | text that is not JSON                 | is not readable as a recorded run: …                      |
      | a JSON object without recommendations | is not a k8s-rightsizer-report run (no `recommendations`) |
