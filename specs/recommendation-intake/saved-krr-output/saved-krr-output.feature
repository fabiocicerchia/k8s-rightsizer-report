@domain:recommendation-intake @area:saved-krr-output @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Reading saved KRR output
  Lets an operator feed a KRR run captured elsewhere (CI, another machine) into the stability history.

  @id:recommendation-intake.saved-krr-output.001 @rule:recommendation-intake.saved-krr-output.reads-file-or-stdin @verified @source:k8s_rightsizer_report.py#load_krr @test:tests/test_rightsizer.py#test_end_to_end_dry_run_prints_the_patches
  Scenario Outline: A saved KRR run is read from a file or from standard input
    Given the operator has the JSON output of `krr simple --formatter json` for api/app in namespace prod
    When the operator runs the rightsizer with `--krr-json <source>`
    Then the report lists `Deployment/api` container `app`
    And the recorded run names its source as `<label>`

    Examples:
      | source   | label         |
      | run.json | file:run.json |
      | -        | file:-        |

  @id:recommendation-intake.saved-krr-output.002 @rule:recommendation-intake.saved-krr-output.tolerates-surrounding-noise @verified @source:k8s_rightsizer_report.py#parse_krr_output @test:tests/test_rightsizer.py#test_parse_krr_output_skips_a_banner_before_the_json
  Scenario: Banner or warning text around the KRR JSON is ignored
    Given the KRR output starts with the line `krr is scanning {this is not json}` before the JSON document
    When the operator runs the rightsizer with `--krr-json run.json`
    Then the KRR document after the banner is used as this run's recommendations

  @id:recommendation-intake.saved-krr-output.003 @rule:recommendation-intake.saved-krr-output.non-krr-output-refused @verified @source:k8s_rightsizer_report.py#parse_krr_output @test:tests/test_rightsizer.py#test_parse_krr_output_rejects_output_with_no_document @test:tests/test_rightsizer.py#test_parse_krr_output_rejects_json_that_is_not_a_krr_run
  Scenario Outline: Output that holds no KRR document is refused
    Given the saved output contains <content>
    When the operator runs the rightsizer with `--krr-json run.json`
    Then stderr shows `error: no krr JSON document found in the output — is this `krr simple --formatter json`?`
    And the command exits with status 1
    And no run is added to the history

    Examples:
      | content                                |
      | krr: connection refused                |
      | {"error": "context deadline exceeded"} |

  @id:recommendation-intake.saved-krr-output.004 @rule:recommendation-intake.saved-krr-output.missing-file-crashes @inferred @source:k8s_rightsizer_report.py#load_krr @questionable
  Scenario: A saved KRR file that does not exist stops the run with a traceback
    Given no file exists at missing.json
    When the operator runs the rightsizer with `--krr-json missing.json`
    Then the command stops with a Python FileNotFoundError traceback rather than an `error:` line
    And the command exits with status 1
    And no run is added to the history
