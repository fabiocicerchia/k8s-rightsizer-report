@domain:recommendation-intake @area:live-krr-scan @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Scanning the cluster with KRR
  Lets an operator get fresh recommendations straight from the cluster by having the tool run KRR for them.

  @id:recommendation-intake.live-krr-scan.001 @rule:recommendation-intake.live-krr-scan.runs-krr-json-scan @inferred @source:k8s_rightsizer_report.py#run_krr
  Scenario: A live scan runs KRR's simple strategy as JSON, scoped and extended as asked
    Given krr is installed on the operator's PATH
    And the operator has not passed a saved KRR file
    When the operator runs the rightsizer with `-n app --krr-arg=--cpu-min=10`
    Then KRR is run as `krr simple --formatter json --quiet -n app --cpu-min=10`
    And the recorded run names its source as `krr simple --formatter json --quiet`
    And the report is built from the recommendations KRR printed

  @id:recommendation-intake.live-krr-scan.002 @rule:recommendation-intake.live-krr-scan.krr-missing-refused @inferred @source:k8s_rightsizer_report.py#run_krr
  Scenario: A live scan without KRR installed is refused with a way forward
    Given krr is not on the operator's PATH
    And the operator has not passed a saved KRR file
    When the operator runs the rightsizer with `-n app`
    Then stderr shows `error: krr is not on PATH — install robusta-dev/krr, or pass --krr-json FILE`
    And the command exits with status 1
    And no run is added to the history

  @id:recommendation-intake.live-krr-scan.003 @rule:recommendation-intake.live-krr-scan.krr-failure-aborts-run @inferred @source:k8s_rightsizer_report.py#run_krr @questionable
  Scenario: A KRR scan that fails aborts the run without recording it
    Given krr is installed but exits with a failure, for example because Prometheus is unreachable
    When the operator runs the rightsizer with `-n app`
    Then the command stops with a Python traceback naming the failed krr command rather than an `error:` line
    And KRR's own error output is not shown
    And the command exits with status 1
    And no run is added to the history
