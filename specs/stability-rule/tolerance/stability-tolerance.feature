@domain:stability-rule @area:tolerance @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Deciding whether a recommendation has changed
  Lets the operator say how much movement between runs still counts as the same recommendation.

  @id:stability-rule.tolerance.001 @rule:stability-rule.tolerance.within-percent-of-smallest @verified @source:k8s_rightsizer_report.py#within_tolerance @test:tests/test_rightsizer.py#test_within_tolerance_counts_small_moves_as_unchanged @test:tests/test_rightsizer.py#test_tolerance_and_run_count_are_configurable
  Scenario Outline: Values within the tolerance of the smallest count as unchanged
    Given KRR's CPU request recommendation over the last runs was <values>
    When the operator runs the rightsizer with `--tolerance <pct>`
    Then the recommendation is counted as <verdict>

    Examples:
      | values     | pct | verdict   |
      | 100m, 110m | 15  | unchanged |
      | 100m, 120m | 15  | changed   |
      | 100m, 150m | 60  | unchanged |

  @id:stability-rule.tolerance.002 @rule:stability-rule.tolerance.judged-per-dimension @verified @source:k8s_rightsizer_report.py#stability @test:tests/test_rightsizer.py#test_memory_flapping_holds_back_a_steady_cpu
  Scenario: Every request and limit must hold steady on its own
    Given KRR's CPU request held at 100m over three runs
    And its memory request went 100Mi, 100Mi, 400Mi
    When the operator runs the rightsizer
    Then nothing is proposed for the container
    And its range reads `requests.memory 100Mi–400Mi (+300%)`

  @id:stability-rule.tolerance.003 @rule:stability-rule.tolerance.appearing-dimension-is-change @verified @source:k8s_rightsizer_report.py#within_tolerance @test:tests/test_rightsizer.py#test_within_tolerance_counts_small_moves_as_unchanged
  Scenario Outline: A size KRR proposes in some runs but not others counts as changed
    Given KRR proposed <cpu limits> as the CPU limit over the last runs
    When the operator runs the rightsizer
    Then the CPU limit is counted as <verdict>

    Examples:
      | cpu limits | verdict   |
      | none, none | unchanged |
      | none, 100m | changed   |
