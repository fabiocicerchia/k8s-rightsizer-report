@domain:run-history @area:workload-identity @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Recognising the same container across runs
  Lets the stability rule follow one container from run to run so its recommendation history is its own.

  @id:run-history.workload-identity.001 @rule:run-history.workload-identity.keyed-by-namespace-kind-workload-container @verified @source:k8s_rightsizer_report.py#normalise @test:tests/test_rightsizer.py#test_normalise_reads_krr_values_and_allocations
  Scenario Outline: A recommendation is identified by namespace, kind, workload and container
    Given KRR reports container app of workload api with namespace <namespace> and kind <kind>
    When the operator runs the rightsizer
    Then the recommendation is tracked as `<key>`

    Examples:
      | namespace | kind        | key                        |
      | prod      | Deployment  | prod/Deployment/api/app    |
      | prod      | StatefulSet | prod/StatefulSet/api/app   |
      | (missing) | (missing)   | default/Deployment/api/app |

  @id:run-history.workload-identity.002 @rule:run-history.workload-identity.unidentifiable-scans-ignored @inferred @source:k8s_rightsizer_report.py#normalise
  Scenario: A KRR result without a workload or container name is ignored
    Given KRR reports one scan with no container name and one for prod/Deployment/api/app
    When the operator runs the rightsizer
    Then only `prod/Deployment/api/app` is recorded and reported
