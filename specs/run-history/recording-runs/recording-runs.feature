@domain:run-history @area:recording-runs @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Recording every run as evidence
  Keeps a committed, dated record of each KRR run so every proposal can be checked against the runs that justified it.

  @id:run-history.recording-runs.001 @rule:run-history.recording-runs.each-run-recorded @verified @source:k8s_rightsizer_report.py#write_run @test:tests/test_rightsizer.py#test_end_to_end_dry_run_prints_the_patches
  Scenario: Each run is saved as a dated file in the history directory
    Given the history directory .rightsizer/history holds two earlier runs
    When the operator runs the rightsizer at 2026-09-01 08:00:00 UTC
    Then a file `.rightsizer/history/2026-09-01T08-00-00Z.json` is added
    And the report header reads ``Engine: KRR (robusta-dev/krr) · history: `.rightsizer/history` (3 runs)``

  @id:run-history.recording-runs.002 @rule:run-history.recording-runs.no-record-opt-out @verified @source:k8s_rightsizer_report.py#run_once @test:tests/test_rightsizer.py#test_no_record_leaves_the_history_alone_but_still_classifies
  Scenario: A one-off run with --no-record is judged against history but not added to it
    Given the history holds two steady runs for prod/Deployment/api/app
    And the new KRR output agrees with them
    When the operator runs the rightsizer with `--no-record --json`
    Then the history still holds two runs
    And api/app is proposed, as the third consecutive run
    And the payload's `history_file` is null

  @id:run-history.recording-runs.003 @rule:run-history.recording-runs.same-second-runs-kept @verified @source:k8s_rightsizer_report.py#next_run_path @test:tests/test_rightsizer.py#test_two_runs_in_the_same_second_do_not_overwrite_each_other
  Scenario: Two runs in the same second are both kept
    Given a run was recorded as `2026-09-01T06-00-00Z.json`
    When the operator runs the rightsizer again within that same second
    Then the new run is saved as `2026-09-01T06-00-00Z_02.json`
    And both runs count, in that order, towards the stability streak

  @id:run-history.recording-runs.004 @rule:run-history.recording-runs.recorded-before-output @inferred @source:k8s_rightsizer_report.py#run_once @questionable
  Scenario: A run is recorded even when generating the change then fails
    Given the history holds two runs
    When the operator runs the rightsizer with `--helm-values values.yaml --helm-key api.resources`
    Then stderr shows `error: --helm-key wants WORKLOAD[/CONTAINER]=DOTTED.PATH, got 'api.resources'`
    And the command exits with status 1
    And the history now holds three runs
