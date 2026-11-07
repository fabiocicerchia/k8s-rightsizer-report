@domain:stability-rule @area:limit-conflicts @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Holding back proposals that would break request and limit rules
  Keeps a merged proposal from producing a manifest the Kubernetes API server rejects at rollout.

  @id:stability-rule.limit-conflicts.001 @rule:stability-rule.limit-conflicts.request-above-limit-held @verified @source:k8s_rightsizer_report.py#limit_conflicts @test:tests/test_rightsizer.py#test_a_request_above_an_existing_limit_is_held_back @test:tests/test_rightsizer.py#test_a_request_under_the_existing_limit_is_proposed
  Scenario Outline: A settled request above the limit in force is held back
    Given KRR has recommended a <request> CPU request for prod/Deployment/api/app for three runs
    And the container currently has a 100m CPU limit and KRR proposes no CPU limit
    When the operator runs the rightsizer
    Then api/app is <outcome>
    And <detail>

    Examples:
      | request | outcome   | detail                                                                                     |
      | 120m    | held back | its why reads `not yet — cpu request 120m exceeds its 100m limit` and no patch is produced |
      | 80m     | proposed  | no conflict is listed for it                                                               |

  @id:stability-rule.limit-conflicts.002 @rule:stability-rule.limit-conflicts.proposed-limit-resolves @verified @source:k8s_rightsizer_report.py#limit_conflicts @test:tests/test_rightsizer.py#test_a_limit_krr_proposes_itself_settles_the_conflict
  Scenario: A limit KRR proposes itself is the one checked
    Given KRR has recommended a 120m CPU request and a 200m CPU limit for three runs
    And the container currently has a 100m CPU limit
    When the operator runs the rightsizer
    Then api/app is proposed with a 200m CPU limit
    And nothing is held back

  @id:stability-rule.limit-conflicts.003 @rule:stability-rule.limit-conflicts.flapping-reported-first @verified @source:k8s_rightsizer_report.py#classify @test:tests/test_rightsizer.py#test_a_flapping_number_reads_as_flapping_even_when_it_also_conflicts
  Scenario: A recommendation still moving is reported as flapping even if it also conflicts
    Given KRR recommended 120m, 400m, 120m CPU for prod/Deployment/api/app
    And the container has a 100m CPU limit
    When the operator runs the rightsizer
    Then api/app's why reads `not yet — flapping`
    And with `--json`, its `conflicts` list contains `cpu request 120m exceeds its 100m limit`
