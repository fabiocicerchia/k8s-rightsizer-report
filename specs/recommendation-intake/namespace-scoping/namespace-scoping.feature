@domain:recommendation-intake @area:namespace-scoping @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Scoping a run to one namespace
  Lets an operator limit a scan or a saved multi-namespace KRR result to the namespace they own.

  @id:recommendation-intake.namespace-scoping.001 @rule:recommendation-intake.namespace-scoping.filters-to-namespace @verified @source:k8s_rightsizer_report.py#normalise @test:tests/test_rightsizer.py#test_normalise_filters_by_namespace
  Scenario: Only the chosen namespace's workloads are considered
    Given the saved KRR output covers Deployment api in namespace prod and Deployment other in namespace staging
    When the operator runs the rightsizer with `--krr-json run.json -n staging`
    Then only `staging/Deployment/other/app` is recorded and reported
    And nothing from namespace prod appears in the report or the patches

  @id:recommendation-intake.namespace-scoping.002 @rule:recommendation-intake.namespace-scoping.empty-filter-recorded @inferred @source:k8s_rightsizer_report.py#run_once @questionable
  Scenario: A namespace that matches nothing in a saved file still records an empty run
    Given the history holds two steady runs for prod/Deployment/api/app
    And the saved KRR output covers only namespace prod
    When the operator runs the rightsizer with `--krr-json run.json -n typo`
    Then the run is recorded with no recommendations
    And the report shows `## Proposed (0)` and `Nothing has settled yet — nothing to propose.`
    And on the next prod run, api/app reads `not yet — 1 of 3 runs`

  @id:recommendation-intake.namespace-scoping.003 @rule:recommendation-intake.namespace-scoping.shared-history-breaks-streaks @inferred @source:k8s_rightsizer_report.py#_consecutive_proposals @questionable
  Scenario: Alternating namespaces in one history keep every workload from settling
    Given the operator records runs for namespaces a and b into the same history directory, alternating
    When the operator runs the rightsizer with `-n b` for the third time
    Then every workload in namespace b reads `not yet — 1 of 3 runs`
    And nothing is proposed
