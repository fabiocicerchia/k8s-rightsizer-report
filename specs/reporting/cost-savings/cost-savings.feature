@domain:reporting @area:cost-savings @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Estimating the monthly saving
  Tells reviewers what merging the proposals is worth, using KRR's own costing.

  @id:reporting.cost-savings.001 @rule:reporting.cost-savings.sum-of-proposed @verified @source:k8s_rightsizer_report.py#monthly_saving @test:tests/test_rightsizer.py#test_pr_body_links_the_history_file_and_counts_the_runs
  Scenario: The projected saving sums current minus proposed cost over proposed recommendations
    Given KRR costs prod/Deployment/api/app at 30.00 now and 8.50 recommended
    And api/app is proposed
    When the operator runs the rightsizer
    Then the report shows `Projected saving: 21.50/month (KRR's costing).`
    And held-back recommendations add nothing to it

  @id:reporting.cost-savings.002 @rule:reporting.cost-savings.omitted-without-cost @verified @source:k8s_rightsizer_report.py#monthly_saving @test:tests/test_rightsizer.py#test_saving_is_dropped_when_krr_does_not_cost_the_workload
  Scenario: Without KRR cost data no saving is shown
    Given KRR's output carries no cost for any proposed recommendation
    When the operator runs the rightsizer
    Then the report has no `Projected saving` line
    And with `--json`, `projected_monthly_saving` is null
    And the recommendations are still proposed

  @id:reporting.cost-savings.003 @rule:reporting.cost-savings.partial-and-negative-totals @inferred @source:k8s_rightsizer_report.py#monthly_saving @questionable
  Scenario Outline: The saving silently covers only costed proposals and may be negative
    Given proposed recommendation <a> is costed <cost a>
    And proposed recommendation <b> is costed <cost b>
    When the operator runs the rightsizer
    Then the report shows `Projected saving: <shown>/month (KRR's costing).`

    Examples:
      | a       | cost a        | b          | cost b     | shown |
      | api/app | 30.00 → 8.50  | worker/app | not costed | 21.50 |
      | api/app | 10.00 → 15.00 | worker/app | not costed | -5.00 |
