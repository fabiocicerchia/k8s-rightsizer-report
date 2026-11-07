@domain:reporting @area:json-output @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Machine-readable results
  Gives scripts and pipelines (such as cloudledger) a versioned contract for the same results the report shows.

  @id:reporting.json-output.001 @rule:reporting.json-output.versioned-payload @verified @source:k8s_rightsizer_report.py#_json_payload @test:tests/test_rightsizer.py#test_no_record_leaves_the_history_alone_but_still_classifies
  Scenario: JSON output is a versioned payload of proposals, held recommendations and the rule
    Given the history holds two steady runs for prod/Deployment/api/app and this run agrees
    When the operator runs the rightsizer with `--json`
    Then stdout is a single JSON object whose first keys are `version` (2) and `rows`
    And `rows` lists `prod/Deployment/api/app`
    And `rule` is `{"tolerance_pct": 15.0, "runs": 3, "description": "a recommendation is proposed only once it has stayed within 15% across 3 consecutive runs"}`
    And it also carries `engine` "krr", `history_file`, `held`, `projected_monthly_saving`, `change`, `files` and `warnings`
    And no report is printed and warnings appear only in the payload

  @id:reporting.json-output.002 @rule:reporting.json-output.pr-url-kept-off-stdout @inferred @source:k8s_rightsizer_report.py#run_once
  Scenario: With JSON output the pull request link goes to stderr
    Given a stable recommendation produces a patch
    When the operator runs the rightsizer with `--json --pr`
    Then stdout holds only the JSON payload
    And the pull request URL is printed on stderr
