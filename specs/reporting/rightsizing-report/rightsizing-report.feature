@domain:reporting @area:rightsizing-report @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Reading the rightsizing report
  Gives the operator one readable page of what is proposed, what is held back, and the rule that decided it.

  @id:reporting.rightsizing-report.001 @rule:reporting.rightsizing-report.rule-and-both-verdicts @verified @source:k8s_rightsizer_report.py#render_report @test:tests/test_rightsizer.py#test_report_shows_the_rule_and_both_verdicts
  Scenario: The report states the rule and lists proposed and held recommendations
    Given prod/Deployment/api/app has held at 100m CPU for three runs
    And prod/Deployment/worker/app went 100m, 200m, 300m
    When the operator runs the rightsizer
    Then the report reads `Rule: a recommendation is proposed only once it has stayed within 15% across 3 consecutive runs.`
    And `## Proposed (1)` lists api with columns workload, container, current req, proposed req, current lim, proposed lim, stable for
    And `## Not yet (1)` lists worker with why `not yet — flapping` and its range over the last 3 runs

  @id:reporting.rightsizing-report.002 @rule:reporting.rightsizing-report.nothing-settled @inferred @source:k8s_rightsizer_report.py#render_report
  Scenario: When nothing has settled the report says so
    Given no recommendation has yet held for 3 runs
    When the operator runs the rightsizer
    Then the report shows `## Proposed (0)` followed by `Nothing has settled yet — nothing to propose.`
    And no patch is printed
