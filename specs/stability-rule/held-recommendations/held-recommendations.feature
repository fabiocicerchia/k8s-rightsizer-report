@domain:stability-rule @area:held-recommendations @from:k8s-rightsizer-report/k8s-rightsizer-report
Feature: Explaining recommendations that are held back
  Shows reviewers why a recommendation was not proposed, with the evidence, so they can judge the verdict rather than take it.

  @id:stability-rule.held-recommendations.001 @rule:stability-rule.held-recommendations.flapping-with-range @verified @source:k8s_rightsizer_report.py#range_text @test:tests/test_rightsizer.py#test_an_oscillating_recommendation_is_reported_as_flapping
  Scenario: A recommendation that keeps moving is held back as flapping, with its range
    Given KRR recommended 100m, 400m, 120m, 500m CPU for prod/Deployment/api/app
    When the operator runs the rightsizer
    Then api/app is listed under `Not yet` with why `not yet — flapping`
    And its range over the last 3 runs begins `requests.cpu 120m–500m (+317%)`

  @id:stability-rule.held-recommendations.002 @rule:stability-rule.held-recommendations.range-names-moving-dimensions @verified @source:k8s_rightsizer_report.py#range_text @test:tests/test_rightsizer.py#test_the_range_names_the_dimension_that_moved
  Scenario: The range shows only the sizes that moved
    Given KRR recommended 100m, 400m, 100m CPU and a steady 100Mi memory for prod/Deployment/api/app
    When the operator runs the rightsizer
    Then the range reads exactly `requests.cpu 100m–400m (+300%)`
