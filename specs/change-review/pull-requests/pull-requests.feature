@domain:change-review @area:pull-requests @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Opening a pull request for review
  Hands settled proposals to reviewers as a GitHub pull request, together with the run that justifies them.

  @id:change-review.pull-requests.001 @rule:change-review.pull-requests.commits-change-with-evidence @verified @source:k8s_rightsizer_report.py#open_pull_request @test:tests/test_rightsizer.py#test_pr_commits_the_patches_with_the_run_that_justifies_them
  Scenario Outline: The pull request commits the change and the run that justifies it together
    Given prod/Deployment/api/app has been stable for 3 runs
    And git and gh are installed and authenticated
    When the operator runs the rightsizer with `--pr <branch option>`
    Then a new branch `<branch>` is created and pushed to origin
    And its single commit holds the api patch and this run's history file
    And a pull request titled `chore(rightsizing): 1 stable recommendation(s) from KRR` is opened and its URL printed

    Examples:
      | branch option                      | branch                     |
      | --branch rightsizer/test           | rightsizer/test            |
      | (none, at 2026-09-01 08:00:00 UTC) | rightsizer/20260901-080000 |

  @id:change-review.pull-requests.002 @rule:change-review.pull-requests.nothing-stable-no-pr @verified @source:k8s_rightsizer_report.py#run_once @test:tests/test_rightsizer.py#test_nothing_stable_opens_no_pull_request
  Scenario: With nothing to propose no pull request is opened
    Given no recommendation has held for 3 runs
    When the operator runs the rightsizer with `--pr`
    Then stderr shows `nothing stable to propose — no pull request opened`
    And no branch is created
    And the command exits with status 0

  @id:change-review.pull-requests.003 @rule:change-review.pull-requests.unchanged-repository-backs-out @verified @source:k8s_rightsizer_report.py#open_pull_request @test:tests/test_rightsizer.py#test_pr_is_not_opened_when_the_patches_already_match_the_repository
  Scenario: When the repository already holds the change the branch is backed out
    Given the patches already match what is committed
    And the run is not recorded
    When the operator runs the rightsizer with `--pr --branch rightsizer/test`
    Then nothing is committed
    And the operator is returned to their previous branch and rightsizer/test is deleted
    And stderr shows `the patches already match the repository — no pull request opened`
    And the command exits with status 0

  @id:change-review.pull-requests.004 @rule:change-review.pull-requests.unplaced-helm-reads-nothing-stable @inferred @source:k8s_rightsizer_report.py#run_once @questionable
  Scenario: Stable Helm proposals that could not be placed are reported as nothing stable
    Given prod/Deployment/api/app has been stable for 3 runs
    And values.yaml has no block for api or app
    When the operator runs the rightsizer with `--helm-values values.yaml --pr`
    Then the report lists api/app under `## Proposed (1)`
    And stderr shows `nothing stable to propose — no pull request opened`

  @id:change-review.pull-requests.005 @rule:change-review.pull-requests.git-failure-leaves-branch @inferred @source:k8s_rightsizer_report.py#_run @questionable
  Scenario: A failed git or gh step leaves the operator on the new branch
    Given prod/Deployment/api/app has been stable for 3 runs
    And pushing to origin is rejected
    When the operator runs the rightsizer with `--pr --branch rightsizer/test`
    Then the command stops with a Python traceback naming the failed git command
    And the checkout is left on rightsizer/test with the change committed
    And the command exits with status 1
