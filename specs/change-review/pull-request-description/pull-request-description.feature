@domain:change-review @area:pull-request-description @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Explaining the change in the pull request
  Gives reviewers the rule, the per-container evidence and the saving, so they can approve without rerunning anything.

  @id:change-review.pull-request-description.001 @rule:change-review.pull-request-description.rule-and-evidence-per-workload @verified @source:k8s_rightsizer_report.py#render_pr_body @test:tests/test_rightsizer.py#test_pr_body_links_the_history_file_and_counts_the_runs @test:tests/test_rightsizer.py#test_pr_commits_the_patches_with_the_run_that_justifies_them
  Scenario: The pull request explains each change with its stability and saving
    Given prod/Deployment/api/app has been stable for 3 runs, moving from 1000m/1024Mi to 100m/100Mi requests
    And KRR costs it at 30.00 now and 8.50 recommended
    When the operator opens the pull request
    Then the body states `this pull request proposes only the ones that have settled — a recommendation is proposed only once it has stayed within 15% across 3 consecutive runs`
    And a `Deployment prod/api` section shows `1000m/1024Mi → 100m/100Mi` and `3 runs`
    And it shows `Projected saving: **21.50/month**` and the total across the pull request

  @id:change-review.pull-request-description.002 @rule:change-review.pull-request-description.history-link @verified @source:k8s_rightsizer_report.py#Target @test:tests/test_rightsizer.py#test_pr_body_links_the_history_file_and_counts_the_runs
  Scenario Outline: The pull request points the reviewer at the recorded run
    Given the run was <recorded> and the repository is <repo>
    When the operator opens the pull request on branch rightsizer/x
    Then the body ends `History for this run: <link>`

    Examples:
      | recorded                                                  | repo          | link                                                                                                                                             |
      | recorded as .rightsizer/history/2026-09-01T08-00-00Z.json | acme/infra    | [`.rightsizer/history/2026-09-01T08-00-00Z.json`](https://github.com/acme/infra/blob/rightsizer/x/.rightsizer/history/2026-09-01T08-00-00Z.json) |
      | recorded as .rightsizer/history/2026-09-01T08-00-00Z.json | unknown to gh | `.rightsizer/history/2026-09-01T08-00-00Z.json`                                                                                                  |
      | not recorded                                              | acme/infra    | not recorded (`--no-record`)                                                                                                                     |

  @id:change-review.pull-request-description.003 @rule:change-review.pull-request-description.held-back-section @inferred @source:k8s_rightsizer_report.py#render_pr_body @questionable
  Scenario: The pull request lists what was held back as still moving
    Given one recommendation is proposed
    And prod/Deployment/worker/app is held back because its cpu request 120m exceeds its 100m limit
    When the operator opens the pull request
    Then the body has `## Held back (1)` introduced by `Still moving, so not proposed:`
    And worker's why reads `not yet — cpu request 120m exceeds its 100m limit`
