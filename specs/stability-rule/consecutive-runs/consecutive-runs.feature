@domain:stability-rule @area:consecutive-runs @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Requiring consecutive stable runs
  Ensures only recommendations that have held steady for N runs in a row reach a reviewer.

  @id:stability-rule.consecutive-runs.001 @rule:stability-rule.consecutive-runs.proposed-after-n-runs @verified @source:k8s_rightsizer_report.py#classify @test:tests/test_rightsizer.py#test_three_steady_runs_are_proposed @test:tests/test_rightsizer.py#test_two_steady_runs_are_not_yet_proposed
  Scenario Outline: A recommendation is proposed once it has held for the required number of runs
    Given KRR recommended <cpu values> for prod/Deployment/api/app over consecutive runs
    When the operator runs the rightsizer with the default rule
    Then api/app is <outcome>
    And its status reads `<status>`

    Examples:
      | cpu values       | outcome   | status                |
      | 100m, 105m, 110m | proposed  | stable for 3 runs     |
      | 100m, 105m       | held back | not yet — 2 of 3 runs |

  @id:stability-rule.consecutive-runs.002 @rule:stability-rule.consecutive-runs.gap-breaks-streak @verified @source:k8s_rightsizer_report.py#_consecutive_proposals @test:tests/test_rightsizer.py#test_a_gap_in_the_history_breaks_the_streak
  Scenario: A run in which the workload was missing breaks its streak
    Given prod/Deployment/api/app was recommended 100m, then absent from one run, then 100m twice
    When the operator runs the rightsizer
    Then api/app is held back
    And its status reads `not yet — 2 of 3 runs`

  @id:stability-rule.consecutive-runs.003 @rule:stability-rule.consecutive-runs.old-swing-forgotten @verified @source:k8s_rightsizer_report.py#stability @test:tests/test_rightsizer.py#test_a_settled_recommendation_survives_an_old_swing
  Scenario: A recommendation that has settled is proposed despite older swings
    Given prod/Deployment/api/app was recommended 900m, then 100m, 100m, 105m, 108m
    When the operator runs the rightsizer
    Then api/app is proposed
    And its status reads `stable for 4 runs`

  @id:stability-rule.consecutive-runs.004 @rule:stability-rule.consecutive-runs.configurable-run-count @verified @source:k8s_rightsizer_report.py#Rule @test:tests/test_rightsizer.py#test_tolerance_and_run_count_are_configurable
  Scenario Outline: The operator sets how many runs a recommendation must hold for
    Given prod/Deployment/api/app was recommended 100m then 150m
    When the operator runs the rightsizer with `--tolerance <pct> --runs <n>`
    Then api/app is <outcome>
    And the report's rule line reads `Rule: a recommendation is proposed only once it has stayed within <pct>% across <n> consecutive runs.`

    Examples:
      | pct | n | outcome   |
      | 15  | 3 | held back |
      | 60  | 2 | proposed  |

  @id:stability-rule.consecutive-runs.005 @rule:stability-rule.consecutive-runs.runs-below-one-not-refused @inferred @source:k8s_rightsizer_report.py#stability @questionable
  Scenario: A run count below one is accepted and proposes everything at once
    Given prod/Deployment/api/app appears for the first time in this run
    When the operator runs the rightsizer with `--runs 0`
    Then api/app is proposed with status `stable for 1 runs`
    And the rule line reads `… across 0 consecutive runs`
