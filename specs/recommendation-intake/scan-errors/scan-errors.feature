@domain:recommendation-intake @area:scan-errors @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Guarding the history against failed scans
  Protects the stability evidence from scans that observed nothing or only part of the cluster, and tells the operator why streaks broke.

  @id:recommendation-intake.scan-errors.001 @rule:recommendation-intake.scan-errors.empty-scan-refused @verified @source:k8s_rightsizer_report.py#observed @test:tests/test_rightsizer.py#test_a_scan_of_nothing_is_refused_rather_than_recorded
  Scenario: A scan that observed nothing is refused and never recorded
    Given the history holds three steady runs for prod/Deployment/api/app
    And KRR returns a document with an empty scan list
    When the operator runs the rightsizer
    Then stderr shows `error: krr scanned nothing — refusing to record a run that would reset every stability streak. Check the namespace, and that krr can reach Prometheus.`
    And the command exits with status 1
    And the history still holds three runs and api/app is still proposed on the next good run

  @id:recommendation-intake.scan-errors.002 @rule:recommendation-intake.scan-errors.krr-errors-warned @inferred @source:k8s_rightsizer_report.py#krr_errors
  Scenario: Errors KRR reported are shown as warnings that the run may be partial
    Given KRR's output lists the error `failed to fetch metrics for prod/worker`
    When the operator runs the rightsizer
    Then the run is still recorded and reported
    And stderr shows `warning: krr reported an error, so this run may be partial: failed to fetch metrics for prod/worker`
    And with `--json`, the same text appears in the payload's `warnings` list instead
